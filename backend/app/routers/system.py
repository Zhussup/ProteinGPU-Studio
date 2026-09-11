"""System endpoints: health, GPU state, demo presets."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

router = APIRouter(prefix="/api/v1", tags=["system"])

# Demo presets from the plan: literature-motivated ubiquitin mutations.
UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")

PRESETS = [
    {
        "id": "ubiq-wt", "name": "Убиквитин (WT)", "sequence": UBIQ,
        "description": "76 aa, контрольный белок",
    },
    {
        "id": "ubiq-i44a", "name": "I44A — гидрофобное пятно",
        "sequence": UBIQ, "position": 44, "mutant_aa": "A",
        "description": "Ile44 в гидрофобном пятне убиквитина; умеренный локальный эффект",
    },
    {
        "id": "ubiq-i3l", "name": "I3L — консервативная замена",
        "sequence": UBIQ, "position": 3, "mutant_aa": "L",
        "description": "Ile→Leu; ожидание RMSD < 1 Å (стабильна)",
    },
    {
        "id": "ubiq-p19g", "name": "P19G — пролин в петле",
        "sequence": UBIQ, "position": 19, "mutant_aa": "G",
        "description": "Pro19 → Gly теряет жёсткий цикл; ожидание RMSD ≥ 2 Å (критично)",
    },
]


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ProteinGPU-Studio"}


@router.get("/system/gpu")
def gpu() -> dict:
    torch = _try_torch()
    if torch is None or not torch.cuda.is_available():
        return {"available": False, "reason": "torch/CUDA unavailable — dummy model"}
    free, total = torch.cuda.mem_get_info()
    return {
        "available": True,
        "name": torch.cuda.get_device_name(0),
        "capability": ".".join(map(str, torch.cuda.get_device_capability(0))),
        "vram_total_mb": round(total / 1e6, 1),
        "vram_free_mb": round(free / 1e6, 1),
    }


@router.get("/system/presets")
def presets() -> dict:
    return {"presets": PRESETS}


@router.get("/system/profiles")
def profiles() -> dict:
    """Which inference profiles are usable right now."""
    torch = _try_torch()
    cuda = torch is not None and torch.cuda.is_available()
    has_weights = _weights_present()
    return {
        "profiles": [
            {"id": "fp32-gpu", "available": cuda and has_weights},
            {"id": "fp16-gpu", "available": cuda and has_weights},
            {"id": "compiled", "available": cuda and has_weights},
            {"id": "cpu", "available": cuda and has_weights},
            {"id": "dummy", "available": True},
        ],
        "active_model": _active_model_name(),
    }


def _try_torch():
    try:
        import torch
        return torch
    except ImportError:
        return None


def _weights_present() -> bool:
    import os
    from pathlib import Path
    p = Path(os.environ.get("OMEGAFOLD_WEIGHTS",
                            os.path.expanduser("~/.cache/omegafold_ckpt/model.pt")))
    return p.exists()


def _active_model_name() -> str:
    from ..services.folding_service import get_folding_service
    return get_folding_service().model_name