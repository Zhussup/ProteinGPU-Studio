"""Telemetry: timing + memory sampling around model calls.

Benchmarks must separate warmup from measured inference (first call compiles
kernels, allocates caches) and report median + IQR — a 60W laptop GPU
throttles, so single-shot numbers are meaningless.
"""
from __future__ import annotations

import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TelemetrySample:
    """One measured call."""
    wall_s: float
    max_vram_mb: float | None = None   # torch.cuda.max_memory_allocated delta
    max_rss_mb: float | None = None    # process RSS peak during the call
    meta: dict[str, Any] = field(default_factory=dict)


class TelemetrySampler:
    """Measures wall time + VRAM/RSS peaks for each `run()` invocation."""

    def __init__(self) -> None:
        self.samples: list[TelemetrySample] = []
        self._baseline_vram = self._current_vram()
        self._baseline_rss = self._current_rss()

    # -- context manager ----------------------------------------------------
    @contextmanager
    def measure(self, **meta: Any):
        import threading

        torch = _try_import_torch()
        peak_vram = [self._current_vram()]
        stop = threading.Event()

        def watch_rss():
            peak = self._current_rss()
            while not stop.is_set():
                r = self._current_rss()
                if r > peak:
                    peak = r
                stop.wait(0.02)  # 20 ms as per the plan
            return peak

        watcher = None
        if self._current_rss() > 0:
            watcher = threading.Thread(target=watch_rss, daemon=True)
        if torch is not None and torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            peak_vram[0] = torch.cuda.max_memory_allocated() / 1e6

        t0 = time.perf_counter()
        if watcher is not None:
            watcher.start()
        try:
            yield
        finally:
            wall = time.perf_counter() - t0
            stop.set()
            rss_peak = self._current_rss()
            if torch is not None and torch.cuda.is_available():
                peak_vram[0] = max(peak_vram[0], torch.cuda.max_memory_allocated() / 1e6)
            self.samples.append(TelemetrySample(
                wall_s=wall,
                max_vram_mb=peak_vram[0] if peak_vram[0] > 0 else None,
                max_rss_mb=rss_peak if rss_peak > 0 else None,
                meta=meta,
            ))

    # -- summaries ------------------------------------------------------------
    def summary(self, drop_warmup: int = 2) -> dict[str, Any]:
        """median + IQR of wall time (first `drop_warmup` samples discarded)."""
        s = self.samples[drop_warmup:] if len(self.samples) > drop_warmup else self.samples
        if not s:
            return {"n": 0}
        walls = [x.wall_s for x in s]
        walls_sorted = sorted(walls)
        q1 = walls_sorted[max(0, int(0.25 * len(walls_sorted)))]
        q3 = walls_sorted[min(len(walls_sorted) - 1, int(0.75 * len(walls_sorted)))]
        vrams = [x.max_vram_mb for x in s if x.max_vram_mb is not None]
        rss = [x.max_rss_mb for x in s if x.max_rss_mb is not None]
        return {
            "n": len(walls),
            "wall_median_s": statistics.median(walls),
            "wall_iqr_s": q3 - q1,
            "wall_min_s": walls_sorted[0],
            "wall_max_s": walls_sorted[-1],
            "vram_median_mb": statistics.median(vrams) if vrams else None,
            "rss_median_mb": statistics.median(rss) if rss else None,
        }

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _current_vram() -> float:
        torch = _try_import_torch()
        if torch is None or not torch.cuda.is_available():
            return 0.0
        try:
            return torch.cuda.memory_allocated() / 1e6
        except Exception:
            return 0.0

    @staticmethod
    def _current_rss() -> float:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KiB→MB
        except Exception:
            return 0.0


def _try_import_torch():
    try:
        import torch
        return torch
    except ImportError:
        return None