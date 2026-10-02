#!/usr/bin/env python
"""33_prepare_fold_targets.py — WT sequences to fold + numbering map for v1.

The bridge between the scan-map pipeline and ProteinGym. For each chosen
assay it derives the WT (column-major consensus over single-substitution
rows, verified by 31) with an explicit fold-mapping rule:

  RL40A_YEAST_*   fold the full 128-aa Ub-L40A fusion, mutant pos -> fold pos
                  (offset 0; the fusion is what the growth selection measured).
  SPG1_STRSG_*    fold the isolated 56-aa GB1 domain sliced from the parent
                  (mutant position p maps to fold position p - 226; singles
                  cover fold positions 2..56, so the untouched pos-1 edge
                  residue is D in the parent, M in the historical construct).

Outputs per assay:
  data/proteingym/targets/<assay>.fasta            (WT sequence to fold)
  data/report/paper_fold_targets.json              (mapping + sanity stats)

Every single mutant is re-verified against the fold sequence: fold[p+off-1]
== wt_aa for ALL singles, else the script refuses to emit anything.
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
SUBS = REPO / "data" / "proteingym" / "substitutions"
TARGETS = REPO / "data" / "proteingym" / "targets"
REPORT = REPO / "data" / "report"
MUT_RE = re.compile(r"^([A-Z])(\d+)([A-Z])$")

# v1 targets (plan 2026-09-29): GB1 (full single scan) + ubiquitin (fusion,
# best-coverage Ub assay). Wu_2016 stays out of v1 — 4 positions only, its
# 149k doubles are the phase-2 epistasis channel.
DEFAULT_ASSAYS = ["SPG1_STRSG_Olson_2014", "RL40A_YEAST_Roscoe_2014"]


def consensus_wt(path: Path, sample_cap: int = 4000) -> str:
    lines, seen = [], 0
    with path.open("r", encoding="utf-8", newline="") as f:
        f.readline()
        for row in f:
            mut = row.split(",", 1)[0]
            if ":" in mut or not MUT_RE.match(mut):
                continue
            seen += 1
            if seen % 2 == 0:
                lines.append(row.split(",", 2)[1])
                if len(lines) >= sample_cap:
                    break
    if len(lines) < 30:
        raise SystemExit(f"{path.name}: only {len(lines)} single rows — consensus unsafe")
    seqs = lines
    votes = [Counter(s[j] for s in seqs if len(s) > j) for j in range(len(seqs[0]))]
    return "".join(v.most_common(1)[0][0] for v in votes)


def load_singles(path: Path) -> list[tuple[int, str, str]]:
    out = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            m = MUT_RE.match(r["mutant"].strip())
            if m:
                out.append((int(m.group(2)), m.group(1), m.group(3)))
    return out


def fold_rule(assay: str, wt: str, single_positions: list[int]) -> tuple[str, int, str]:
    """Returns (fold_seq, mut_pos_offset, note). fold pos = mut pos + offset.

    Mutant strings are in PARENT numbering (that is what the offset-0 audit
    proved); the fold target is the isolated construct, hence the offset.
    """
    lo, hi = min(single_positions), max(single_positions)
    if assay.startswith("RL40A"):
        # the growth selection measured the full Ub-L40A fusion: fold it whole
        return wt, 0, "full 128-aa Ub-L40A fusion, direct mapping"
    if assay.startswith("SPG1"):
        # GB1 domain: construct = M1 + (construct 2..56, PDB 1PGB numbering)
        # = parent's 228..282 residues; the parent's residue at the domain
        # edge (D at 227) vs the construct's cloning M is the one unswept
        # divergence — recorded for the methods section.
        seq = "M" + wt[lo - 1:hi]  # M + parent 228..282 (0-based 227..281)
        offset = -(lo - 2)         # parent p -> construct p - 226
        assert len(seq) == 56 and seq[0] == "M" and seq[1] == "Q", \
            f"GB1 construct wrong: len={len(seq)}, starts {seq[:2]}"
        return seq, offset, ("isolated 56-aa GB1 construct (PDB 1PGB Q2..E56); "
                             "M1 replaces the parent's edge D at parent 227 — unswept")
    raise SystemExit(f"no fold rule for {assay} — define one or add it here")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--assays", nargs="*", default=DEFAULT_ASSAYS)
    args = ap.parse_args()

    TARGETS.mkdir(parents=True, exist_ok=True)
    out = {}
    for assay in args.assays:
        path = SUBS / f"{assay}.csv"
        if not path.exists():
            raise SystemExit(f"missing {path} — run 30_download_proteingym.py")
        wt = consensus_wt(path)
        singles = load_singles(path)
        positions = sorted({p for p, _, _ in singles})
        wt_by_pos = {}
        for p, w, m in singles:
            wt_by_pos.setdefault(p, w)
            if wt_by_pos[p] != w:
                raise SystemExit(f"{assay} pos {p}: conflicting WT letters {wt_by_pos[p]} vs {w}")
        fold_seq, off, note = fold_rule(assay, wt, positions)
        bad = [(p, w, m) for p, w, m in singles
               if not (1 <= p + off <= len(fold_seq)) or fold_seq[p + off - 1] != w]
        if bad:
            raise SystemExit(f"{assay}: {len(bad)} singles fail the fold mapping, "
                             f"e.g. {bad[:3]}")
        full19 = sorted(p for p in positions
                        if sum(1 for pp, _, _ in singles if pp == p) >= 19)
        fasta = TARGETS / f"{assay}.fasta"
        fasta.write_text(f">{assay}|wt|{len(fold_seq)}aa\n{fold_seq}\n")
        out[assay] = {
            "dms_file": str(path.relative_to(REPO)),
            "fold_fasta": str(fasta.relative_to(REPO)),
            "fold_seq": fold_seq, "fold_len": len(fold_seq),
            "mut_pos_offset": off,
            "construct_note": note,
            "single_rows": len(singles),
            "scanned_positions": positions,
            "positions_with_full_19": full19,
        }
        print(f"{assay}: fold {len(fold_seq)} aa, {len(singles)} singles, "
              f"{len(full19)}/{len(positions)} positions with full 19 -> {fasta.name}")

    dest = REPORT / "paper_fold_targets.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    sys.exit(main())