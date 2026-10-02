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

# фразы полос по языкам: по 3 полосы, пороги фиксированы interpret_rmsd
# 各语言的区间短语：各 3 档，阈值由 interpret_rmsd 固定
_BANDS: dict[str, dict[str, tuple[str, ...]]] = {
    "ru": {
        # полосы локального RMSD (те же пороги, что в interpret_rmsd: 1.0 / 2.0 Å)
        # 局部 RMSD 区间（阈值同 interpret_rmsd：1.0 / 2.0 Å）
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
        # полосы TM-score: <0.5 / 0.5–0.9 / >0.9
        # TM-score 区间：<0.5 / 0.5–0.9 / >0.9
        "tm": (
            "глобальная укладка изменена — цепи сворачиваются по-разному",
            "глобальная укладка в целом сохранена, но деформирована",
            "глобальная укладка сохранена",
        ),
        # полосы ΔpLDDT: ≤−1 / −1..+1 / ≥+1
        # ΔpLDDT 区间：≤−1 / −1..+1 / ≥+1
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

# interpretation → финальная фраза-вердикт
# interpretation → 最终结论短语
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

# шаблоны строк, по одному на язык; {плейсхолдеры} заполняются в make_summary
# 行模板，每种语言一份；{占位符} 在 make_summary 中填充
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

# сводка скана: по одному предложению на язык (перенесено из predict.py)
# 扫描摘要：每种语言一句（自 predict.py 迁移而来）
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


# сводка ансамбля: выход ручки — распределение откликов, поэтому предложение
# сообщает распределение (медиана + IQR локального RMSD, медиана |ΔpLDDT| окна
# якоря) и вердикт — а не сравнение двух структур.
# 组合摘要：旋钮的输出是响应分布，因此句子报告分布（局部 RMSD 的中位数 + IQR、
# 锚定窗口的 |ΔpLDDT| 中位数）及其结论——而非两结构比较。
_ENSEMBLE_TPL: dict[str, str] = {
    "ru": ("Ансамбль позиции {pos} ({wt}): {n} вариантов, μ={mu}, τ={tau}. "
           "Медианный local RMSD {lr:.2f} Å (IQR {iqr:.2f} Å), "
           "медианный |ΔpLDDT| окна {dp:.2f}. Отклики {width} — "
           "уровень чувствительности: {level}."),
    "en": ("Ensemble of position {pos} ({wt}): {n} variants, mu={mu}, tau={tau}. "
           "Median local RMSD {lr:.2f} Å (IQR {iqr:.2f} Å), "
           "median window |ΔpLDDT| {dp:.2f}. Responses are {width} — "
           "sensitivity level: {level}."),
    "zh": ("位置 {pos}（{wt}）的组合：{n} 个变体，μ={mu}，τ={tau}。"
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


# сводка карты: заголовок карты — самая хрупкая позиция плюс подсчёт квадрантов
# (dum.md §5, сигнатуры форм) — снова вердикт по распределению,
# а не сравнение двух структур.
# 图谱摘要：图谱标题为最脆弱位点加象限统计（dum.md §5 形态签名）——
# 同样是基于分布的结论，绝非两结构比较。
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


# сводка PLM-скрина: ранговый язык (percentile в пуле всех замен белка);
# fragile-выбор по plm_v_max, худшая замена = минимальный margin.
# PLM 筛查摘要：排序语言（全蛋白替换池中的百分位）；最脆弱按 plm_v_max，
# 最差替换为最小 margin。
_PLM_TPL: dict[str, str] = {
    "ru": ("PLM-скрин: {n_pos}×19 замен оценены из одного форварда; "
           "самая хрупкая позиция — {wt}{pos} (pctl {pctl:.0f}), "
           "worst-замена {best} (margin {margin:+.2f}); "
           "сфолднуто {folds_done} из топ-K."),
    "en": ("PLM screen: {n_pos}×19 substitutions scored from one forward; "
           "most fragile position — {wt}{pos} (pctl {pctl:.0f}), "
           "worst substitution {best} (margin {margin:+.2f}); "
           "{folds_done} of top-K folded."),
    "zh": ("PLM 筛查：{n_pos}×19 种替换由一次前向评估；"
           "最脆弱位置——{wt}{pos}（pctl {pctl:.0f}），"
           "最差替换 {best}（margin {margin:+.2f}）；"
           "已折叠 {folds_done} 个 top-K。"),
}

_NOTE_DUMMY: dict[str, str] = {
    "ru": (" Внимание: профиль dummy — оценки подставлены детерминированным "
           "фейком и непригодны для выводов."),
    "en": (" Caution: dummy profile — the scores are deterministic placeholders "
           "and must not be interpreted."),
    "zh": (" 注意：dummy 配置——评分由确定性占位数据填充，不可用于解读。"),
}


def make_plm_screen_summary(n_pos: int, folds_done: int, fragile: dict | None,
                            scorer: str, lang: str | None = None) -> str:
    """Headline for a whole-protein PLM screen (rank language: the PLM
    margin has no interpretable absolute scale — only within-protein ranks)."""
    lg = norm_lang(lang)
    if fragile is None:
        return _PLM_TPL[lg].format(
            n_pos=n_pos, folds_done=folds_done, wt="—", pos="—", pctl=0.0,
            best="—", margin=0.0) + (_NOTE_DUMMY[lg] if scorer == "dummy-plm" else "")
    worst = min(fragile["rows"], key=lambda r: r["plm_margin"])
    return _PLM_TPL[lg].format(
        n_pos=n_pos, folds_done=folds_done, wt=fragile["wt_aa"],
        pos=fragile["pos"], pctl=fragile["stats"]["pctl_v_max"],
        best=worst["mut_aa"], margin=worst["plm_margin"],
    ) + (_NOTE_DUMMY[lg] if scorer == "dummy-plm" else "")


# сводка DMS-валидации: ранговый язык; ρ(PLM-margin, fitness) — zero-shot
# заголовок, структурный отклик — на сфолднутом подмножестве. Неинформативные
# значения (ρ None при n<3) печатаются как «—», а не как 0.
# DMS 验证摘要：排序语言；ρ(PLM-margin, fitness) 为 zero-shot 标题。
_DMS_TPL: dict[str, str] = {
    "ru": ("DMS-валидация {assay}: mapped {n_rows} синглов; "
           "zero-shot ρ(PLM-margin, fitness) = {rho} (n={n_plm}); "
           "сфолднуто {n_fold}: ρ(ΔpLDDT, fitness) = {drho}."),
    "en": ("DMS validation {assay}: {n_rows} mapped singles; "
           "zero-shot ρ(PLM margin, fitness) = {rho} (n={n_plm}); "
           "{n_fold} folded: ρ(ΔpLDDT, fitness) = {drho}."),
    "zh": ("DMS 验证 {assay}：映射 {n_rows} 条单突变；"
           "zero-shot ρ(PLM-margin, fitness) = {rho}（n={n_plm}）；"
           "折叠 {n_fold} 个：ρ(ΔpLDDT, fitness) = {drho}。"),
}


def make_dms_validation_summary(assay_id: str, n_rows: int,
                                plm_rho: float | None, n_plm: int,
                                dplddt_rho: float | None, n_fold: int,
                                lang: str | None = None) -> str:
    """Headline for a DMS-validation run (ranks only; ρ=None → «—»)."""
    lg = norm_lang(lang)
    rho = "—" if plm_rho is None else f"{plm_rho:+.2f}"
    drho = "—" if dplddt_rho is None else f"{dplddt_rho:+.2f}"
    return _DMS_TPL[lg].format(
        assay=assay_id, n_rows=n_rows, rho=rho, n_plm=n_plm,
        drho=drho, n_fold=n_fold)