#!/usr/bin/env python
"""10_bench_inference.py — Stage 5: honest CPU vs GPU inference benchmark.

4 profiles (fp32-gpu, fp16-gpu, cpu, dummy) x lengths {76, 100, 200, 300} x
5 repeats (2 warmup dropped) -> median + IQR, VRAM peak. A 60W laptop GPU
throttles: single shots lie, medians don't.

Writes data/report/bench_inference.json and appends an nvidia-smi perf log.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.services.benchmark_service import bench_inference  # noqa: E402

UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")
PROFILES = ["fp32-gpu", "fp16-gpu", "cpu"]
LENGTHS = [76, 100, 200, 300]


def nvidia_perf_snapshot() -> dict:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=clocks.sm,clocks.max.sm,temperature.gpu,"
             "power.draw,power.limit,utilization.gpu,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        vals = [v.strip() for v in out.stdout.strip().split(",")]
        keys = ["clock_sm_mhz", "clock_sm_max_mhz", "temp_c",
                "power_draw_w", "power_limit_w", "util_pct", "mem_used_mb"]
        return dict(zip(keys, vals))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lengths", type=int, nargs="+", default=LENGTHS)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--profiles", nargs="+", default=PROFILES)
    ap.add_argument("--sequence", default=UBIQ)
    args = ap.parse_args()

    print(f"profiles={args.profiles} lengths={args.lengths} repeats={args.repeats}")
    t0 = time.perf_counter()
    rows = bench_inference(args.sequence, args.profiles, args.lengths,
                           args.repeats,
                           progress_cb=lambda f: print(f"  progress {f:.0%}",
                                                       flush=True))
    wall = time.perf_counter() - t0
    snapshot = nvidia_perf_snapshot()

    report = {
        "description": "inference latency/VRAM, median + IQR over repeats "
                       "(2 warmup dropped), RTX 3050 Laptop 6GB, 60W",
        "sequence_len": len(args.sequence),
        "repeats": args.repeats,
        "wall_total_s": round(wall, 1),
        "nvidia_snapshot_end": snapshot,
        "rows": rows,
    }
    out = REPO / "data" / "report" / "bench_inference.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(rows, indent=2))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())