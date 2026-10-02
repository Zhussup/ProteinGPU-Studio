#!/usr/bin/env python
"""31_proteingym_numbering.py — inventory + numbering audit of ProteinGym DMS.

Step 1 of the paper protocol (dum.md / plan): before any statistics, prove that
the mutant strings in a chosen assay point at the same residues we fold. The
classic pitfall: an assay's internal numbering (leader peptide, construct
boundaries, 1QJP-style domain numbering) diverging from target_seq.

Method: WT = modal value of `mutated_sequence` (or `target_seq` column);
every mutant "X123Y" must satisfy target[123-1] == 'X'. If not, scan offsets
-10..+10 and report the best reconciling shift (and whether one exists at all).

Usage:
    python scripts/31_proteingym_numbering.py --inventory        # all 217 ids
    python scripts/31_proteingym_numbering.py --audit 1QJP_Wu_2016   # full audit
    python scripts/31_proteingym_numbering.py --audit auto       # GB1/ubq candidates
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUBS = REPO / "data" / "proteingym" / "substitutions"
REPORT = REPO / "data" / "report"
DEFAULT_CANDIDATES = re.compile(r"SPG1|RL40A|GB1|UBQ|Ubiq", re.IGNORECASE)
UBQ_RE = re.compile(r"UBQ|Roscoe|Mavor|RL40A", re.IGNORECASE)
MUT_RE = re.compile(r"^([A-Z])(\d+)([A-Z])$")


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return f.readline().rstrip("\n").split(",")


def iter_rows(path: Path):
    import csv
    with path.open("r", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def consensus_wt(path: Path, sample_cap: int = 2000) -> str:
    """WT = per-position majority vote over **single-substitution rows only**.

    Modal-sequence breaks when every row is unique; column votes over *all*
    rows break when a position is mutated in most rows (Wu-2016's hot spots
    266/267/280 are on a double-mutant background in most of its 150k rows).
    Singles never overwhelm a column: each single mutates exactly its own
    position, so WT wins everywhere else and wins at hot spots too.
    """
    lines = []
    seen = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        f.readline()  # header
        for row in f:
            mut = row.split(",", 1)[0]
            if ":" in mut or not MUT_RE.match(mut):
                continue
            seen += 1
            if seen % 2 == 0:  # mild thinning, plenty anyway
                lines.append(row.split(",", 2)[1])
                if len(lines) >= sample_cap:
                    break
    if len(lines) < 30:
        print(f"  warn: {path.name}: only {len(lines)} single rows for WT vote")
    n, m = len(lines), len(lines[0])
    assert all(len(s) >= m for s in lines), "ragged mutated_sequence widths"
    votes = [Counter(s[j] for s in lines if len(s) > j) for j in range(m)]
    return "".join(v.most_common(1)[0][0] for v in votes)


def audit(path: Path) -> dict:
    """WT = column-major consensus; audit **single** substitutions only.

    The Wu-2016 file stores ~150k colon-joined 2-substitution mutants ("the
    pairwise epistasis paper") inside the substitutions benchmark — those are
    phase-2 epistasis material, not the 19-vector singles; they are counted,
    not audited. Every single 'X123Y' must satisfy target[123-1] == 'X'; if
    the assay numbers a *domain* inside a parent sequence, the per-residue
    occurrence scan reports the reconciling offset.
    """
    cols = read_header(path)
    wt = consensus_wt(path)
    idx_by_aa: dict[str, list[int]] = {}
    for i, ch in enumerate(wt):
        idx_by_aa.setdefault(ch, []).append(i)

    n_rows = n_singles = n_multi = n_bad = n_range = 0
    offsets = Counter()
    dup_mutants = Counter()
    singles_by_pos: Counter = Counter()
    pos_min, pos_max = 10**9, 0
    for r in iter_rows(path):
        n_rows += 1
        mut = r["mutant"].strip()
        dup_mutants[mut] += 1
        if ":" in mut:
            n_multi += 1
            continue
        m = MUT_RE.match(mut)
        if not m:
            n_bad += 1
            continue
        n_singles += 1
        wt_aa, pos_s, mut_aa = m.groups()
        pos = int(pos_s)
        singles_by_pos[pos] += 1
        pos_min, pos_max = min(pos_min, pos), max(pos_max, pos)
        if not (1 <= pos <= len(wt)):
            n_range += 1
            continue
        if wt[pos - 1] == wt_aa:
            offsets[0] += 1
        for i in idx_by_aa.get(wt_aa, ()):
            if i != pos - 1:
                offsets[i - (pos - 1)] += 1

    best_off, best_hit = None, offsets[0]
    for off, hit in offsets.items():
        if off != 0 and hit > best_hit:
            best_off, best_hit = off, hit
    full_19 = sum(1 for _, c in singles_by_pos.items() if c >= 19)
    frac = lambda hit: round(hit / max(1, n_singles), 4)
    dups = {k: v for k, v in dup_mutants.items() if v > 1}
    return {
        "file": path.name, "consensus_len": len(wt),
        "rows": n_rows, "singles": n_singles, "multi_subs": n_multi,
        "unparseable_singles": n_bad,
        "singles_positions": sorted(singles_by_pos),
        "positions_with_full_19": full_19,
        "match_at_offset_0": frac(offsets[0]),
        "out_of_range": n_range,
        "best_offset": best_off, "best_offset_match": frac(best_hit),
        "duplicate_mutant_strings": len(dups),
        "wt_seq": wt,
    }


def fasta_seq(path: Path) -> str:
    return "".join(line.strip() for line in path.read_text().splitlines()
                   if line.strip() and not line.startswith(">"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=Path, default=SUBS)
    ap.add_argument("--inventory", action="store_true",
                    help="list all assays (id, row count) and exit")
    ap.add_argument("--audit", default="auto",
                    help="'auto' (GB1/ubq candidates), a DMS_id, 'all', or '' to skip")
    ap.add_argument("--fasta", type=Path, default=REPO / "data" / "examples" / "ubiq.fasta",
                    help="our WT fasta to compare against ubiquitin assays")
    ap.add_argument("--candidates", default=r"SPG1|RL40A|GB1|UBQ|Ubiq")
    args = ap.parse_args()

    files = sorted(args.dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"no CSVs under {args.dir} — run 30_download_proteingym.py")
    print(f"{len(files)} assay files in {args.dir}")

    if args.inventory:
        for f in files:
            cols = read_header(f)
            print(f"  {f.stem:<40} {cols}")
        return

    cand_re = re.compile(args.candidates, re.IGNORECASE)
    order = {f.stem: i for i, f in enumerate(files)}
    chosen = ([f for f in files if cand_re.search(f.stem)] if args.audit == "auto"
              else [args.dir / f"{args.audit}.csv"] if args.audit not in ("", "all")
              else files)
    if args.audit == "auto" and len(chosen) == len(files):
        print("--candidates matched everything; audit first 5 to stay fast")
        chosen = chosen[:5]

    results = {}
    our_ubq = fasta_seq(args.fasta) if args.fasta.exists() else None
    for f in sorted(chosen, key=lambda p: order[p.stem]):
        res = audit(f)
        res["our_fasta_identity"] = None
        if our_ubq and UBQ_RE.search(f.stem):
            # prefix identity vs our canonical-ubq fasta (RL40A is an Ub-L40A
            # fusion, so only the overlapping span is comparable)
            a, b = res["wt_seq"], our_ubq
            same = sum(x == y for x, y in zip(a, b))
            res["our_fasta_identity"] = round(same / min(len(a), len(b)), 3)
        results[f.stem] = res
        f0, off, foff = res["match_at_offset_0"], res["best_offset"], res["best_offset_match"]
        if f0 >= 0.99:
            verdict = f"OK at offset 0 ({f0:.1%})"
        elif off is not None and foff >= 0.99:
            verdict = f"DOMAIN NUMBERING: single pos + ({off}) -> consensus ({foff:.1%})"
        else:
            verdict = f"SUSPECT: offset0 {f0:.1%}, best offset {off} ({foff:.1%})"
        print(f"\n{f.stem}")
        print(f"  consensus_len={res['consensus_len']} rows={res['rows']} "
              f"singles={res['singles']} multi_subs={res['multi_subs']} "
              f"full_19_positions={res['positions_with_full_19']} "
              f"dup_strings={res['duplicate_mutant_strings']}")
        print(f"  -> {verdict}")
        if res["our_fasta_identity"]:
            print(f"  identity vs our fasta: {res['our_fasta_identity']:.1%}")

    REPORT.mkdir(parents=True, exist_ok=True)
    out = REPORT / "proteingym_numbering.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    sys.exit(main())