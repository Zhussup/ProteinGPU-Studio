"""Inference profiles for benchmarking (plan: 4 profiles).

  1. fp32-gpu    — OmegaFold fp32 on CUDA (TF32 matmul allowed)
  2. fp16-gpu    — weights.half(), CUDA
  3. compiled    — fp16 + torch.compile (best effort; result logged even if
                   compile fails on this torch/python combo)
  4. cpu         — fp32 on CPU (fallback reference)

Each profile is (name, apply_fn) applied to a RESIDENT model instance, so
latency measures inference, not disk I/O.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def clear_gpu() -> dict[str, float]:
    """Drop CUDA cache; report free VRAM before/after."""
    import torch
    before = torch.cuda.mem_get_info()[0] / 1e6 if torch.cuda.is_available() else -1
    torch.cuda.empty_cache()
    after = torch.cuda.mem_get_info()[0] / 1e6 if torch.cuda.is_available() else -1
    return {"free_before_mb": before, "free_after_mb": after}


def to_fp16(model) -> None:
    if hasattr(model, "to_fp16"):
        model.to_fp16()
    elif hasattr(model, "_model"):
        model._model.half()


def to_fp32(model) -> None:
    if hasattr(model, "to_fp32"):
        model.to_fp32()
    elif hasattr(model, "_model"):
        model._model.float()


def to_compiled(model, seq_for_warmup: str | None = None) -> str:
    """torch.compile the inner model. Returns 'ok' | reason string."""
    try:
        import torch
        inner = getattr(model, "_model", model)
        inner_c = torch.compile(inner)
        model._model = inner_c
        if seq_for_warmup:
            t0 = time.perf_counter()
            model.predict(seq_for_warmup)
            logger.info("torch.compile warmup took %.1fs", time.perf_counter() - t0)
        return "ok"
    except Exception as exc:
        logger.warning("torch.compile failed: %s", exc)
        return f"failed: {exc}"


PROFILES = ("fp32-gpu", "fp16-gpu", "compiled", "cpu")