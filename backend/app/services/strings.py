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


# -- pipeline stage messages (predict router + job_manager GPU wait) ----------
# ru values must stay byte-identical to the pre-i18n strings (tests assert on
# them); {m}/{i}/{n} are interpolated via stage_text().
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
    },
}


def stage_text(key: str, lang: str | None, **params: object) -> str:
    return STAGES[norm_lang(lang)][key].format(**params)


# -- GPU badge reason (system router) ------------------------------------------
GPU_REASON: dict[str, str] = {
    "ru": "torch/CUDA недоступен — dummy-модель",
    "en": "torch/CUDA unavailable — dummy model",
    "zh": "torch/CUDA 不可用 — dummy 模型",
}


# -- DNA translation warnings (service) and 422 errors (router) ---------------
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


# -- inline 422 validations surfaced in the run error box (predict router) ------
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