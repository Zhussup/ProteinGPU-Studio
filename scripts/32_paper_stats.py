#!/usr/bin/env python
"""32_paper_stats.py — pre-registered v1 analysis: structural response vs DMS.

Question of the paper (plan 2026-09-29, refined by the PLM-vs-structure debate):
what does the *perpositional structural channel* (single-shot folding response:
local RMSD, |ΔpLDDT_local|) carry about experimental fitness *beyond*
zero-shot PLM scoring and Grantham? Not Pak et al.'s global ΔpLDDT-vs-ΔΔG
(r≈−0.17) — per-position 19-vectors: "роза против розы".

Pre-registered (no fitting, honest on weak signal):
  1. per-position Spearman ρ(pred_proxy, DMS fitness) over the 19 substitutions,
     proxy = −response so that *higher = predicted healthier* for every channel;
  2. median ρ over positions > 0 — sign test (binomial, one-sided);
  3. beats Grantham baseline; adds signal beyond PLM ΔScore — partial
     Spearman (rank-residualization) controlling Grantham + PLM;
  4. quadrant validation: hedgehog/needle/disk/clover positions vs DMS median;
  5. noise floor: WT-vs-WT replicate runs — ρ between two no-mutation runs.

Channels: structural (from scan-map exports, sensitivity.CSV_HEADER format),
Grantham (from the same export), PLM ΔScore (optional side file, phase 1.5).

Usage:
    python scripts/32_paper_stats.py --selftest                    # known answers
    python scripts/32_paper_stats.py --dms <file.csv> --structural <dir|csv> \
        [--plm <scores.csv>] [--replicate <dir|csv>]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.services.mutagenesis import grantham  # noqa: E402
from app.services.sensitivity import position_stats  # noqa: E402

REPORT = REPO / "data" / "report"
# The full 20-letter alphabet (sensitivity.AA); the response vector from an
# export holds exactly the 19 substitutions *excluding* the WT residue, so the
# analysis iterates over the export's own keys, sorted for determinism —
# never over a hardcoded AA list that would include the WT letter.
AA20 = "ACDEFGHIKLMNPQRSTVWY"
MUT_SINGLE = re.compile(r"^([A-Z])(\d+)([A-Z])$")


def load_dms(path: Path) -> dict[tuple[int, str], float]:
    """(pos, mut_aa) -> mean fitness over duplicate rows. Column 'mutant'."""
    col = None
    out: dict[tuple[int, str], list[float]] = defaultdict(list)
    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        col = "DMS_score" if "DMS_score" in (rdr.fieldnames or []) else rdr.fieldnames[-1]
        for r in rdr:
            m = r.get("mutant", "")
            if m and MUT_SINGLE.match(m.strip()):
                wt_aa, pos, mut_aa = MUT_SINGLE.match(m.strip()).groups()
                if r[col]:
                    out[(pos, mut_aa)].append(float(r[col]))
    return {k: sum(v) / len(v) for k, v in out.items()}


def load_structural(path: Path) -> dict[int, dict[str, dict[str, float]]]:
    """Scan-map export CSVs -> per-position {mut_aa: {local_rmsd, abs_dplddt_local, grantham}}."""
    rows = []
    for csvp in ([path] if path.is_file() else sorted(path.glob("*.csv"))):
        with csvp.open(newline="") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    pos: dict[int, dict[str, dict[str, float]]] = defaultdict(dict)
    for r in rows:
        pos[int(r["position"])][r["mut_aa"]] = {
            "local_rmsd": float(r["local_rmsd"]),
            "abs_dplddt_local": float(r["abs_dplddt_local"]),
            "grantham": float(r["grantham"]),
        }
    return pos


def partial_spearman(y: np.ndarray, x: np.ndarray, controls) -> float:
    """Partial Spearman: rank-transform all, OLS-residualize, Pearson.

    With a single control this equals the classic rank-residualization partial
    correlation; with several it is the natural extension without any fitting
    of the target quantity (no leakage — controls and DMS stay external).
    """
    ry = np.asarray(stats.rankdata(y), float)
    rx = np.asarray(stats.rankdata(x), float)
    rc = np.column_stack([np.asarray(stats.rankdata(np.asarray(c, float)), float)
                          for c in controls])
    A = np.column_stack([np.ones_like(ry), rc])
    res_y = ry - A @ np.linalg.lstsq(A, ry, rcond=None)[0]
    res_x = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    if res_y.std() < 1e-12 or res_x.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(res_y, res_x)[0, 1])


def per_position_rho(structural, dms, min_points=19):
    """Per-position: ρ and partial ρ of each channel vs DMS over the 19-vector.

    Strict 'роза против розы': positions need all 19 substitutions folded and
    (default min_points=19) all 19 DMS cells read; relax min_points only if
    coverage turns out thin — then ρ runs on the present subset.
    """
    res = {"rmsd": [], "dplddt": [], "grantham": [], "rmsd_partial": [],
           "dplddt_partial": []}
    used = []
    for p, muts in sorted(structural.items()):
        if len(muts) != 19:
            continue
        aas = sorted(muts)
        y = np.array([dms.get((p, aa), np.nan) for aa in aas], float)
        if np.isnan(y).sum() > len(y) - min_points:
            continue
        keep = ~np.isnan(y)
        if keep.sum() < min_points:
            continue
        y = y[keep]
        aas_k = [aas[i] for i in np.flatnonzero(keep)]
        r_rmsd = [-muts[aa]["local_rmsd"] for aa in aas_k]
        r_dp = [-muts[aa]["abs_dplddt_local"] for aa in aas_k]
        gran = [muts[aa]["grantham"] for aa in aas_k]
        used.append(p)
        res["rmsd"].append(stats.spearmanr(r_rmsd, y).statistic)
        res["dplddt"].append(stats.spearmanr(r_dp, y).statistic)
        res["grantham"].append(stats.spearmanr([-g for g in gran], y).statistic)
        res["rmsd_partial"].append(partial_spearman(y, r_rmsd, [gran]))
        res["dplddt_partial"].append(partial_spearman(y, r_dp, [gran]))
    for key in res:
        res[key] = [float(r) for r in res[key] if not np.isnan(r)]
    return used, res


def sign_test(rhos: list[float]) -> dict:
    n = len(rhos)
    if not n:
        return {"n_positions": 0, "positive": 0, "median_rho": float("nan"),
                "sign_test_p": float("nan")}
    k = sum(1 for r in rhos if r > 0)
    p = stats.binomtest(k, n, 0.5, alternative="greater").pvalue
    return {"n_positions": n, "positive": k, "median_rho": float(np.median(rhos)),
            "sign_test_p": float(p)}


def quadrant_table(structural, dms):
    """hedgehog/needle/disk/clover positions: median DMS fitness of their mutants."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for p, muts in structural.items():
        if len(muts) != 19:
            continue
        aas = sorted(muts)
        st = position_stats([muts[aa]["local_rmsd"] for aa in aas],
                            [muts[aa]["abs_dplddt_local"] for aa in aas])
        for aa in aas:
            if (p, aa) in dms:
                buckets[st["quadrant"]].append(dms[(p, aa)])
    return {q: {"n_mutants": len(v), "median_fitness": float(np.median(v))}
            for q, v in buckets.items()}


def noise_floor(rep1, rep2, dms):
    """WT-vs-WT: ρ between two replicate response 19-vectors, per position."""
    res = {"rmsd": [], "dplddt": []}
    for p, muts_a in rep1.items():
        muts_b = rep2.get(p)
        if not muts_b or len(muts_a) != 19 or len(muts_b) != 19:
            continue
        aas = sorted(muts_a)
        for key, field in (("rmsd", "local_rmsd"), ("dplddt", "abs_dplddt_local")):
            a = [-muts_a[aa][field] for aa in aas]
            b = [-muts_b[aa][field] for aa in aas]
            r = stats.spearmanr(a, b).statistic
            if not np.isnan(r):
                res[key].append(float(r))
    return {k: sign_test(v) if v else None for k, v in res.items()}


def selftest() -> dict:
    """Known-answers test on synthetic data: structural channel is real,
    grantham is a shared confound — partial ρ must survive, sign test pass."""
    rng = np.random.default_rng(19)
    n_pos = 40
    rhos, rhos_p, rhos_g = [], [], []
    for _ in range(n_pos):
        gran = np.array([grantham("A", aa) for aa in AA20], float)
        latent = -0.6 * stats.zscore(gran) - 0.5 * rng.normal(size=20)
        resp = -latent * (1.0 + 0.1 * rng.normal(size=20))  # measured response
        dms = latent + 0.6 * rng.normal(size=20)            # noisy assay
        rhos.append(stats.spearmanr(-resp, dms).statistic)
        rhos_g.append(stats.spearmanr(-gran, dms).statistic)
        rhos_p.append(partial_spearman(dms, -resp, [gran]))
    out = {
        "structural": sign_test(rhos), "structural_partial": sign_test(rhos_p),
        "grantham": sign_test(rhos_g),
    }
    ok = (out["structural"]["median_rho"] > 0.5 and out["structural"]["sign_test_p"] < 1e-3
          and out["structural_partial"]["median_rho"] > 0.3)
    print(json.dumps({k: {kk: round(vv, 3) if isinstance(vv, float) else vv
                          for kk, vv in v.items()} for k, v in out.items()}, indent=2))
    print("selftest:", "PASS" if ok else "FAIL")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dms", type=Path, help="ProteinGym per-assay CSV")
    ap.add_argument("--structural", type=Path, help="scan-map export dir or CSV")
    ap.add_argument("--plm", type=Path, help="columns: pos,mut_aa,dscore (optional)")
    ap.add_argument("--replicate", type=Path,
                    help="2nd scan-map export (WT-vs-WT double run) for noise floor")
    ap.add_argument("--min-points", type=int, default=19)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.dms or not args.structural:
        raise SystemExit("--dms and --structural required (or --selftest)")

    dms = load_dms(args.dms)
    structural = load_structural(args.structural)
    used, res = per_position_rho(structural, dms, min_points=args.min_points)

    out = {
        "dms_file": str(args.dms), "structural_source": str(args.structural),
        "positions_used": len(used),
        "structural_rmsd": sign_test(res["rmsd"]),
        "structural_dplddt": sign_test(res["dplddt"]),
        "grantham_baseline": sign_test(res["grantham"]),
        "partial_controlling_grantham": {
            "rmsd": sign_test(res["rmsd_partial"]),
            "dplddt": sign_test(res["dplddt_partial"]),
        },
        "quadrants": quadrant_table(structural, dms),
    }
    if args.replicate:
        rep2 = load_structural(args.replicate)
        out["noise_floor_wt_vs_wt"] = noise_floor(structural, rep2, dms)
    if args.plm:
        plm_scores: dict[tuple[int, str], float] = {}
        with args.plm.open(newline="") as f:
            for r in csv.DictReader(f):
                plm_scores[(int(r["pos"]), r["mut_aa"])] = float(r["dscore"])
        out["plm_present"] = len(plm_scores)
        # partial vs structural controlling Grantham + PLM goes in phase 1.5;
        # the machinery (partial_spearman) is exercised by --selftest.

    REPORT.mkdir(parents=True, exist_ok=True)
    dest = REPORT / "paper_v1_stats.json"
    dest.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items()
                      if not isinstance(v, str) and k != "plm_present"}, indent=2))
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    sys.exit(main())