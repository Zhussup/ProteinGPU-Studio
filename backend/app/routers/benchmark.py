"""Benchmark endpoints (inference profiles + kernel micro-bench)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ..schemas import (  # noqa: E402
    BenchmarkProfileRow, BenchmarkRequest, BenchmarkResponse)
from ..services.benchmark_service import (  # noqa: E402
    bench_inference, bench_kernels)
from ..services.folding_service import get_folding_service  # noqa: E402
from ..services.job_manager import Job, get_job_manager  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["benchmark"])

ALLOWED_PROFILES = {"fp32-gpu", "fp16-gpu", "cpu", "dummy"}


def _run_benchmark(job: Job) -> dict:
    rows = bench_inference(
        sequence=job.params["sequence"],
        profiles=job.params["profiles"],
        lengths=job.params.get("lengths"),
        repeats=job.params["repeats"],
        progress_cb=lambda p: setattr(job, "progress", p),
    )
    return {"rows": rows}


@router.post("/benchmark", response_model=BenchmarkResponse)
def benchmark(req: BenchmarkRequest) -> BenchmarkResponse:
    bad = set(req.profiles) - ALLOWED_PROFILES
    if bad:
        from fastapi import HTTPException
        raise HTTPException(422, f"unknown profiles: {sorted(bad)}")
    # Профили только-CPU (и dummy) не занимают GPU-слот.
    # 仅 CPU 的配置（及 dummy）不需要 GPU 名额。
    use_gpu = bool(set(req.profiles) - {"cpu", "dummy"}) and "omegafold" in get_folding_service().model_name
    jm = get_job_manager()
    job_id = jm.submit(kind="benchmark",
                       params={"sequence": req.sequence, "profiles": req.profiles,
                               "lengths": req.lengths, "repeats": req.repeats},
                       run_fn=_run_benchmark, use_gpu=use_gpu)
    return BenchmarkResponse(job_id=job_id, status="queued")


def _run_kernel_benchmark(job: Job) -> dict:
    p = job.params
    return {"rows": bench_kernels(B=p["pairs"], N=p["atoms"],
                                  repeats=p["repeats"])}


@router.post("/benchmark/kernels")
def benchmark_kernels(pairs: int = 2048, atoms: int = 512, repeats: int = 9):
    pairs = min(max(pairs, 1), 8192)
    atoms = min(max(atoms, 3), 2048)
    jm = get_job_manager()
    job_id = jm.submit(kind="benchmark_kernels",
                       params={"pairs": pairs, "atoms": atoms, "repeats": repeats},
                       run_fn=_run_kernel_benchmark, use_gpu=False)
    return {"job_id": job_id, "status": "queued"}