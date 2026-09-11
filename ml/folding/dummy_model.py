"""Deterministic fake folder for backend/frontend development without GPU.

Produces geometrically valid, sequence-dependent structures: an idealized
alpha-helix whose phase/geometry is perturbed by a hash of the sequence, so
WT vs mutant structures differ in a controlled, reproducible way. pLDDT is a
smooth profile (higher mid-chain). Perfect for UI wiring, job lifecycle and
e2e tests; NEVER produces numbers for the report.
"""
from __future__ import annotations

import hashlib
import io
import os

import numpy as np

from .base import PredictResult, validate_sequence

THREE = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN",
    "E": "GLU", "G": "GLY", "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS",
    "M": "MET", "F": "PHE", "P": "PRO", "S": "SER", "T": "THR", "W": "TRP",
    "Y": "TYR", "V": "VAL",
}
BB_NAMES = ("N", "CA", "C", "O")


class DummyModel:
    """Fast, deterministic, dependency-free stand-in for OmegaFold."""

    def __init__(self, device: str = "cpu"):
        self.name = "dummy"
        self.device = device

    def predict(self, seq: str) -> PredictResult:
        seq = validate_sequence(seq)
        n = len(seq)
        h = hashlib.sha256(seq.encode()).digest()
        phase = int.from_bytes(h[:4], "big") / 2**32 * 2 * np.pi
        twist = 1.8 + (h[4] % 5) * 0.01          # rad/residue ≈ 100° alpha helix
        rise = 1.5 + (h[5] % 4) * 0.005          # Å/residue
        radius = 2.3 + (h[6] % 3) * 0.02
        bend = (h[7] % 100) / 100 * 0.002        # slow curvature along the axis

        t = np.arange(n, dtype=np.float64)
        ca = np.stack([
            radius * np.cos(twist * t + phase) + bend * t**2 * 0.01,
            radius * np.sin(twist * t + phase),
            rise * t,
        ], axis=1)
        # N/CA/C/O offsets in a local frame — geometry is plausible, not exact.
        tang = np.gradient(ca, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
        side = np.cross(tang, np.array([0.0, 0.0, 1.0]))
        side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-9
        bb = np.stack([
            ca - 1.5 * tang + 1.0 * side,
            ca,
            ca + 1.5 * tang + 0.5 * side,
            ca + 2.4 * tang,
        ], axis=1)  # [N, 4, 3]

        # pLDDT: soft profile — dips near termini, sequence-dependent ripples.
        x = t / max(n - 1, 1)
        ripple = 8 * np.sin(6 * np.pi * x + phase)
        plddt = np.clip(88 * (1 - x * (1 - x)) * (1 - 0.5 * x * (1 - x)) + ripple, 35, 97)

        pdb_text = self._to_pdb(bb, seq, plddt)
        return PredictResult(
            coords_backbone=bb, plddt=plddt, pdb_text=pdb_text, seq=seq,
            plddt_mean=float(plddt.mean()),
        )

    @staticmethod
    def _to_pdb(bb: np.ndarray, seq: str, plddt: np.ndarray) -> str:
        buf = io.StringIO()
        for i, aa in enumerate(seq):
            for j, name in enumerate(BB_NAMES):
                x, y, z = bb[i, j]
                buf.write(
                    f"ATOM  {i*4+j+1:5d}  {name:<3s} {THREE[aa]:>3s} A{i+1:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00{plddt[i]:6.2f}           {name[0]:>2s}\n"
                )
        buf.write("TER\nEND\n")
        return buf.getvalue()

    def close(self) -> None:
        pass


def get_model(profile: str = "auto"):
    """Factory used by backend + spike scripts.

    profiles: auto (real if weights+CUDA, else dummy) | omegafold | dummy |
    fp32-gpu | fp16-gpu (autocast) | cpu
    """
    if profile == "dummy":
        return DummyModel()
    if profile == "omegafold":
        from .omegafold_model import OmegaFoldModel
        return OmegaFoldModel()
    if profile in ("fp32-gpu", "fp16-gpu", "cpu"):
        import torch
        from .omegafold_model import weights_path
        if not (torch.cuda.is_available() and weights_path().exists()):
            return DummyModel()
        from .omegafold_model import OmegaFoldModel
        if profile == "fp16-gpu":
            return OmegaFoldModel(half=True)      # autocast, weights stay fp32
        if profile == "cpu":
            return OmegaFoldModel(device="cpu")
        return OmegaFoldModel()
    # auto
    try:
        import torch
        from .omegafold_model import weights_path
        if torch.cuda.is_available() and weights_path().exists():
            from .omegafold_model import OmegaFoldModel
            return OmegaFoldModel()
    except Exception as exc:  # pragma: no cover - depends on env
        os.environ.setdefault("FOLDING_FALLBACK_REASON", str(exc))
    return DummyModel()