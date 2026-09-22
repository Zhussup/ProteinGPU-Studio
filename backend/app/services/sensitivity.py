"""Position sensitivity math for the scan map / "wind rose" (dum.md §5).

Pure stdlib: the fixed petal compass, per-position scalars, the
hedgehog/needle/disk/clover quadrant classification, within-protein percentile
normalization and the flat CSV projection. No folding here — the router feeds
measured 19-vectors in; this module turns them into rose-ready data (and into
the dataset rows the future surrogate + DMS bridge consume), unit-testable in
milliseconds like mutagenesis.py.
"""
from __future__ import annotations

import math

# Same alphabet as mutagenesis.AA / ml.folding.base.AA_RE.
AA = "ACDEFGHIKLMNPQRSTVWY"

# Fixed rose compass (dum.md §5): physico-chemical sectors in a fixed order,
# alphabetical within a sector. The order is position-INDEPENDENT so roses of
# different positions are directly comparable; a position's WT residue leaves
# an empty slot (the notch) instead of reshuffling the compass.
SECTORS: dict[str, str] = {
    "hydrophobic": "AVILM",
    "aromatic": "FWY",
    "polar": "STNQ",
    "acidic": "DE",
    "basic": "KRH",
    "special": "GCP",
}
SECTOR_ORDER = ("hydrophobic", "aromatic", "polar", "acidic", "basic", "special")
PETAL_DIRS = "".join(SECTORS[s] for s in SECTOR_ORDER)          # "AVILMFWYSTNQDEKRHGCP"
SECTOR_OF: dict[str, str] = {aa: s for s in SECTOR_ORDER for aa in SECTORS[s]}


def petal_dirs(wt_aa: str) -> list[str]:
    """The 19 substitution directions for a WT residue, in compass order."""
    return [aa for aa in PETAL_DIRS if aa != wt_aa]


# -- per-position scalars and quadrant -----------------------------------------

# Quadrant thresholds, pinned to the existing honesty bands: 1.0/2.0 Å are the
# interpret_rmsd stable/critical edges; a needle must actually stick out past
# the stable band to be called one.
STRONG_MED = 1.0      # median local RMSD (Å) separating quiet from responding
SHARP_RATIO = 2.0     # max/median ratio that marks one dominant direction
NEEDLE_MIN_MAX = 1.0  # a needle needs max >= this (Å), else the bump is noise

QUADRANTS = ("hedgehog", "needle", "disk", "clover")

QUADRANT_WORDS: dict[str, dict[str, str]] = {
    "ru": {
        "hedgehog": "ёж (ломается любая замена)",
        "needle": "игла (больно в одном химическом направлении)",
        "disk": "диск (толерантная позиция)",
        "clover": "клевер (сильно, но рвано — несколько ярких лепестков)",
    },
    "en": {
        "hedgehog": "hedgehog (every substitution hurts)",
        "needle": "needle (one chemical direction hurts)",
        "disk": "disk (tolerant position)",
        "clover": "clover (strong but ragged — several bright petals)",
    },
    "zh": {
        "hedgehog": "海胆（任何替换都致伤）",
        "needle": "尖针（仅一个化学方向致伤）",
        "disk": "圆盘（耐受位点）",
        "clover": "三叶草（强烈但破碎——几片亮花瓣）",
    },
}


def position_stats(local_rmsd: list[float],
                   abs_dplddt_local: list[float]) -> dict[str, float | str]:
    """Scalars + quadrant for one position's 19 responses.

    local_rmsd: per-substitution local RMSD values (any order);
    abs_dplddt_local: |ΔpLDDT| of the local window per substitution.
    The 3D paint scalar V(i) is max/mean local RMSD; the rose's length channel
    stays |ΔpLDDT_local| (dum.md §6 honesty hierarchy) — both shipped.
    """
    if len(local_rmsd) != 19 or len(abs_dplddt_local) != 19:
        raise ValueError("a sensitivity vector has exactly 19 responses")
    xs = sorted(local_rmsd)
    med = xs[9]  # median of 19 = the 10th smallest, no float ambiguity
    mx = xs[-1]
    mean = sum(xs) / len(xs)
    med_dp = sorted(abs_dplddt_local)[9]

    # No-signal guard: nothing moves anywhere -> disk regardless of the ratio.
    if mx < 1e-9:
        quadrant = "disk"
    elif med < STRONG_MED:
        sharp = mx >= max(med * SHARP_RATIO, NEEDLE_MIN_MAX)
        quadrant = "needle" if sharp else "disk"
    else:
        quadrant = "hedgehog" if mx < med * SHARP_RATIO else "clover"

    return {
        "median_local_rmsd": med, "max_local_rmsd": mx,
        "mean_local_rmsd": mean, "median_abs_dplddt_local": med_dp,
        "sharpness": mx / max(med, 1e-9),
        "quadrant": quadrant,
    }


# -- within-protein normalization ----------------------------------------------

def percentile_rank(x: float, arr: list[float]) -> float:
    """Rank of x in arr, 0..1 — fraction of values strictly below, over n-1.

    Byte-parity with the frontend's SensitivityCompare.rank(): ties sit at the
    bottom (a constant array maps everything to 0.0, not 0.5); a single
    element maps to 0.5. Both sides normalize identically by construction.
    """
    below = sum(1 for v in arr if v < x)
    return below / (len(arr) - 1) if len(arr) > 1 else 0.5


def normalize_protein(positions: list[dict]) -> None:
    """Add within-protein percentiles in place (dum.md §5: petal length and
    paint scalar are percentiles inside the protein, raw values stay visible).

    Adds to each position dict: stats["pctl_v_max"], stats["pctl_v_med"] and a
    per-row "pctl" (rank of |dplddt_local| among ALL responses of the protein).
    """
    n_pos = len(positions)
    if n_pos == 0:
        return
    v_maxes = [p["stats"]["max_local_rmsd"] for p in positions]
    v_meds = [p["stats"]["median_local_rmsd"] for p in positions]
    pool: list[float] = []
    for p in positions:
        pool.extend(r["abs_dplddt_local"] for r in p["rows"])
    for p in positions:
        p["stats"]["pctl_v_max"] = percentile_rank(p["stats"]["max_local_rmsd"], v_maxes)
        p["stats"]["pctl_v_med"] = percentile_rank(p["stats"]["median_local_rmsd"], v_meds)
        for r in p["rows"]:
            r["pctl"] = percentile_rank(r["abs_dplddt_local"], pool)


# -- dataset projection ---------------------------------------------------------

CSV_HEADER = ("position,wt_aa,mut_aa,sector,grantham,local_rmsd,global_rmsd,"
              "tm_score,plddt_mut,dplddt,dplddt_local,abs_dplddt_local,pctl,"
              "engine")


def build_csv(positions: list[dict]) -> str:
    """Flat DMS-ready projection: one row per (position, substitution).

    The scan map JSON is the viewer's artifact; this CSV is the dataset row
    format (dum.md §3) — the same values the rose displays, unfolded into
    ProteinGym-`DMS_substitutions`-shaped lines.
    """
    out = [CSV_HEADER]
    for p in positions:
        for r in p["rows"]:
            out.append(",".join([
                str(p["pos"]), p["wt_aa"], r["mut_aa"],
                SECTOR_OF[r["mut_aa"]],
                str(r["grantham"]),
                f"{r['local_rmsd']:.6f}", f"{r['global_rmsd']:.6f}",
                f"{r['tm_score']:.6f}", f"{r['plddt_mut']:.4f}",
                f"{r['dplddt']:+.4f}", f"{r['dplddt_local']:+.4f}",
                f"{r['abs_dplddt_local']:.4f}", f"{r['pctl']:.4f}",
                r["engine"],
            ]))
    return "\n".join(out) + "\n"


def quadrant_counts(positions: list[dict]) -> dict[str, int]:
    counts = {q: 0 for q in QUADRANTS}
    for p in positions:
        counts[p["stats"]["quadrant"]] += 1
    return counts


def most_fragile(positions: list[dict]) -> dict | None:
    """The position with the highest within-protein v_max percentile."""
    return max(positions, key=lambda p: p["stats"]["pctl_v_max"], default=None)