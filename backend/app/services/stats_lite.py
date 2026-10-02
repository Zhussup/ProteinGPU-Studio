"""Small pure-math statistics helpers (no scipy dependency).

The DMS-fitness series are rank-correlated, and ranking data is full of
ties — so Spearman here uses AVERAGE ranks (ties share the mean rank),
the textbook definition, not the naive "argsort twice" shortcut that
miscalculates every tied series. Confidence intervals are percentile
bootstrap (seeded, deterministic). Everything returns Python floats or
None — job.result is JSON, so numpy never leaks inside.
"""
from __future__ import annotations

import numpy as np


def avg_ranks(values) -> np.ndarray:
    """Average ranks, 1-based, ties share the mean of their rank block."""
    a = np.asarray(values, dtype=np.float64)
    order = np.argsort(a, kind="stable")
    ranks = np.empty(a.shape[0], dtype=np.float64)
    sorted_vals = a[order]
    i = 0
    while i < a.shape[0]:
        j = i
        while j + 1 < a.shape[0] and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        rank = (i + j) / 2.0 + 1.0  # среднее блоков рангов i..j (1-based)
        ranks[order[i:j + 1]] = rank
        i = j + 1
    return ranks


def spearman(x, y) -> float | None:
    """Spearman rho, or None when not computable (n<3 or a constant side)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size != y.size or x.size < 3:
        return None
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return None  # константная сторона: корреляция не определена
    rx, ry = avg_ranks(x), avg_ranks(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    if denom == 0:
        return None
    return float((rx * ry).sum() / denom)


def spearman_ci(x, y, n_boot: int = 200, seed: int = 0) -> tuple[float, float] | None:
    """Percentile bootstrap CI for Spearman rho (seeded, deterministic)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = x.size
    if n < 4:
        return None
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        rho = spearman(x[idx], y[idx])
        if rho is not None:
            boots.append(rho)
    if len(boots) < n_boot // 2:
        return None
    return (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))


def stride_downsample(rows: list, cap: int = 800) -> list:
    """Keep ~cap rows, evenly by index (order-preserving)."""
    if len(rows) <= cap or cap < 2:
        return list(rows)
    step = (len(rows) - 1) / (cap - 1)
    return [rows[round(i * step)] for i in range(cap)]