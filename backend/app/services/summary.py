"""Template-based natural-language summary for a mutation run.

No LLM: each metric is mapped to a phrase through a small band table, and the
summary is the composition of those fragments. Adding a metric means adding a
(bands, phrases) table entry — not another branch.
"""
from __future__ import annotations

from ..schemas import RmsdResult

# local RMSD bands (same thresholds as interpret_rmsd: 1.0 / 2.0 Å)
_LOCAL = (
    "замена поглощена структурой без локальной перестройки",
    "наблюдается умеренная локальная перестройка конформации",
    "локальная конформация в районе мутации существенно изменена",
)
_LOCAL_NOTE = (
    " (на почти детерминированной single-sequence модели это ожидаемо — "
    "оценивайте мутации сравнением между собой, а не абсолютным порогом)",
    "",
    "",
)
# TM-score bands: <0.5 / 0.5–0.9 / >0.9
_TM = (
    "глобальная укладка изменена — цепи сворачиваются по-разному",
    "глобальная укладка в целом сохранена, но деформирована",
    "глобальная укладка сохранена",
)
# ΔpLDDT bands: ≤−1 / −1..+1 / ≥+1
_PLDDT = (
    "модель стала менее уверена в структуре мутанта — мутация попала в структурно значимый регион",
    "уверенность модели практически не изменилась",
    "модель стала увереннее в структуре мутанта",
)
# interpretation → final phrase
_VERDICT = {
    "stable": "структура стабильна: эффект мутации в пределах шума модели",
    "moderate": "эффект мутации умеренный: стоит прогнать соседние мутации для сравнения",
    "critical": "критическое изменение конформации в районе мутации",
}


def make_summary(r: RmsdResult, wt_aa: str, position: int, mut_aa: str) -> str:
    """Compose a human-readable verdict from the metric bands."""
    lr = r.local_rmsd
    lb = 0 if lr < 1.0 else (1 if lr < 2.0 else 2)

    if r.tm_score > 0.9:
        tb = 2
    elif r.tm_score >= 0.5:
        tb = 1
    else:
        tb = 0

    d = r.plddt_mut - r.plddt_wt
    if d <= -1.0:
        pb = 0
    elif d >= 1.0:
        pb = 2
    else:
        pb = 1

    parts = [
        f"Мутация {wt_aa}{position}{mut_aa}:",
        f"локальный RMSD {lr:.2f} Å (окно {r.local_window[0]}–{r.local_window[1]}) — "
        f"{_LOCAL[lb]}{_LOCAL_NOTE[lb]}",
        f"TM-score {r.tm_score:.3f} — {_TM[tb]}",
        f"ΔpLDDT {d:+.1f} — {_PLDDT[pb]}",
        f"Итог: {_VERDICT[r.interpretation]}.",
    ]
    return " ".join(parts)