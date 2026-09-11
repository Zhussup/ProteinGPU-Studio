"""Alignment service: Kabsch via the hpc_core native extension.

Mandatory numpy fallback (plan requirement) — if the extension is missing or
fails, the pure-python path below produces the same numbers, tagged engine
"numpy". Every result carries its engine tag.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "hpc_core" / "python"), str(REPO / "ml")):
    if p not in sys.path:
        sys.path.insert(0, p)


@dataclass(frozen=True)
class AlignOutput:
    global_rmsd: float
    local_rmsd: float
    local_window: tuple[int, int]  # 1-based inclusive
    tm_score: float
    engine: str


def _kabsch_numpy(P: np.ndarray, Q: np.ndarray) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Reference SVD Kabsch (column-vector convention q = R p + t)."""
    Pc, Qc = P - P.mean(0), Q - Q.mean(0)
    U, S, Wt = np.linalg.svd(Pc.T @ Qc)
    d = np.sign(np.linalg.det(U @ Wt))
    R = (U @ np.diag([1.0, 1.0, d]) @ Wt).T
    diff = Pc @ R.T - Qc
    rmsd = float(np.sqrt((diff ** 2).sum() / len(P)))
    t = Q.mean(0) - R @ P.mean(0)
    return rmsd, float(S.sum()), R, t


def _tm_score(P: np.ndarray, Q: np.ndarray, R: np.ndarray, t: np.ndarray) -> float:
    n = len(P)
    if n <= 15:
        return 0.0
    d0 = max(0.5, 1.24 * np.cbrt(n - 15) - 1.8)
    diff = (R @ P.T).T + t - Q
    dist2 = (diff ** 2).sum(1)
    return float((1.0 / (1.0 + dist2 / (d0 * d0))).sum() / n)


def align_pair(wt_ca: np.ndarray, mut_ca: np.ndarray, position: int,
               radius: int = 10) -> AlignOutput:
    """Align mutant CA trace onto WT; global + local (±radius) RMSD + TM.

    `position` is the 1-based mutation site. Direction matters for reporting:
    we superpose the mutant onto WT so RMSD is expressed in the WT frame.
    """
    wt = np.ascontiguousarray(wt_ca, dtype=np.float64)
    mut = np.ascontiguousarray(mut_ca, dtype=np.float64)
    if wt.shape != mut.shape or wt.ndim != 2 or wt.shape[1] != 3:
        raise ValueError(f"bad shapes {wt.shape} vs {mut.shape}")
    if not np.isfinite(wt).all() or not np.isfinite(mut).all():
        raise ValueError("coordinates contain NaN/inf")

    engine = "numpy"
    g_rmsd = l_rmsd = tm = None
    try:
        import hpc_core  # native extension, CUDA preferred inside
        lo, hi = 0, len(wt)
        full = hpc_core.kabsch(mut, wt)
        g_rmsd, tm, engine = full.rmsd, full.tm_score, full.engine
        start = max(0, position - 1 - radius)
        end = min(len(wt), position + radius)
        if end - start >= 3:
            loc = hpc_core.kabsch(mut[start:end], wt[start:end])
            l_rmsd = loc.rmsd
        else:
            l_rmsd = g_rmsd
    except ImportError:
        pass

    if g_rmsd is None:  # numpy fallback
        g_rmsd, _, R, t = _kabsch_numpy(mut, wt)
        tm = _tm_score(mut, wt, R, t)
        start = max(0, position - 1 - radius)
        end = min(len(wt), position + radius)
        l_rmsd = _kabsch_numpy(mut[start:end], wt[start:end])[0] if end - start >= 3 else g_rmsd

    return AlignOutput(
        global_rmsd=g_rmsd, local_rmsd=l_rmsd,
        local_window=(start + 1, end), tm_score=tm, engine=engine,
    )


def write_aligned_pdb(mut_pdb_text: str, R: np.ndarray, t: np.ndarray) -> str:
    """Apply rigid transform (R, t) to every ATOM coordinate in a PDB string.

    The viewer loads this pre-aligned file — no client-side math.
    """
    R = np.asarray(R, dtype=np.float64)
    t = np.asarray(t, dtype=np.float64)
    out = []
    for line in mut_pdb_text.splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            xyz = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
            new = R @ xyz + t
            out.append(f"{line[:30]}{new[0]:8.3f}{new[1]:8.3f}{new[2]:8.3f}{line[54:]}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"