"""Base types for the folding layer.

A FoldingModel turns a FASTA sequence into 3D coordinates + per-residue
confidence. Every implementation returns the SAME PredictResult so the
backend, benchmarks and tests are model-agnostic (OmegaFold vs dummy vs
fallback ESMFold behind an env flag).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np

AA_RE = "ACDEFGHIKLMNPQRSTVWY"


@dataclass
class PredictResult:
    """Output of one folding call.

    coords_backbone: [N, 4, 3] N, CA, C, O (float32/float64, angstroms)
    coords_ca:       [N, 3] view/convenience copy of CA atoms
    plddt:           [N] per-residue confidence in [0, 100]
    pdb_text:        full ATOM-record PDB string (pLDDT in B-factor column)
    seq:             the folded sequence
    """
    coords_backbone: np.ndarray
    plddt: np.ndarray
    pdb_text: str
    seq: str
    coords_ca: np.ndarray = field(init=False)
    # Filled by implementations when known (OmegaFold overall confidence).
    plddt_mean: float = field(default=float("nan"))

    def __post_init__(self) -> None:
        self.coords_ca = np.ascontiguousarray(self.coords_backbone[:, 1, :], dtype=np.float64)


def ca_coords_from_pdb(pdb_text: str) -> np.ndarray:
    """Extract CA coordinates [N, 3] from a PDB string (first model, chain A)."""
    ca = []
    for line in pdb_text.splitlines():
        if line.startswith(("ATOM  ", "HETATM")) and line[12:16].strip() == "CA":
            ca.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
    if not ca:
        raise ValueError("PDB text contains no CA atoms")
    return np.asarray(ca, dtype=np.float64)


def validate_sequence(seq: str, min_len: int = 10, max_len: int = 600) -> str:
    """Uppercase, strip whitespace, check alphabet and length. Raises ValueError."""
    s = "".join(seq.split()).upper()
    if not (min_len <= len(s) <= max_len):
        raise ValueError(f"sequence length must be {min_len}..{max_len}, got {len(s)}")
    bad = set(s) - set(AA_RE)
    if bad:
        raise ValueError(f"non-standard residues: {''.join(sorted(bad))}")
    return s


@runtime_checkable
class FoldingModel(Protocol):
    """Anything that can fold a sequence into a PredictResult."""

    name: str
    device: str

    def predict(self, seq: str) -> PredictResult: ...

    def close(self) -> None:
        """Release weights/VRAM (no-op for stateless models)."""
        ...


def mutant_sequence(seq: str, pos: int, mut_aa: str) -> str:
    """1-based point mutation: pos in 1..len(seq), mut_aa one letter.

    Returns the mutant string. Raises ValueError on out-of-range position.
    """
    if not (1 <= pos <= len(seq)):
        raise ValueError(f"position {pos} out of range 1..{len(seq)}")
    mut_aa = mut_aa.upper()
    if mut_aa not in AA_RE:
        raise ValueError(f"bad mutant residue {mut_aa!r}")
    return seq[: pos - 1] + mut_aa + seq[pos:]


def local_window(pos: int, n: int, radius: int = 10) -> tuple[int, int]:
    """Inclusive [start, end) index window of ±radius residues around pos (1-based)."""
    return max(0, pos - 1 - radius), min(n, pos + radius)


def tm_d0(length: int) -> float:
    """TM-score normalization d0 = 1.24 (L-15)^(1/3) - 1.8, floored at 0.5."""
    if length <= 15:
        return 0.5
    return max(0.5, 1.24 * math.cbrt(length - 15) - 1.8)