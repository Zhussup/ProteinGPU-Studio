"""Python wrapper for the Kabsch/RMSD HPC core.

Loads the compiled extension (CUDA build preferred when present), validates
inputs, and exposes numpy-friendly functions plus an AlignmentResult dataclass.
Engine tag travels with every result so the UI/report always discloses which
engine produced a number ("cuda" | "cpp").
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass

import numpy as np

_CUDA_MODULE = "hpc_core_native_cuda"
_CPU_MODULE = "hpc_core_native"


@dataclass(frozen=True)
class AlignmentResult:
    rmsd: float
    tm_score: float
    R: np.ndarray  # [3,3] вращение, row-major | [3,3] 旋转矩阵，行主序
    t: np.ndarray  # [3] сдвиг | [3] 平移向量
    n: int
    engine: str


def _load():
    """Prefer the CUDA build; fall back to CPU-only. Returns (module, has_cuda)."""
    import os
    import sys

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)
    try:
        return importlib.import_module(_CUDA_MODULE), True
    except ImportError:
        return importlib.import_module(_CPU_MODULE), False


_native, HAS_CUDA = _load()


def _to_coords(x) -> np.ndarray:
    # torch-тензоры принимаются через numpy-протокол (detach → cpu → numpy)
    # torch 张量经 numpy 协议接收（detach → cpu → numpy）
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"expected [N,3] coordinates, got {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError("coordinates contain NaN/inf")
    return np.ascontiguousarray(arr)


def _is_cuda_tensor(x) -> bool:
    # device-тензоры torch/cupy выставляют __cuda_array_interface__; нативный
    # слой принимает их по указателю с нулём PCIe-копий.
    # torch/cupy 设备张量暴露 __cuda_array_interface__；原生层按指针接收，零 PCIe 拷贝。
    return hasattr(x, "__cuda_array_interface__")


def kabsch(P, Q) -> AlignmentResult:
    """Optimal rigid alignment of P onto Q (Kabsch). Returns RMSD, R, t, TM-score."""
    if HAS_CUDA and _is_cuda_tensor(P) and _is_cuda_tensor(Q):
        try:
            r = _native.kabsch_rmsd_cuda(P, Q)  # быстрый путь для тензоров на устройстве | 设备常驻张量的快速路径
        except Exception:
            r = _native.kabsch_rmsd_cpu(_to_coords(P), _to_coords(Q))
        return AlignmentResult(
            rmsd=float(r["rmsd"]), tm_score=float(r["tm_score"]),
            R=np.asarray(r["R"]), t=np.asarray(r["t"]), n=int(r["n"]),
            engine=str(r["engine"]))
    p, q = _to_coords(P), _to_coords(Q)
    if len(p) != len(q):
        raise ValueError(f"length mismatch: {len(p)} vs {len(q)}")
    if HAS_CUDA and len(p) >= 3:
        try:
            r = _native.kabsch_rmsd_cuda(p, q)
        except Exception:
            r = _native.kabsch_rmsd_cpu(p, q)  # сбой CUDA → CPU, тег engine сообщает какой | CUDA 失败 → CPU，engine 标签标明
        return AlignmentResult(
            rmsd=float(r["rmsd"]), tm_score=float(r["tm_score"]),
            R=np.asarray(r["R"]), t=np.asarray(r["t"]), n=int(r["n"]),
            engine=str(r["engine"]))
    r = _native.kabsch_rmsd_cpu(p, q)
    return AlignmentResult(
        rmsd=float(r["rmsd"]), tm_score=float(r["tm_score"]),
        R=np.asarray(r["R"]), t=np.asarray(r["t"]), n=int(r["n"]),
        engine=str(r["engine"]))


def batched_rmsd(P, Q, use_gpu: bool = True) -> np.ndarray:
    """Pairwise RMSD over B pairs: P, Q of shape [B, N, 3]. Returns [B] float64.

    Device tensors (torch/cupy, float64, CUDA) are passed to the GPU by
    pointer — no host copy. Host arrays go over PCIe (the copy cost is real
    and part of the honest benchmark).
    """
    if use_gpu and HAS_CUDA and _is_cuda_tensor(P) and _is_cuda_tensor(Q):
        try:
            return np.asarray(_native.batched_rmsd_cuda(P, Q))
        except Exception:
            pass  # проваливаемся в путь через хост ниже | 继续走下方的主机路径
    p = np.ascontiguousarray(np.asarray(P, dtype=np.float64))
    q = np.ascontiguousarray(np.asarray(Q, dtype=np.float64))
    if p.ndim != 3 or p.shape[2] != 3:
        raise ValueError(f"expected [B,N,3], got {p.shape}")
    if p.shape != q.shape:
        raise ValueError(f"shape mismatch: {p.shape} vs {q.shape}")
    if use_gpu and HAS_CUDA:
        try:
            return np.asarray(_native.batched_rmsd_cuda(p, q))
        except Exception:
            pass
    return np.asarray(_native.batched_rmsd_cpu(p, q))


def rmsd(P, Q) -> float:
    """Single-pair RMSD (fused path)."""
    return float(kabsch(P, Q).rmsd)


__all__ = [
    "AlignmentResult", "HAS_CUDA", "kabsch", "batched_rmsd", "rmsd",
]