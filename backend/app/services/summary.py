"""Template-based natural-language summary for a mutation run.

No LLM: each metric is mapped to a phrase through a small band table, and the
summary is the composition of those fragments. Adding a metric means adding a
(bands, phrases) table entry — not another branch. The frontend's active UI
language arrives as `lang`; ru is the source of truth and stays byte-identical
to the pre-i18n strings (tests assert on them).
"""
from __future__ import annotations

from .strings import norm_lang

from ..schemas import RmsdResult

# band phrases per language: 3 bands each, thresholds fixed by interpret_rmsd
_BANDS: dict[str, dict[str, tuple[str, ...]]] = {
    "ru": {
        # local RMSD bands (same thresholds as interpret_rmsd: 1.0 / 2.0 Å)
        "local": (
            "замена поглощена структурой без локальной перестройки",
            "наблюдается умеренная локальная перестройка конформации",
            "локальная конформация в районе мутации существенно изменена",
        ),
        "local_note": (
            " (на почти детерминированной single-sequence модели это ожидаемо — "
            "оценивайте мутации сравнением между собой, а не абсолютным порогом)",
            "",
            "",
        ),
        # TM-score bands: <0.5 / 0.5–0.9 / >0.9
        "tm": (
            "глобальная укладка изменена — цепи сворачиваются по-разному",
            "глобальная укладка в целом сохранена, но деформирована",
            "глобальная укладка сохранена",
        ),
        # ΔpLDDT bands: ≤−1 / −1..+1 / ≥+1
        "plddt": (
            "модель стала менее уверена в структуре мутанта — мутация попала в структурно значимый регион",
            "уверенность модели практически не изменилась",
            "модель стала увереннее в структуре мутанта",
        ),
    },
    "en": {
        "local": (
            "the substitution is absorbed by the structure with no local rearrangement",
            "a moderate local rearrangement of the conformation is observed",
            "the local conformation near the mutation is substantially altered",
        ),
        "local_note": (
            " (expected on a nearly deterministic single-sequence model — "
            "compare mutations against each other, not against an absolute threshold)",
            "",
            "",
        ),
        "tm": (
            "the global fold is changed — the chains fold differently",
            "the global fold is largely preserved but deformed",
            "the global fold is preserved",
        ),
        "plddt": (
            "the model became less confident in the mutant structure — the mutation hits a structurally important region",
            "model confidence is essentially unchanged",
            "the model became more confident in the mutant structure",
        ),
    },
    "zh": {
        "local": (
            "替换被结构吸收，未引起局部重排",
            "突变位点附近出现中等程度的局部构象重排",
            "突变附近的局部构象发生显著改变",
        ),
        "local_note": (
            "（在近乎确定性的单序列模型上这属于预期——请通过突变之间的相互比较来评估，而不是对照绝对阈值）",
            "",
            "",
        ),
        "tm": (
            "全局折叠被改变——两条链的折叠方式不同",
            "全局折叠总体保留，但发生了形变",
            "全局折叠保留",
        ),
        "plddt": (
            "模型对突变体结构的置信度下降——突变落在了结构上重要的区域",
            "模型置信度基本不变",
            "模型对突变体结构的置信度上升",
        ),
    },
}

# interpretation → final verdict phrase
_VERDICTS: dict[str, dict[str, str]] = {
    "ru": {
        "stable": "структура стабильна: эффект мутации в пределах шума модели",
        "moderate": "эффект мутации умеренный: стоит прогнать соседние мутации для сравнения",
        "critical": "критическое изменение конформации в районе мутации",
    },
    "en": {
        "stable": "the structure is stable: the mutation's effect is within the model's noise",
        "moderate": "the mutation's effect is moderate: it is worth running neighbouring substitutions for comparison",
        "critical": "a critical conformational change near the mutation site",
    },
    "zh": {
        "stable": "结构稳定：突变效应在模型噪声范围内",
        "moderate": "突变效应中等：建议对邻近替换进行扫描比较",
        "critical": "突变位点附近发生了关键性的构象改变",
    },
}

# line templates, one per language; {placeholders} filled in make_summary
_SUMMARY_TPL: dict[str, tuple[str, ...]] = {
    "ru": (
        "Мутация {m}:",
        "локальный RMSD {lr:.2f} Å (окно {a}–{b}) — {local}{note}",
        "TM-score {tm:.3f} — {tm_p}",
        "ΔpLDDT {d:+.1f} — {plddt_p}",
        "Итог: {verdict}.",
    ),
    "en": (
        "Mutation {m}:",
        "local RMSD {lr:.2f} Å (window {a}–{b}) — {local}{note}",
        "TM-score {tm:.3f} — {tm_p}",
        "ΔpLDDT {d:+.1f} — {plddt_p}",
        "Verdict: {verdict}.",
    ),
    "zh": (
        "突变 {m}：",
        "局部 RMSD {lr:.2f} Å（窗口 {a}–{b}）— {local}{note}",
        "TM-score {tm:.3f} — {tm_p}",
        "ΔpLDDT {d:+.1f} — {plddt_p}",
        "结论：{verdict}。",
    ),
}

# scan summary: one sentence per language (moved here from predict.py)
_SCAN_TPL: dict[str, str] = {
    "ru": ("Скан позиции {pos}: {n} замен вокруг {wt}. "
           "Сильнейший отклик — {wt}{pos}{best} "
           "(local RMSD {best_r:.2f} Å), "
           "нейтральнейший — {wt}{pos}{worst} "
           "({worst_r:.2f} Å). "
           "Разброс ×{ratio:.1f} — "
           "порядок откликов и есть предиктивный сигнал на детерминированной модели."),
    "en": ("Scan of position {pos}: {n} substitutions around {wt}. "
           "Strongest response — {wt}{pos}{best} "
           "(local RMSD {best_r:.2f} Å), "
           "most neutral — {wt}{pos}{worst} "
           "({worst_r:.2f} Å). "
           "Spread ×{ratio:.1f} — "
           "on a deterministic model, the ordering of responses is the predictive signal."),
    "zh": ("位置 {pos} 的扫描：围绕 {wt} 的 {n} 种替换。"
           "响应最强——{wt}{pos}{best}"
           "（local RMSD {best_r:.2f} Å），"
           "最中性——{wt}{pos}{worst}"
           "（{worst_r:.2f} Å）。"
           "离散度 ×{ratio:.1f}——"
           "在确定性模型上，响应的排序本身就是预测信号。"),
}


def make_summary(r: RmsdResult, wt_aa: str, position: int, mut_aa: str,
                 lang: str | None = None) -> str:
    """Compose a human-readable verdict from the metric bands."""
    lg = norm_lang(lang)
    bands = _BANDS[lg]
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

    return " ".join(_SUMMARY_TPL[lg]).format(
        m=f"{wt_aa}{position}{mut_aa}",
        lr=lr, a=r.local_window[0], b=r.local_window[1],
        local=bands["local"][lb], note=bands["local_note"][lb],
        tm=r.tm_score, tm_p=bands["tm"][tb],
        d=d, plddt_p=bands["plddt"][pb],
        verdict=_VERDICTS[lg][r.interpretation],
    )


def make_scan_summary(pos: int, n: int, wt_aa: str,
                      best_aa: str, best_rmsd: float,
                      worst_aa: str, worst_rmsd: float,
                      lang: str | None = None) -> str:
    """Ranking summary for the saturation scan (best vs most neutral)."""
    return _SCAN_TPL[norm_lang(lang)].format(
        pos=pos, n=n, wt=wt_aa, best=best_aa, best_r=best_rmsd,
        worst=worst_aa, worst_r=worst_rmsd,
        ratio=best_rmsd / max(worst_rmsd, 1e-9),
    )


# ensemble summary: the dial's output is the distribution of responses, so the
# sentence reports the distribution (median + IQR of local RMSD, median |ΔpLDDT|
# of the anchor window) and its verdict — not a two-structure comparison.
_ENSEMBLE_TPL: dict[str, str] = {
    "ru": ("Ансамбль позиции {pos} ({wt}): {n} вариантов, μ={mu}, τ={tau}. "
           "Медианный local RMSD {lr:.2f} Å (IQR {iqr:.2f} Å), "
           "медианный |ΔpLDDT| окна {dp:.2f}. Отклики {width} — "
           "уровень чувствительности: {level}."),
    "en": ("Ensemble of position {pos} ({wt}): {n} variants, mu={mu}, tau={tau}. "
           "Median local RMSD {lr:.2f} Å (IQR {iqr:.2f} Å), "
           "median window |ΔpLDDT| {dp:.2f}. Responses are {width} — "
           "sensitivity level: {level}."),
    "zh": ("位置 {pos}（{wt}）的集合：{n} 个变体，μ={mu}，τ={tau}。"
           "局部 RMSD 中位数 {lr:.2f} Å（IQR {iqr:.2f} Å），"
           "窗口 |ΔpLDDT| 中位数 {dp:.2f}。响应{width}——"
           "敏感性水平：{level}。"),
}

_LEVEL_WORDS: dict[str, dict[str, str]] = {
    "ru": {
        "quiet": "слабая (отклики в пределах шума модели)",
        "moderate": "умеренная",
        "strong": "высокая",
    },
    "en": {
        "quiet": "low (responses within the model's noise)",
        "moderate": "moderate",
        "strong": "high",
    },
    "zh": {
        "quiet": "低（响应在模型噪声范围内）",
        "moderate": "中等",
        "strong": "高",
    },
}

_WIDTH_WORDS: dict[str, dict[str, str]] = {
    "ru": {
        "narrow": "узко разбросаны",
        "moderate": "умеренно разбросаны",
        "wide": "широко разбросаны",
    },
    "en": {
        "narrow": "narrowly spread",
        "moderate": "moderately spread",
        "wide": "widely spread",
    },
    "zh": {
        "narrow": "离散较窄",
        "moderate": "离散适中",
        "wide": "离散较宽",
    },
}


def make_ensemble_summary(pos: int, wt_aa: str, mu: int, tau: float, n: int,
                          stats: dict, headline: dict,
                          lang: str | None = None) -> str:
    """Distribution summary for a sampled mutagenesis ensemble."""
    lg = norm_lang(lang)
    lr = stats["local_rmsd"]
    return _ENSEMBLE_TPL[lg].format(
        pos=pos, wt=wt_aa, n=n, mu=mu, tau=tau,
        lr=lr["median"], iqr=lr["iqr"],
        dp=stats["dplddt_local"]["median"],
        width=_WIDTH_WORDS[lg][headline["width"]],
        level=_LEVEL_WORDS[lg][headline["level"]],
    )


# scan map summary: the map's headline is its most fragile position plus the
# quadrant census (dum.md §5 shape signatures) — a distribution verdict again,
# never a two-structure comparison.
_SCAN_MAP_TPL: dict[str, str] = {
    "ru": ("Карта чувствительности: {n} позиций × 19 замен ({folds} фолдов). "
           "Самая хрупкая — {wt}{pos}{best} (max local RMSD {best_r:.2f} Å). "
           "Квадранты: ежей: {h}, игл: {nd}, дисков: {d}, клеверов: {c}."),
    "en": ("Sensitivity map: {n} positions × 19 substitutions ({folds} folds). "
           "Most fragile — {wt}{pos}{best} (max local RMSD {best_r:.2f} Å). "
           "Quadrants: hedgehogs: {h}, needles: {nd}, disks: {d}, clovers: {c}."),
    "zh": ("敏感性图谱：{n} 个位置 × 19 种替换（{folds} 次折叠）。"
           "最脆弱——{wt}{pos}{best}（max local RMSD {best_r:.2f} Å）。"
           "象限：海胆：{h}，尖针：{nd}，圆盘：{d}，三叶草：{c}。"),
}


def make_scan_map_summary(n: int, folds: int, fragile: dict | None,
                          counts: dict, lang: str | None = None) -> str:
    """Headline for a sensitivity map run."""
    lg = norm_lang(lang)
    if fragile is None:
        return _SCAN_MAP_TPL[lg].format(
            n=n, folds=folds, wt="—", pos="—", best="—", best_r=0.0,
            h=counts["hedgehog"], nd=counts["needle"],
            d=counts["disk"], c=counts["clover"])
    best = max(fragile["rows"], key=lambda r: r["local_rmsd"])
    return _SCAN_MAP_TPL[lg].format(
        n=n, folds=folds, wt=fragile["wt_aa"], pos=fragile["pos"],
        best=best["mut_aa"], best_r=best["local_rmsd"],
        h=counts["hedgehog"], nd=counts["needle"],
        d=counts["disk"], c=counts["clover"])