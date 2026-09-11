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
    # Curated research proteins (UniProt-verified sequences, data/examples/).
    {
        "id": "kras-g12d", "name": "KRAS G12D",
        "sequence": "MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHHYREQIKRVKDSEDVPMVLVGNKCDLPSRTVDTKQAQDLARSYGIPFIETSAKTRQRVEDAFYTLVREIRQYRLKKISKEEKTPGCVKIKKCIIM",
        "position": 12, "mutant_aa": "D",
        "description": "Онкоген 189 aa; G12D блокирует гидролиз GTP — 25% всех опухолей",
    },
    {
        "id": "p53-r82h", "name": "p53 R82H (R175H)",
        "sequence": "SSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKK",
        "position": 82, "mutant_aa": "H",
        "description": "ДНК-связывающий домен p53 (94-292), нумерация фрагмента: R82=полноразмерный R175 — структурная мутация, разрушает фолд",
    },
    {
        "id": "hbb-e6v", "name": "β-гемоглобин E6V",
        "sequence": "VHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH",
        "position": 6, "mutant_aa": "V",
        "description": "Серповидноклеточная анемия: Glu6→Val создаёт гидрофобный бугорок на поверхности",
    },
    {
        "id": "lyz-i56t", "name": "Лизоцим I56T",
        "sequence": "KVFERCELARTLKRLGMDGYRGISLANWMCLAKWESGYNTRATNYNAGDRSTDYGIFQINSRYWCNDGKTPGAVNACHLSCSALLQDNIADAVACAKRVVRDPQGIRAWVAWRNRCQNRDVRQYVQGCGV",
        "position": 56, "mutant_aa": "T",
        "description": "Наследственный амилоидоз: I56T и D67H дестабилизируют фолд",
    },
    {
        "id": "trpcage-w6f", "name": "Trp-cage W6F",
        "sequence": "DAYAQWLKDGGPSSGRPPPS",
        "position": 6, "mutant_aa": "F",
        "description": "Мини-белок 20 aa (1L2Y); W6F теряет индол гидрофобного ядра — самый быстрый прогон",
    },
    {
        "id": "abeta-e22g", "name": "Aβ42 E22G",
        "sequence": "DAEFRHDSGYEVHHQKLVFFAEDVGSNKGAIIGLMVGGVVIA",
        "position": 22, "mutant_aa": "G",
        "description": "Пепел Альцгеймера, «арктическая» мутация; быстрый прогон (~10 с)",
    },
    {
        "id": "asyn-a53t", "name": "α-синуклеин A53T",
        "sequence": "MDVFMKGLSKAKEGVVAAAEKTKQGVAEAAGKTKEGVLYVGSKTKEGVVHGVATVAEKTKEQVTNVGGAVVTGVTAVAQKTVEGAGSIAAATGFVKKDQLGKNEEGAPQEGILEDMPVDPDNEAYEMPSEEGYQDYEPEA",
        "position": 53, "mutant_aa": "T",
        "description": "Болезнь Паркинсона; белок в природе неупорядочен — честная ловушка для модели",
    },
    {
        "id": "gfp-s65t", "name": "GFP S65T",
        "sequence": "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTFSYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITHGMDELYK",
        "position": 65, "mutant_aa": "T",
        "description": "Хромофор EGFP; кавет: хромофор — пост-трансляционная модификация, невидимая модели",
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