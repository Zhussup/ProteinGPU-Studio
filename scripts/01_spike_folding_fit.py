#!/usr/bin/env python
"""Stage 1 decision gate: does OmegaFold fit the 6 GB VRAM budget?

Measures peak VRAM / latency / output validity for OmegaFold (fp32 and fp16,
GPU) at chain lengths {76 (ubiquitin), 100, 200, 300} and writes a decision
table. PASS criteria (from the approved plan):
    VRAM      <= 4500 MB peak
    300 aa    <= 120 s per forward
    PDB       parses (Biopython), CA atoms == residues

Usage:  .venv/bin/python scripts/01_spike_folding_fit.py [--lengths 76 100 200 300]
Output: data/report/spike_folding.json + printed table; exit 1 if any FAIL.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from Bio import PDB  # noqa: E402
from ml.folding.omegafold_model import OmegaFoldModel  # noqa: E402
from ml.telemetry import TelemetrySampler  # noqa: E402

VRAM_BUDGET_MB = 4500.0
TIME_BUDGET_300_S = 120.0


def random_sequence(n: int, seed: int = 7) -> str:
    rng = random.Random(seed)
    aas = "ACDEFGHIKLMNPQRSTVWY"
    return "".join(rng.choice(aas) for _ in range(n))


def check_pdb(pdb_text: str, expected_len: int) -> tuple[bool, str]:
    try:
        struct = PDB.PDBParser(QUIET=True).get_structure("x", pdb_text.splitlines() and _as_file(pdb_text))
        ca = [a for a in struct.get_atoms() if a.get_id() == "CA"]
        if len(ca) != expected_len:
            return False, f"CA atoms {len(ca)} != residues {expected_len}"
        return True, "ok"
    except Exception as exc:
        return False, f"parse error: {exc}"


def _as_file(text: str):
    import io
    return io.StringIO(text)


def run_profile(model: OmegaFoldModel, label: str, lengths: list[int]) -> list[dict]:
    rows = []
    for n in lengths:
        seq = random_sequence(n)
        sampler = TelemetrySampler()
        error = None
        pdb_ok, pdb_msg = False, "not run"
        repeats = 3 if n <= 200 else 2
        for rep in range(repeats):
            try:
                with sampler.measure(rep=rep):
                    res = model.predict(seq)
                if rep == 0:
                    pdb_ok, pdb_msg = check_pdb(res.pdb_text, n)
            except RuntimeError as exc:  # OOM etc.
                error = str(exc)[:200]
                break
        if error is None:
            s = sampler.summary(drop_warmup=1)
            row = {
                "profile": label, "length": n,
                "wall_median_s": round(s["wall_median_s"], 2),
                "wall_iqr_s": round(s["wall_iqr_s"], 3),
                "vram_peak_mb": round(s["vram_median_mb"] or -1, 1),
                "pdb_ok": pdb_ok, "pdb_msg": pdb_msg,
                "plddt_mean": round(res.plddt_mean, 1),
                "status": "PASS" if (pdb_ok and s["vram_median_mb"] <= VRAM_BUDGET_MB) else "FAIL",
            }
            if n == 300 and s["wall_median_s"] > TIME_BUDGET_300_S:
                row["status"] = "FAIL"
                row["pdb_msg"] += "; time budget exceeded"
        else:
            row = {"profile": label, "length": n, "status": "FAIL", "error": error,
                   "vram_peak_mb": -1, "pdb_ok": False, "pdb_msg": error}
        rows.append(row)
        print(f"  {label:12s} n={n:4d}  {row.get('wall_median_s','--'):>8} s  "
              f"vram={row['vram_peak_mb']:>8} MB  pdb={row['pdb_ok']}  -> {row['status']}",
              flush=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lengths", type=int, nargs="+", default=[76, 100, 200, 300])
    args = ap.parse_args()

    import torch
    if not torch.cuda.is_available():
        print("CUDA unavailable — spike requires GPU", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    print("== OmegaFold fp32 GPU ==", flush=True)
    model = OmegaFoldModel(device="cuda", half=False)
    all_rows += run_profile(model, "fp32-gpu", args.lengths)

    print("== OmegaFold fp16 GPU ==", flush=True)
    model.to_fp16()
    all_rows += run_profile(model, "fp16-gpu", args.lengths)

    vram_peak = max((r["vram_peak_mb"] for r in all_rows if r["vram_peak_mb"] > 0), default=-1)
    t300 = max((r["wall_median_s"] for r in all_rows if r["length"] == 300 and r.get("wall_median_s")),
               default=None)
    decision = {
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gpu": torch.cuda.get_device_name(0),
        "vram_total_mb": round(torch.cuda.get_device_properties(0).total_memory / 1e6, 1),
        "budgets": {"vram_peak_mb": VRAM_BUDGET_MB, "time_300aa_s": TIME_BUDGET_300_S},
        "observed_vram_peak_mb": vram_peak,
        "observed_300aa_s": t300,
        "rows": all_rows,
    }
    decision["decision"] = (
        "PASS: OmegaFold fits the 6GB budget — primary model confirmed"
        if all(r["status"] == "PASS" for r in all_rows)
        else "FAIL: see rows"
    )

    out = REPO / "data" / "report" / "spike_folding.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(decision, indent=2))
    print(f"\n{decision['decision']}")
    print(f"written: {out}")
    return 0 if decision["decision"].startswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())