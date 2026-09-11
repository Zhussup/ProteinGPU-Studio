"""PDB helpers: B-factor rewriting and light parsing (Biopython-free fast path)."""
from __future__ import annotations

import numpy as np


def set_b_factors(pdb_text: str, plddt: np.ndarray) -> str:
    """Overwrite the B-factor column with per-residue pLDDT (scaled 0-100)."""
    out = []
    res_seen: dict[tuple, int] = {}
    for line in pdb_text.splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            key = (line[21], line[22:26].strip())
            idx = res_seen.setdefault(key, len(res_seen))
            if idx < len(plddt):
                line = f"{line[:60]}{plddt[idx]:6.2f}{line[66:]}"
        out.append(line)
    return "\n".join(out) + "\n"


def parse_ca_coords(pdb_text: str) -> np.ndarray:
    """[N, 3] CA coordinates (first model, any chain — single-chain pipeline)."""
    ca = [
        [float(l[30:38]), float(l[38:46]), float(l[46:54])]
        for l in pdb_text.splitlines()
        if l.startswith("ATOM  ") and l[12:16].strip() == "CA"
    ]
    if not ca:
        raise ValueError("no CA atoms in PDB text")
    return np.asarray(ca, dtype=np.float64)


def parse_plddt(pdb_text: str) -> np.ndarray:
    """Per-residue pLDDT from B-factor column (one value per residue)."""
    vals, seen = [], set()
    for l in pdb_text.splitlines():
        if l.startswith("ATOM  ") and l[12:16].strip() == "CA":
            key = (l[21], l[22:26].strip())
            if key not in seen:
                seen.add(key)
                vals.append(float(l[60:66]))
    return np.asarray(vals, dtype=np.float64)