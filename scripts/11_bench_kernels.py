#!/usr/bin/env python
"""11_bench_kernels.py — Stage 5: Kabsch kernel micro-benchmark matrix.

Sweeps (pairs B, atoms N) over {(64,76), (1024,256), (2048,512), (4096,1024)}
for engines numpy / cpp-openmp / cuda-pcie / cuda-resident. Reports
median + IQR wall times -> data/report/bench_kernels.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.services.benchmark_service import bench_kernels  # noqa: E402

SWEEP = [(64, 76), (1024, 256), (2048, 512), (4096, 1024)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=9)
    ap.add_argument("--sweep", type=int, nargs="+",
                    help="B N pairs, e.g. --sweep 1024 512 4096 1024")
    args = ap.parse_args()

    sweep = list(zip(args.sweep[::2], args.sweep[1::2])) if args.sweep else SWEEP
    rows = []
    t0 = time.perf_counter()
    for B, N in sweep:
        print(f"B={B} N={N} ...", flush=True)
        rows.extend(bench_kernels(B=B, N=N, repeats=args.repeats))
    wall = time.perf_counter() - t0

    report = {
        "description": "Kabsch batched RMSD kernel wall time, median + IQR; "
                       "cuda-pcie includes 2x H2D/D2H copies, cuda-resident is "
                       "the zero-copy device-resident path",
        "repeats": args.repeats,
        "wall_total_s": round(wall, 1),
        "rows": rows,
    }
    out = REPO / "data" / "report" / "bench_kernels.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(rows, indent=2))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())