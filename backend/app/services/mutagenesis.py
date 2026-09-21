"""Grantham substitution spectrum + variant sampler + distribution stats.

The mutagenesis-strength dial (dum.md §2): on the input the dial is how many
and which mutations to generate — mu, the number of simultaneous substitutions
per variant, and tau, a scalar "temperature" of the substitution spectrum
weighted by Grantham distance (conservative ↔ radical). On the output the
position's sensitivity is the DISTRIBUTION of structural responses across the
sampled variants — never a two-structure eyeball comparison.

Pure stdlib (random, hashlib, math): no numpy/torch, so the sampler and the
stats are unit-testable in milliseconds. The router feeds the sampled
mutation sets to the folding service one sequence at a time.

Two-halves spectrum: for a site with WT residue w, the 19 available
substitutions are split by Grantham distance into a conservative half (10
lowest distances) and a radical half (9 highest). Temperature tau mixes the
halves: tau=0 draws only from the conservative half, tau=1 only from the
radical half, tau=0.5 is the near-uniform mixture of the two (10 + 9
candidates, so 1/20 vs 1/18 per draw — deviation from the exact uniform
1/19 is negligible).
"""
from __future__ import annotations

import hashlib
import math
import random

# project alphabet (== ml.folding.base.AA_RE) — iteration order defines the
# exhaustive mode's fold order, so it must stay byte-identical to /scan's
AA = "ACDEFGHIKLMNPQRSTVWY"

# layout of the published 20x20 table (Grantham 1974, Science 185:862-864,
# Table 2); keep this order so re-transcription against the paper is mechanical
GRANTHAM_ORDER = "ARNDCQEGHILKMFPSTWYV"

_MUT_ROWS = [
    #     A    R    N    D    C    Q    E    G    H    I    L    K    M    F    P    S    T    W    Y    V
    [   0, 112, 111, 126, 195,  91, 107,  60,  86,  94,  96, 106,  84, 113,  27,  99,  58, 148, 112,  64],  # A
    [ 112,   0,  86,  96, 180,  43,  54, 125,  29,  97, 102,  26,  91,  97, 103, 110,  71, 101,  77,  96],  # R
    [ 111,  86,   0,  23, 139,  46,  42,  80,  68, 149, 153,  94, 142, 158,  91,  46,  65, 174, 143, 133],  # N
    [ 126,  96,  23,   0, 154,  61,  45,  94,  81, 168, 172, 101, 160, 177, 108,  65,  85, 181, 160, 152],  # D
    [ 195, 180, 139, 154,   0, 154, 170, 159, 174, 198, 198, 202, 196, 205, 169, 112, 149, 215, 194, 192],  # C
    [  91,  43,  46,  61, 154,   0,  29,  87,  24, 109, 113,  53, 101, 116,  76,  68,  42, 130,  99,  96],  # Q
    [ 107,  54,  42,  45, 170,  29,   0,  98,  40, 134, 138,  56, 126, 140,  93,  80,  65, 152, 122, 121],  # E
    [  60, 125,  80,  94, 159,  87,  98,   0,  98, 135, 138, 127, 127, 153,  42,  56,  59, 184, 147, 109],  # G
    [  86,  29,  68,  81, 174,  24,  40,  98,   0,  94,  99,  32,  87, 100,  77,  89,  47, 115,  83,  84],  # H
    [  94,  97, 149, 168, 198, 109, 134, 135,  94,   0,   5, 102,  10,  21,  95, 142,  89,  61,  33,  29],  # I
    [  96, 102, 153, 172, 198, 113, 138, 138,  99,   5,   0, 107,  15,  22,  98, 145,  92,  61,  36,  32],  # L
    [ 106,  26,  94, 101, 202,  53,  56, 127,  32, 102, 107,   0,  95, 102, 103, 121,  78, 110,  85,  97],  # K
    [  84,  91, 142, 160, 196, 101, 126, 127,  87,  10,  15,  95,   0,  28,  87, 135,  81,  67,  36,  21],  # M
    [ 113,  97, 158, 177, 205, 116, 140, 153, 100,  21,  22, 102,  28,   0, 114, 155, 103,  40,  22,  50],  # F
    [  27, 103,  91, 108, 169,  76,  93,  42,  77,  95,  98, 103,  87, 114,   0,  74,  38, 147, 110,  68],  # P
    [  99, 110,  46,  65, 112,  68,  80,  56,  89, 142, 145, 121, 135, 155,  74,   0,  58, 177, 144, 124],  # S
    [  58,  71,  65,  85, 149,  42,  65,  59,  47,  89,  92,  78,  81, 103,  38,  58,   0, 128,  92,  69],  # T
    [ 148, 101, 174, 181, 215, 130, 152, 184, 115,  61,  61, 110,  67,  40, 147, 177, 128,   0,  37,  88],  # W
    [ 112,  77, 143, 160, 194,  99, 122, 147,  83,  33,  36,  85,  36,  22, 110, 144,  92,  37,   0,  55],  # Y
    [  64,  96, 133, 152, 192,  96, 121, 109,  84,  29,  32,  97,  21,  50,  68, 124,  69,  88,  55,   0],  # V
]

GRANTHAM: dict[str, dict[str, int]] = {}
for _i, _a in enumerate(GRANTHAM_ORDER):
    GRANTHAM[_a] = dict(zip(GRANTHAM_ORDER, _MUT_ROWS[_i]))


def grantham(a: str, b: str) -> int:
    """Grantham (1974) physico-chemical distance; grantham(a, a) == 0."""
    return GRANTHAM[a][b]


# -- mutation set construction -------------------------------------------------
Mutation = tuple[int, str, str]  # (1-based position, wt_aa, mut_aa)


def substitution_halves(wt_aa: str) -> tuple[list[str], list[str]]:
    """(conservative, radical) halves of the 19 substitutions at a site.

    Candidates = AA minus wt_aa, sorted by (Grantham distance, letter); the 10
    lowest form the conservative half, the 9 highest the radical half. The
    letter tiebreak makes the split deterministic.
    """
    cands = [a for a in AA if a != wt_aa]
    ranked = sorted(cands, key=lambda a: (GRANTHAM[wt_aa][a], a))
    return ranked[:10], ranked[10:]


def derived_seed(sequence: str, position: int, mu: int, tau: float, k: int) -> int:
    """Reproducibility without an explicit seed: the same configuration always
    folds the same ensemble (demo/README friendly); an explicit seed overrides."""
    key = f"ensemble:{sequence}:{position}:{mu}:{tau:.2f}:{k}"
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)


def _draw_one(sequence: str, position: int, mu: int, tau: float,
              rng: random.Random) -> list[Mutation]:
    """One variant: the anchor always mutated + (mu-1) distinct background
    sites; every site's substitution drawn from the tau-spectrum (mut != wt)."""
    n = len(sequence)
    others = [p for p in range(1, n + 1) if p != position]
    sites = sorted([position] + rng.sample(others, mu - 1))
    muts: list[Mutation] = []
    for p in sites:
        wt_aa = sequence[p - 1]
        cons, rad = substitution_halves(wt_aa)
        pool = rad if rng.random() < tau else cons
        mut_aa = pool[rng.randrange(len(pool))]
        muts.append((p, wt_aa, mut_aa))
    return muts


def sample_variants(sequence: str, position: int, mu: int, tau: float,
                    k: int, seed: int) -> list[list[Mutation]]:
    """K distinct mutation sets. The anchor position is mutated in every
    variant (mut_aa != wt_aa there); background sites are distinct, != the
    anchor and uniform over the rest of the chain. Deterministic given seed."""
    rng = random.Random(seed)
    variants: list[list[Mutation]] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = 200 * k
    while len(variants) < k:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError(
                f"cannot draw {k} distinct variants (mu={mu}) — "
                "the mutation space is exhausted")
        muts = _draw_one(sequence, position, mu, tau, rng)
        key = apply_mutations(sequence, muts)
        if key in seen:
            continue
        seen.add(key)
        variants.append(muts)
    return variants


def exhaustive_mutations(sequence: str, position: int) -> list[list[Mutation]]:
    """All 19 single substitutions at the position, in the project AA order —
    exactly the /scan target list (the lossless-migration requirement)."""
    wt_aa = sequence[position - 1]
    return [[(position, wt_aa, a)] for a in AA if a != wt_aa]


def apply_mutations(sequence: str, muts: list[Mutation]) -> str:
    """Build the mutant sequence; same 1-based splice as
    ml.folding.base.mutant_sequence (kept local so this module stays stdlib)."""
    seq = sequence
    for pos, _wt_aa, mut_aa in muts:
        if not (1 <= pos <= len(seq)):
            raise ValueError(f"position {pos} out of range 1..{len(seq)}")
        seq = seq[: pos - 1] + mut_aa + seq[pos:]
    return seq


def mutation_label(muts: list[Mutation]) -> str:
    """'I44A' for a single substitution, 'I44A+L3M' for several (sorted by
    position — the label carries the site order)."""
    return "+".join(f"{wt}{pos}{m}" for pos, wt, m in muts)


# -- distribution stats + headline (the output side of the dial) ---------------

def distribution_stats(values: list[float]) -> dict[str, float]:
    """{mean, std (population, ddof=0), median, iqr (p75-p25), min, max}.

    Quantiles use linear interpolation on the sorted list (numpy's 'linear'
    convention), pinned by unit tests. Pure python: the backend has no
    numpy-based stats (the benchmark's median/IQR precedent is index-based).
    """
    xs = sorted(float(v) for v in values)
    n = len(xs)
    if n == 0:
        raise ValueError("no values")
    mean = sum(xs) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in xs) / n)

    def q(p: float) -> float:
        idx = p * (n - 1)
        lo = math.floor(idx)
        hi = math.ceil(idx)
        return xs[lo] + (xs[hi] - xs[lo]) * (idx - lo)

    return {"mean": mean, "std": std, "median": q(0.5),
            "iqr": q(0.75) - q(0.25), "min": xs[0], "max": xs[-1]}


def sensitivity_headline(stats_local_rmsd: dict[str, float],
                         med_abs_dplddt_local: float) -> dict[str, float | str]:
    """Distribution verdict — no invented 0-100 score (dum.md §6 honesty).

    level reuses the existing bands: quiet = both medians below 1.0, strong =
    either median >= 2.0 (local RMSD in Å, |ΔpLDDT| in pLDDT points). width is
    the relative spread of the response distribution (IQR / median).
    """
    med_lr = stats_local_rmsd["median"]
    iqr = stats_local_rmsd["iqr"]
    iqr_ratio = iqr / max(med_lr, 0.05)
    if med_lr < 1.0 and med_abs_dplddt_local < 1.0:
        level = "quiet"
    elif med_lr >= 2.0 or med_abs_dplddt_local >= 2.0:
        level = "strong"
    else:
        level = "moderate"
    if iqr_ratio <= 0.2:
        width = "narrow"
    elif iqr_ratio <= 0.6:
        width = "moderate"
    else:
        width = "wide"
    return {
        "level": level, "width": width, "iqr_ratio": iqr_ratio,
        "median_local_rmsd": med_lr,
        "median_abs_dplddt_local": med_abs_dplddt_local,
    }