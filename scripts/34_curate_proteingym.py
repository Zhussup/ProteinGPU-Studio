#!/usr/bin/env python
"""34_curate_proteingym.py — curate the local ProteinGym DMS downloads.

The substitutions benchmark is already on disk (scripts/30_download_proteingym.py,
data/proteingym/substitutions/, 217 assays). This script walks every assay once,
counts the single-substitution rows, verifies numbering against the per-assay
consensus WT (column vote, scripts/31_proteingym_numbering.consensus_wt) and
writes the COMMITTED manifest data/dms/curated.json — the only part of the
benchmark that reaches git (the CSVs are gitignored, ~1 GB).

Curation rule (small whites, fully swept):
  consensus_len <= 250 AND singles >= 100 AND singles/rows >= 0.9
  AND match_at_offset_0 >= 0.95 (numbering sane) AND not a giant (GFP
  excluded by default; --include-giant to admit it as a stress case).

Rows are deduplicated by (pos, alt) at load time in the API; here we only
count the duplicates so the manifest is honest about what an assay holds.

Usage:
    python scripts/34_curate_proteingym.py                 # sweep + curate
    python scripts/34_curate_proteingym.py --keep 12
    python scripts/34_curate_proteingym.py --include-giant
Exit codes: 0 ok; 3 schema drift / no data; 4 curation is empty.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

SUBS = REPO / "data" / "proteingym" / "substitutions"
OUT_DIR = REPO / "data" / "dms"
OUT = OUT_DIR / "curated.json"

MUT_SINGLE = re.compile(r"^([A-Z])(\d+)([A-Z])$")
GIANT_RE = re.compile(r"GFP|NS3|HIV1_ENV|BRCA1|TP53", re.IGNORECASE)


def consensus_wt(path: Path, sample_cap: int = 2000) -> str:
    """Same protocol as the numbering audit (31): column vote over singles."""
    from importlib import import_module
    audit = import_module("31_proteingym_numbering")
    return audit.consensus_wt(path, sample_cap)


def sweep(path: Path) -> dict:
    """One pass over the assay: counts + (pos, alt) inventory of singles."""
    consensus = consensus_wt(path)
    n_rows = n_singles = n_multi = n_bad = n_range = n_mismatch = 0
    dups: Counter = Counter()
    singles_by_pos: Counter = Counter()
    with path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames or []
        if "mutant" not in cols:
            raise SchemaDrift(f"{path.name}: no 'mutant' column: {cols[:6]}…")
        for r in rdr:
            n_rows += 1
            mut = (r.get("mutant") or "").strip()
            if ":" in mut:
                n_multi += 1
                continue
            m = MUT_SINGLE.match(mut)
            if not m:
                n_bad += 1
                continue
            n_singles += 1
            wt_aa, pos_s, mut_aa = m.groups()
            pos = int(pos_s)
            dups[(pos, mut_aa)] += 1
            singles_by_pos[pos] += 1
            if not (1 <= pos <= len(consensus)):
                n_range += 1
            elif consensus[pos - 1] != wt_aa:
                n_mismatch += 1
    n_dup_keys = sum(1 for c in dups.values() if c > 1)
    return {
        "consensus_seq": consensus,
        "rows": n_rows, "singles": n_singles, "multi": n_multi,
        "bad_rows": n_bad,
        "out_of_range": n_range, "wt_letter_mismatches": n_mismatch,
        "positions_swept": len(singles_by_pos),
        "positions_with_full_19": sum(1 for c in singles_by_pos.values() if c >= 19),
        "duplicate_pair_keys": n_dup_keys,
    }


class SchemaDrift(RuntimeError):
    pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", type=int, default=8,
                    help="cap the curated list (seq_len asc, then singles desc)")
    ap.add_argument("--include-giant", action="store_true",
                    help="admit GFP-class assays (tens of thousands of rows)")
    args = ap.parse_args()

    if not SUBS.is_dir() or not any(SUBS.glob("*.csv")):
        print(f"no ProteinGym CSVs under {SUBS} — run scripts/30_download_proteingym.py first",
              file=sys.stderr)
        sys.exit(3)

    files = sorted(SUBS.glob("*.csv"))
    print(f"{len(files)} assays in {SUBS}")
    inventory = []
    for f in files:
        try:
            info = sweep(f)
        except SchemaDrift as e:
            print(f"  SCHEMA DRIFT: {e}", file=sys.stderr)
            sys.exit(3)
        inventory.append({"dms_id": f.stem, "file": str(f.relative_to(REPO)), **info})
        print(f"  {f.stem:<44} len={len(info['consensus_seq']):>3}  "
              f"singles={info['singles']:>6}  multi={info['multi']:>7}")

    rules_ok = [a for a in inventory
                if len(a["consensus_seq"]) <= 250
                and a["singles"] >= 100
                and a["singles"] / max(1, a["rows"]) >= 0.9
                and a["out_of_range"] + a["wt_letter_mismatches"] == 0
                and a["bad_rows"] == 0]
    giants = [a for a in rules_ok if GIANT_RE.search(a["dms_id"])]
    if not args.include_giant:
        rules_ok = [a for a in rules_ok if not GIANT_RE.search(a["dms_id"])]
    print(f"curated rule: {len(rules_ok)} pass "
          f"({len(giants)} giant{'s' if len(giants) != 1 else ''} excluded; "
          f"--include-giant to admit)")

    rules_ok.sort(key=lambda a: (len(a["consensus_seq"]), -a["singles"]))
    chosen = rules_ok[:args.keep]
    if not chosen:
        print("curation is empty — relax the rules or check the downloads",
              file=sys.stderr)
        sys.exit(4)

    manifest = {
        "rule": ("consensus_len<=250, singles>=100, singles/rows>=0.9, "
                 "numbering clean (offset-0 verified), no unparseable rows"),
        "giant_excluded": [a["dms_id"] for a in giants] if not args.include_giant else [],
        "swept": len(inventory),
        "assays": chosen,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\nwrote {OUT} ({len(chosen)} assays)")
    for a in chosen:
        print(f"  {a['dms_id']:<44} L={len(a['consensus_seq'])} "
              f"singles={a['singles']} pos={a['positions_swept']}")


if __name__ == "__main__":
    sys.exit(main())