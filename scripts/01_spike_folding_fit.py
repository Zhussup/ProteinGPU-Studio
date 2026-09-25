#!/usr/bin/env python
"""Stage 1 decision gate: does OmegaFold fit the 6 GB VRAM budget?

Measures peak VRAM / latency / output validity for OmegaFold (fp32 and fp16
autocast, GPU) at chain lengths {76 (ubiquitin), 100, 200, 300} and writes a
decision table. PASS criteria (from the approved plan):
    VRAM      <= 4500 MB peak
    300 aa    <= 120 s per forward
    PDB       parses (Biopython), CA atoms == residues

Each profile runs in a FRESH subprocess: a CUDA OOM in one profile leaves the
allocator/context poisoned and would cascade into false FAILs for the rest
(observed on run 3 — fp32 300aa OOM took the whole fp16 phase down with it).

Usage:  .venv/bin/python scripts/01_spike_folding_fit.py \
            [--lengths 76 100 200 300] [--profiles fp32-gpu fp16-gpu]
Output: data/report/spike_folding.json + printed table; exit 1 if any FAIL.
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
OUT = REPO / "data" / "report" / "spike_folding.json"

VRAM_BUDGET_MB = 4500.0
TIME_BUDGET_300_S = 120.0


def run_profile_subprocess(profile: str, lengths: list[int]) -> list[dict]:
    """Run one profile in a fresh process; merge its rows from a side JSON."""
    side = REPO / "data" / "report" / f"_spike_{profile}.json"
    cmd = [sys.executable, str(SELF), "--_worker", profile,
           "--lengths", *[str(n) for n in lengths],
           "--_out", str(side)]
    proc = subprocess.run(cmd, cwd=REPO, timeout=3600)
    if proc.returncode != 0 or not side.exists():
        return [{"profile": profile, "length": n, "status": "FAIL",
                 "error": f"worker exit {proc.returncode}", "vram_peak_mb": -1,
                 "pdb_ok": False, "pdb_msg": "worker crashed"}
                for n in lengths]
    return json.loads(side.read_text())


def run_worker(profile: str, lengths: list[int], out_path: Path) -> int:
    """In-process profile run (executed inside the fresh subprocess)."""
    import random
    sys.path.insert(0, str(REPO))

    from Bio import PDB
    from ml.folding.omegafold_model import OmegaFoldModel
    from ml.telemetry import TelemetrySampler

    def random_sequence(n: int, seed: int = 7) -> str:
        rng = random.Random(seed)
        aas = "ACDEFGHIKLMNPQRSTVWY"
        return "".join(rng.choice(aas) for _ in range(n))

    def check_pdb(pdb_text: str, expected_len: int) -> tuple[bool, str]:
        try:
            struct = PDB.PDBParser(QUIET=True).get_structure(
                "x", io.StringIO(pdb_text))
            ca = [a for a in struct.get_atoms() if a.get_id() == "CA"]
            if len(ca) != expected_len:
                return False, f"CA atoms {len(ca)} != residues {expected_len}"
            return True, "ok"
        except Exception as exc:  # noqa: BLE001
            return False, f"parse error: {exc}"

    model = OmegaFoldModel(device="cuda", half=False)
    if profile == "fp16-gpu":
        model.to_fp16()

    rows = []
    for n in lengths:
        seq = random_sequence(n)
        sampler = TelemetrySampler()
        error = None
        pdb_ok, pdb_msg = False, "not run"
        repeats = 3 if n <= 200 else 2
        res = None
        for rep in range(repeats):
            try:
                with sampler.measure(rep=rep):
                    res = model.predict(seq)
                if rep == 0:
                    pdb_ok, pdb_msg = check_pdb(res.pdb_text, n)
            except RuntimeError as exc:  # OOM и т.п. | OOM 等
                error = f"{type(exc).__name__}: {str(exc)[:300]}"
                break
        if error is None:
            s = sampler.summary(drop_warmup=1)
            row = {
                "profile": profile, "length": n,
                "wall_median_s": round(s["wall_median_s"], 2),
                "wall_iqr_s": round(s["wall_iqr_s"], 3),
                "vram_peak_mb": round(s["vram_median_mb"] or -1, 1),
                "pdb_ok": pdb_ok, "pdb_msg": pdb_msg,
                "plddt_mean": round(res.plddt_mean, 1) if res else -1,
                "status": "PASS" if (pdb_ok and s["vram_median_mb"] <= VRAM_BUDGET_MB)
                          else "FAIL",
            }
            if n == 300 and row["wall_median_s"] > TIME_BUDGET_300_S:
                row["status"] = "FAIL"
                row["pdb_msg"] += "; time budget exceeded"
        else:
            row = {"profile": profile, "length": n, "status": "FAIL", "error": error,
                   "vram_peak_mb": -1, "pdb_ok": False, "pdb_msg": error}
        rows.append(row)
        print(f"  {profile:12s} n={n:4d}  {row.get('wall_median_s', '--'):>8} s  "
              f"vram={row['vram_peak_mb']:>8} MB  pdb={row['pdb_ok']}  -> {row['status']}"
              + (f"  [{row['error'][:120]}]" if error else ""), flush=True)
        if error:  # состояние аллокатора отравлено — останавливаем профиль здесь | 分配器状态已损坏——就此停止该配置
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lengths", type=int, nargs="+", default=[76, 100, 200, 300])
    ap.add_argument("--profiles", nargs="+", default=["fp32-gpu", "fp16-gpu"])
    ap.add_argument("--_worker")
    ap.add_argument("--_out")
    args = ap.parse_args()

    # режим worker: один профиль в этом (свежем) процессе
    # worker 模式：在本（全新）进程中运行一个配置
    if args._worker:
        assert args._out, "--_worker requires --_out"
        return run_worker(args._worker, args.lengths, Path(args._out))

    import torch
    if not torch.cuda.is_available():
        print("CUDA unavailable — spike requires GPU", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    for profile in args.profiles:
        print(f"== OmegaFold {profile} (fresh subprocess) ==", flush=True)
        all_rows += run_profile_subprocess(profile, args.lengths)

    vram_peak = max((r["vram_peak_mb"] for r in all_rows if r["vram_peak_mb"] > 0),
                    default=-1)
    t300 = max((r["wall_median_s"] for r in all_rows
                if r["length"] == 300 and r.get("wall_median_s")), default=None)
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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(decision, indent=2))
    print(f"\n{decision['decision']}")
    print(f"written: {OUT}")
    # подчищаем side-файлы
    # 清理临时文件
    for p in OUT.parent.glob("_spike_*.json"):
        p.unlink()
    return 0 if decision["decision"].startswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())