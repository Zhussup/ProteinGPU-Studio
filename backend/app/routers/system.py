"""System endpoints: health, GPU state, demo presets."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ..services.strings import GPU_REASON, norm_lang  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["system"])

# Демо-пресеты из плана: мутации убиквитина, мотивированные литературой.
# name/description — словари по языкам; эндпоинт выбирает язык по
# запрошенному ?lang= (ru — источник истины).
# 计划中的演示预设：有文献依据的泛素突变。
# name/description 是按语言的字典；端点按请求的 ?lang= 取对应语言（ru 为基准）。
UBIQ = ("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")

PRESETS = [
    {
        "id": "ubiq-wt",
        "name": {"ru": "Убиквитин (WT)", "en": "Ubiquitin (WT)", "zh": "泛素（WT）"},
        "sequence": UBIQ,
        "description": {
            "ru": "76 aa, контрольный белок",
            "en": "76 aa, control protein",
            "zh": "76 aa，对照蛋白",
        },
    },
    {
        "id": "ubiq-i44a",
        "name": {"ru": "I44A — гидрофобное пятно", "en": "I44A — hydrophobic patch",
                 "zh": "I44A —— 疏水斑"},
        "sequence": UBIQ, "position": 44, "mutant_aa": "A",
        "description": {
            "ru": "Ile44 в гидрофобном пятне убиквитина; умеренный локальный эффект",
            "en": "Ile44 in ubiquitin's hydrophobic patch; moderate local effect",
            "zh": "Ile44 位于泛素的疏水斑；局部效应中等",
        },
    },
    {
        "id": "ubiq-i3l",
        "name": {"ru": "I3L — консервативная замена", "en": "I3L — conservative substitution",
                 "zh": "I3L —— 保守替换"},
        "sequence": UBIQ, "position": 3, "mutant_aa": "L",
        "description": {
            "ru": "Ile→Leu; ожидание RMSD < 1 Å (стабильна)",
            "en": "Ile→Leu; expected RMSD < 1 Å (stable)",
            "zh": "Ile→Leu；预期 RMSD < 1 Å（稳定）",
        },
    },
    {
        "id": "ubiq-p19g",
        "name": {"ru": "P19G — пролин в петле", "en": "P19G — loop proline",
                 "zh": "P19G —— 环区脯氨酸"},
        "sequence": UBIQ, "position": 19, "mutant_aa": "G",
        "description": {
            "ru": "Pro19 → Gly теряет жёсткий цикл; ожидание RMSD ≥ 2 Å (критично)",
            "en": "Pro19→Gly loses the rigid ring; expected RMSD ≥ 2 Å (critical)",
            "zh": "Pro19→Gly 丢失刚性环；预期 RMSD ≥ 2 Å（严重）",
        },
    },
    # Отобранные исследовательские белки (последовательности сверены с UniProt, data/examples/).
    # 精选的研究蛋白（序列经 UniProt 校验，见 data/examples/）。
    {
        "id": "kras-g12d", "name": {"ru": "KRAS G12D", "en": "KRAS G12D", "zh": "KRAS G12D"},
        "sequence": "MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHHYREQIKRVKDSEDVPMVLVGNKCDLPSRTVDTKQAQDLARSYGIPFIETSAKTRQRVEDAFYTLVREIRQYRLKKISKEEKTPGCVKIKKCIIM",
        "position": 12, "mutant_aa": "D",
        "description": {
            "ru": "Онкоген 189 aa; G12D блокирует гидролиз GTP — 25% всех опухолей",
            "en": "Oncogene, 189 aa; G12D blocks GTP hydrolysis — 25% of all tumors",
            "zh": "癌基因，189 aa；G12D 阻断 GTP 水解——约占所有肿瘤的 25%",
        },
    },
    {
        "id": "p53-r82h",
        "name": {"ru": "p53 R82H (R175H)", "en": "p53 R82H (R175H)", "zh": "p53 R82H（R175H）"},
        "sequence": "SSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKK",
        "position": 82, "mutant_aa": "H",
        "description": {
            "ru": "ДНК-связывающий домен p53 (94-292), нумерация фрагмента: R82=полноразмерный R175 — структурная мутация, разрушает фолд",
            "en": "p53 DNA-binding domain (94–292), fragment numbering: R82 = full-length R175 — a structural mutation that breaks the fold",
            "zh": "p53 DNA 结合结构域（94–292），片段编号：R82 = 全长 R175——破坏折叠的结构性突变",
        },
    },
    {
        "id": "hbb-e6v",
        "name": {"ru": "β-гемоглобин E6V", "en": "β-hemoglobin E6V", "zh": "β-血红蛋白 E6V"},
        "sequence": "VHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH",
        "position": 6, "mutant_aa": "V",
        "description": {
            "ru": "Серповидноклеточная анемия: Glu6→Val создаёт гидрофобный бугорок на поверхности",
            "en": "Sickle-cell anemia: Glu6→Val creates a hydrophobic knob on the surface",
            "zh": "镰状细胞贫血：Glu6→Val 在表面形成疏水凸起",
        },
    },
    {
        "id": "lyz-i56t",
        "name": {"ru": "Лизоцим I56T", "en": "Lysozyme I56T", "zh": "溶菌酶 I56T"},
        "sequence": "KVFERCELARTLKRLGMDGYRGISLANWMCLAKWESGYNTRATNYNAGDRSTDYGIFQINSRYWCNDGKTPGAVNACHLSCSALLQDNIADAVACAKRVVRDPQGIRAWVAWRNRCQNRDVRQYVQGCGV",
        "position": 56, "mutant_aa": "T",
        "description": {
            "ru": "Наследственный амилоидоз: I56T и D67H дестабилизируют фолд",
            "en": "Hereditary amyloidosis: I56T and D67H destabilize the fold",
            "zh": "遗传性淀粉样变：I56T 与 D67H 破坏折叠的稳定性",
        },
    },
    {
        "id": "trpcage-w6f",
        "name": {"ru": "Trp-cage W6F", "en": "Trp-cage W6F", "zh": "Trp-cage W6F"},
        "sequence": "DAYAQWLKDGGPSSGRPPPS",
        "position": 6, "mutant_aa": "F",
        "description": {
            "ru": "Мини-белок 20 aa (1L2Y); W6F теряет индол гидрофобного ядра — самый быстрый прогон",
            "en": "20 aa mini-protein (1L2Y); W6F loses the indole of the hydrophobic core — fastest run",
            "zh": "20 aa 微型蛋白（1L2Y）；W6F 失去疏水核心的吲哚——运行最快",
        },
    },
    {
        "id": "abeta-e22g",
        "name": {"ru": "Aβ42 E22G", "en": "Aβ42 E22G", "zh": "Aβ42 E22G"},
        "sequence": "DAEFRHDSGYEVHHQKLVFFAEDVGSNKGAIIGLMVGGVVIA",
        "position": 22, "mutant_aa": "G",
        "description": {
            "ru": "Пептид Альцгеймера, «арктическая» мутация; быстрый прогон (~10 с)",
            "en": "Alzheimer's peptide, the \"Arctic\" mutation; fast run (~10 s)",
            "zh": "阿尔茨海默病肽段，“北极”突变；运行快（约 10 秒）",
        },
    },
    {
        "id": "asyn-a53t",
        "name": {"ru": "α-синуклеин A53T", "en": "α-synuclein A53T", "zh": "α-突触核蛋白 A53T"},
        "sequence": "MDVFMKGLSKAKEGVVAAAEKTKQGVAEAAGKTKEGVLYVGSKTKEGVVHGVATVAEKTKEQVTNVGGAVVTGVTAVAQKTVEGAGSIAAATGFVKKDQLGKNEEGAPQEGILEDMPVDPDNEAYEMPSEEGYQDYEPEA",
        "position": 53, "mutant_aa": "T",
        "description": {
            "ru": "Болезнь Паркинсона; белок в природе неупорядочен — честная ловушка для модели",
            "en": "Parkinson's disease; the protein is intrinsically disordered — an honest trap for the model",
            "zh": "帕金森病；该蛋白天然无序——对模型的诚实考验",
        },
    },
    {
        "id": "gfp-s65t",
        "name": {"ru": "GFP S65T", "en": "GFP S65T", "zh": "GFP S65T"},
        "sequence": "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTFSYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITHGMDELYK",
        "position": 65, "mutant_aa": "T",
        "description": {
            "ru": "Хромофор EGFP; нюанс: хромофор — пост-трансляционная модификация, невидимая модели",
            "en": "EGFP chromophore; caveat: the chromophore is a post-translational modification invisible to the model",
            "zh": "EGFP 生色团；注意：生色团是翻译后修饰，模型不可见",
        },
    },
]


def _localized_presets(lang: str) -> list[dict]:
    lg = norm_lang(lang)
    out = []
    for p in PRESETS:
        row = dict(p)
        row["name"] = p["name"][lg]
        row["description"] = p["description"][lg]
        out.append(row)
    return out


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ProteinGPU-Studio"}


@router.get("/system/gpu")
def gpu(lang: str = "ru") -> dict:
    torch = _try_torch()
    if torch is None or not torch.cuda.is_available():
        return {"available": False, "reason": GPU_REASON[norm_lang(lang)]}
    free, total = torch.cuda.mem_get_info()
    return {
        "available": True,
        "name": torch.cuda.get_device_name(0),
        "capability": ".".join(map(str, torch.cuda.get_device_capability(0))),
        "vram_total_mb": round(total / 1e6, 1),
        "vram_free_mb": round(free / 1e6, 1),
    }


@router.get("/system/presets")
def presets(lang: str = "ru") -> dict:
    return {"presets": _localized_presets(lang)}


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