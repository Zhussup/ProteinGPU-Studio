"""Per-language user-facing strings (ru is the source of truth).

The frontend sends its active UI language (?lang=ru|en|zh, default ru) and the
backend picks templates from these tables. Adding a language = adding a column
to each table; adding a string = adding a key to every table (a KeyError on a
half-added key is loud on the first request, not a silent Russian fallback).
"""
from __future__ import annotations

LANGS = ("ru", "en", "zh")


def norm_lang(lang: str | None) -> str:
    """Map any foreign/absent value to ru (the documented default)."""
    return lang if lang in LANGS else "ru"


# -- сообщения этапов конвейера (predict router + ожидание GPU в job_manager) --
# значения ru должны остаться побайтно равными строкам до i18n (тесты сверяют
# их); {m}/{i}/{n} подставляются через stage_text().
# -- 流水线阶段消息（predict 路由 + job_manager 的 GPU 等待）---------------------
# ru 值必须与引入 i18n 前的字符串逐字节一致（测试有断言）；
# {m}/{i}/{n} 经 stage_text() 插值。
STAGES: dict[str, dict[str, str]] = {
    "ru": {
        "model": "подготовка модели",
        "wt": "инференс WT",
        "pdb": "сохранение PDB",
        "mutant": "инференс мутанта",
        "pdbs": "запись PDB-файлов",
        "kabsch": "наложение Кабша (C++/CUDA)",
        "metrics": "метрики",
        "subs": "мутант {m} ({i}/{n})",
        "ens": "вариант {m} ({i}/{n})",
        "map": "карта: {m} ({i}/{n})",
        "gpu_wait": "ожидание GPU-слота (занята другой задачей)",
        "plm_forward": "PLM-проход: {n}×19 замен из одного форварда",
        "plm_fold_topk": "PLM-скрин: фолдинг топ-K {m} ({i}/{n})",
        "plm_screen_wt": "PLM-скрин: инференс WT (якорь 3D-краски)",
        "dms_load": "DMS-набор: {id} — синглы, гигиена строк",
        "dms_map": "маппинг нумерации DMS → наша последовательность ({n} aa таргет)",
        "dms_plm": "PLM-маргин для {n} вариантов (один форвард)",
        "dms_folds": "фолдинг: WT + топ-1 по PLM на позицию + стратифицированная выборка ({n} всего)",
        "dms_fold_one": "DMS: фолдинг {m} ({i}/{n})",
        "dms_stats": "корреляции: {n} вариантов, bootstrap-CI",
    },
    "en": {
        "model": "loading the model",
        "wt": "WT inference",
        "pdb": "saving PDB",
        "mutant": "mutant inference",
        "pdbs": "writing PDB files",
        "kabsch": "Kabsch overlay (C++/CUDA)",
        "metrics": "computing metrics",
        "subs": "mutant {m} ({i}/{n})",
        "ens": "variant {m} ({i}/{n})",
        "map": "map: {m} ({i}/{n})",
        "gpu_wait": "waiting for a GPU slot (busy with another job)",
        "plm_forward": "PLM pass: {n}×19 substitutions from one forward",
        "plm_fold_topk": "PLM screen: folding top-K {m} ({i}/{n})",
        "plm_screen_wt": "PLM screen: WT inference (3D-paint anchor)",
        "dms_load": "DMS assay: {id} — singles, per-row hygiene",
        "dms_map": "mapping DMS numbering → our sequence ({n} aa target)",
        "dms_plm": "PLM margin for {n} variants (one forward)",
        "dms_folds": "folding: WT + PLM-fragile top-1 per position + stratified sample ({n} total)",
        "dms_fold_one": "DMS: folding {m} ({i}/{n})",
        "dms_stats": "correlations: {n} variants, bootstrap CI",
    },
    "zh": {
        "model": "准备模型",
        "wt": "WT 推理",
        "pdb": "保存 PDB",
        "mutant": "突变体推理",
        "pdbs": "写入 PDB 文件",
        "kabsch": "Kabsch 叠合（C++/CUDA）",
        "metrics": "计算指标",
        "subs": "突变体 {m}（{i}/{n}）",
        "ens": "变体 {m}（{i}/{n}）",
        "map": "图谱：{m}（{i}/{n}）",
        "gpu_wait": "等待 GPU 槽位（被其他任务占用）",
        "plm_forward": "PLM 前向：{n}×19 种替换，来自一次前向",
        "plm_fold_topk": "PLM 筛查：折叠 top-K {m}（{i}/{n}）",
        "plm_screen_wt": "PLM 筛查：WT 推理（3D 着色锚点）",
        "dms_load": "DMS 数据集：{id}——单突变行、逐行卫生检查",
        "dms_map": "DMS 编号映射到我们的序列（目标 {n} aa）",
        "dms_plm": "为 {n} 个变体计算 PLM 裕度（一次前向）",
        "dms_folds": "折叠：WT + 每位置 PLM 最脆弱 top-1 + 分层抽样（共 {n} 个）",
        "dms_fold_one": "DMS：折叠 {m}（{i}/{n}）",
        "dms_stats": "相关性：{n} 个变体，bootstrap 置信区间",
    },
}


# -- честные оговорки валидации (i18n-ключи с параметрами: фронт резолвит
# t(key, params) при активном языке, значения не замораживаются при смене языка)
# -- 验证的诚实说明（带参数的 i18n 键：前端按当前语言解析）-----------------------------
CAVEATS: dict[str, dict[str, str]] = {
    "ru": {
        "multiFiltered": "{n} строк multi-мутантов пропущено — заявлен только single-substitution режим",
        "regionMap": "DMS-таргет сшит с нашей последовательностью выравниванием ({mode}) — позиции вне колонок выравнивания отброшены",
        "foldSubset": "структурные корреляции посчитаны на подмножестве: сфолднуто {folded} из {total} mapped-строк",
        "zscoreCenter": "fitness z-score центрирован по среднему мутантов assay, а не по WT",
        "tiedFitness": "дисперсия fitness нулевая — корреляции не определены",
        "dummyProfile": "профиль dummy: PLM-маргины — детерминированный фейк, цифры не для выводов",
    },
    "en": {
        "multiFiltered": "{n} multi-mutant rows skipped — only the single-substitution regime is claimed",
        "regionMap": "the DMS target was stitched onto our sequence by alignment ({mode}) — positions outside aligned columns are dropped",
        "foldSubset": "structural correlations are computed on a subset: {folded} of {total} mapped rows folded",
        "zscoreCenter": "fitness z-score is centered on the assay's mutant mean, not the WT",
        "tiedFitness": "fitness variance is zero — correlations are undefined",
        "dummyProfile": "dummy profile: PLM margins are a deterministic fake — the numbers are for pipeline debugging",
    },
    "zh": {
        "multiFiltered": "已跳过 {n} 行多突变体——只声明单替换模式",
        "regionMap": "DMS 目标通过比对拼接到我们的序列上（{mode}）——比对列之外的位置已丢弃",
        "foldSubset": "结构相关性只在子集上计算：{total} 条映射行中折叠了 {folded} 条",
        "zscoreCenter": "fitness z-score 以 assay 的突变体均值为中心，而非 WT",
        "tiedFitness": "fitness 方差为零——相关性未定义",
        "dummyProfile": "dummy 配置：PLM 裕度为确定性假数据——数字仅用于调试流水线",
    },
}


def stage_text(key: str, lang: str | None, **params: object) -> str:
    return STAGES[norm_lang(lang)][key].format(**params)


# -- причина, которую показывает GPU-бейдж (system router) --------------------------------------
# -- GPU 徽标原因（system 路由）-------------------------------------------------
GPU_REASON: dict[str, str] = {
    "ru": "torch/CUDA недоступен — dummy-модель",
    "en": "torch/CUDA unavailable — dummy model",
    "zh": "torch/CUDA 不可用 — dummy 模型",
}


# -- предупреждения трансляции ДНК (service) и ошибки 422 (router) -------------
# -- DNA 翻译警告（service）与 422 错误（router）---------------------------------
TRANS_WARNINGS: dict[str, dict[str, str]] = {
    "ru": {
        "dropped": "удалены посторонние символы: {chars}",
        "no_atg": "старт-кодон ATG не найден — трансляция с первого нуклеотида",
        "tail3": "хвост цепи не кратен 3 — неполный кодон проигнорирован",
    },
    "en": {
        "dropped": "removed non-DNA characters: {chars}",
        "no_atg": "no ATG start codon found — translating from the first nucleotide",
        "tail3": "sequence tail is not a multiple of 3 — the incomplete codon is ignored",
    },
    "zh": {
        "dropped": "已移除非 DNA 字符：{chars}",
        "no_atg": "未找到起始密码子 ATG——从第一个核苷酸开始翻译",
        "tail3": "序列尾部不是 3 的倍数——不完整的密码子已忽略",
    },
}

TRANS_ERRORS: dict[str, dict[str, str]] = {
    "ru": {
        "no_codon": "не найдено ни одного полного кодона (нужны A/C/G/T)",
        "too_long": "цепь слишком длинная для трансляции: {n} nt (максимум 60000)",
    },
    "en": {
        "no_codon": "no complete codon found (A/C/G/T required)",
        "too_long": "sequence too long for translation: {n} nt (max 60000)",
    },
    "zh": {
        "no_codon": "未找到任何完整密码子（需要 A/C/G/T）",
        "too_long": "序列过长，无法翻译：{n} nt（上限 60000）",
    },
}


# -- inline-валидации 422 в окне ошибки запуска (predict router) ---------------
# -- 内联 422 校验，显示在运行错误框中（predict 路由）-----------------------------
VALIDATION: dict[str, dict[str, str]] = {
    "ru": {
        "same_residue": "мутантный остаток совпадает с остатком WT в этой позиции",
    },
    "en": {
        "same_residue": "mutant residue equals WT residue at that position",
    },
    "zh": {
        "same_residue": "突变残基与该位置的 WT 残基相同",
    },
}