"""Benchmark service: CPU vs GPU inference + kernel micro-benchmarks.

Runs inside a job (GPU ones hold the GPU semaphore). Produces rows for the
BenchmarksPage: per (profile, length) median wall + IQR + VRAM peak, with
warmup runs discarded — the 60W laptop throttles, single shots lie.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ml.telemetry import TelemetrySampler  # noqa: E402

from .folding_service import get_folding_service  # noqa: E402


def bench_inference(sequence: str, profiles: list[str], lengths: list[int] | None,
                    repeats: int, progress_cb=None) -> list[dict]:
    """Fold `lengths` variants (sequence truncated/extended deterministically).

    profiles: subset of {"fp32-gpu", "fp16-gpu", "cpu", "dummy"} — "dummy"
    rows use the dummy model so the UI can be benchmarked without GPU.
    """
    svc = get_folding_service()
    real_model = svc.model
    torch = _try_torch()
    on_gpu = torch is not None and torch.cuda.is_available() and real_model.device == "cuda"

    if lengths:
        seqs = {n: _variant_of_length(sequence, n) for n in lengths}
    else:
        seqs = {len(sequence): sequence}

    rows: list[dict] = []
    total = max(1, len(profiles) * len(seqs))
    done = 0
    for profile in profiles:
        if profile == "dummy":
            from ml.folding.dummy_model import DummyModel
            model = DummyModel()
        else:
            model = real_model
            if profile == "fp16-gpu" and on_gpu and hasattr(model, "to_fp16"):
                model.to_fp16()
            elif profile == "fp32-gpu" and on_gpu and hasattr(model, "to_fp32"):
                model.to_fp32()
            elif profile == "cpu" and on_gpu:
                # move resident model to CPU for the reference row, then back
                inner = getattr(model, "_model", None)
                if inner is not None:
                    inner.float().to("cpu")
                    model.device = "cpu"

        for n, seq in seqs.items():
            sampler = TelemetrySampler()
            for rep in range(repeats):
                with sampler.measure(rep=rep):
                    model.predict(seq)
                if progress_cb:
                    done += 1
                    progress_cb(done / total)
            s = sampler.summary(drop_warmup=2)
            rows.append({
                "profile": profile,
                "length": n,
                "wall_median_s": round(s["wall_median_s"], 4),
                "wall_iqr_s": round(s["wall_iqr_s"], 4),
                "vram_peak_mb": round(s["vram_median_mb"], 1) if s["vram_median_mb"] else None,
                "repeats": s["n"],
            })

        # restore resident state between profiles
        if profile != "dummy" and on_gpu:
            inner = getattr(model, "_model", None)
            if inner is not None:
                inner.float().to("cuda")
            model.device = "cuda"
        if profile == "fp16-gpu" and hasattr(model, "to_fp32"):
            model.to_fp32()
        if torch is not None and on_gpu:
            torch.cuda.empty_cache()

    return rows


def bench_kernels(B: int = 2048, N: int = 512, repeats: int = 9) -> list[dict]:
    """Kernel micro-benchmark: numpy vs C++ OpenMP vs CUDA (host/resident)."""
    import numpy as np

    rng = np.random.default_rng(0)
    P = rng.uniform(-5, 5, (B, N, 3))
    Q = P + rng.normal(0, 0.05, P.shape)

    rows = []

    # numpy reference (median of repeats)
    import time

    def kabsch_numpy_batch(P, Q):
        Pc, Qc = P - P.mean(1, keepdims=True), Q - Q.mean(1, keepdims=True)
        out = np.empty(len(P))
        for b in range(len(P)):
            U, S, Wt = np.linalg.svd(Pc[b].T @ Qc[b])
            d = np.sign(np.linalg.det(U @ Wt))
            R = (U @ np.diag([1.0, 1.0, d]) @ Wt).T
            out[b] = np.sqrt(((Pc[b] @ R.T - Qc[b]) ** 2).sum() / len(P))
        return out

    walls = []
    for _ in range(3):  # warmup
        kabsch_numpy_batch(P[:2], Q[:2])
    for _ in range(repeats):
        t0 = time.perf_counter()
        kabsch_numpy_batch(P, Q)
        walls.append(time.perf_counter() - t0)
    rows.append(_kernel_row("numpy", B, N, walls))

    import hpc_core
    walls = []
    for _ in range(2):
        hpc_core.batched_rmsd(P[:2], Q[:2], use_gpu=False)
    for _ in range(repeats):
        t0 = time.perf_counter()
        hpc_core.batched_rmsd(P, Q, use_gpu=False)
        walls.append(time.perf_counter() - t0)
    rows.append(_kernel_row("cpp-openmp", B, N, walls))

    if hpc_core.HAS_CUDA:
        walls = []
        for _ in range(2):
            hpc_core.batched_rmsd(P, Q, use_gpu=True)
        for _ in range(repeats):
            t0 = time.perf_counter()
            hpc_core.batched_rmsd(P, Q, use_gpu=True)
            walls.append(time.perf_counter() - t0)
        rows.append(_kernel_row("cuda-pcie", B, N, walls))

        # zero-copy path: tensors resident on GPU
        if _try_torch() is not None and _try_torch().cuda.is_available():
            torch = _try_torch()
            Pt = torch.from_numpy(P).cuda()
            Qt = torch.from_numpy(Q).cuda()
            hpc_core.batched_rmsd(Pt, Qt)
            walls = []
            for _ in range(repeats):
                t0 = time.perf_counter()
                hpc_core.batched_rmsd(Pt, Qt)
                walls.append(time.perf_counter() - t0)
            rows.append(_kernel_row("cuda-resident", B, N, walls))

    return rows


def _kernel_row(engine: str, B: int, N: int, walls: list[float]) -> dict:
    import numpy as np
    walls = sorted(walls)
    med = float(np.median(walls))
    q1, q3 = walls[int(0.25 * len(walls))], walls[min(len(walls) - 1, int(0.75 * len(walls)))]
    return {"engine": engine, "pairs": B, "atoms": N,
            "wall_median_s": round(med, 5), "wall_iqr_s": round(q3 - q1, 5)}


def _variant_of_length(sequence: str, n: int) -> str:
    """Deterministic sequence of length n derived from the input."""
    aas = "ACDEFGHIKLMNPQRSTVWY"
    if n <= len(sequence):
        return sequence[:n]
    out = list(sequence)
    i = 0
    while len(out) < n:
        out.append(aas[(i * 7 + len(out)) % 20])
        i += 1
    return "".join(out)


def _try_torch():
    try:
        import torch
        return torch
    except ImportError:
        return None