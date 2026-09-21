# -*- coding: utf-8 -*-
"""Генератор презентаций дипломной работы: RU + ZH.

Запуск:  .venv/bin/python scripts/21_make_presentation.py
Выход:   docs/presentation_ru.pptx, docs/presentation_zh.pptx

Один набор слайдов, два языка. Строгая чёрно-белая стилистика проекта
(квадратные углы, акцент #b91c1c как в UI). Все числа — из docs/
(benchmarks.md, ml_model_decision.md), ничего не выдумано.
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"

BLACK = RGBColor(0x11, 0x11, 0x11)
GREY = RGBColor(0x73, 0x73, 0x73)
LIGHT = RGBColor(0xD4, 0xD4, 0xD4)
RED = RGBColor(0xB9, 0x1C, 0x1C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.6)
FONT = "Arial"           # базовый; для CJK PowerPoint сам подставит системный
CJK_FONT = "Microsoft YaHei"

# ---------------------------------------------------------------------------
# Контент: каждый элемент — пара (русский, китайский). Структура деки общая.
# ---------------------------------------------------------------------------

TITLE = {
    "ru": ("ProteinGPU-Studio",
           "Предиктивное 3D-моделирование белков и анализ мутаций in silico на GPU",
           "Дипломная работа · 2026 · Автор: [ФИО, группа]"),
    "zh": ("ProteinGPU-Studio",
           "基于 GPU 的蛋白质三维结构预测与突变 in silico 分析平台",
           "毕业设计 · 2026 · 作者：[姓名，班级]"),
}

# (заголовок, [(тезис или None для пропуска, ...)], таблица или None)
#   таблица: (headers, rows) — тоже парами языков
SLIDES = [
    (
        {"ru": "Проблема", "zh": "问题"},
        [
            {"ru": "Точечная аминокислотная замена может дестабилизировать белок и привести к заболеванию",
             "zh": "单点氨基酸替换可能导致蛋白质失稳并引发疾病"},
            {"ru": "Экспериментальная проверка одной мутации — недели и реактивы; нужен быстрый вычислительный эксперимент",
             "zh": "实验验证单个突变需要数周；需要快速的计算实验"},
            {"ru": "Задача: предсказать структуры WT и мутанта, количественно сравнить, уложиться в интерактивное время",
             "zh": "任务：预测野生型与突变体结构，定量比较，并控制在交互式响应时间内"},
        ],
        None,
    ),
    (
        {"ru": "Задачи проекта", "zh": "项目任务"},
        [
            {"ru": "Сервис предсказания 3D-структуры по последовательности FASTA",
             "zh": "基于 FASTA 序列的 3D 结构预测服务"},
            {"ru": "In silico мутагенез: наложение по Кабшу, RMSD (глобальный + локальный ±10), TM-score, pLDDT",
             "zh": "In silico 突变：Kabsch 叠合、RMSD（全局 + 局部 ±10）、TM-score、pLDDT"},
            {"ru": "Ядро наложения на C++17 + CUDA с бенчмаркингом CPU vs GPU",
             "zh": "C++17 + CUDA 叠合核心，CPU 与 GPU 基准对比"},
            {"ru": "Веб-интерфейс: 3D-визуализация, насыщающий скан позиции, обозреватель белка",
             "zh": "Web 界面：3D 可视化、位点饱和扫描、蛋白质浏览器"},
            {"ru": "Честный бенчмаркинг: median+IQR, PCIe-копии отдельно, учёт троттлинга 60W GPU",
             "zh": "严谨基准测试：median+IQR、单独统计 PCIe 拷贝、考虑 60W GPU 降频"},
        ],
        None,
    ),
    (
        {"ru": "Выбор ML-модели", "zh": "ML 模型选型"},
        [
            {"ru": "Бюджет: 6 GB VRAM ноутбука RTX 3050 (60W). Спайк-протокол: VRAM/latency × длина × точность",
             "zh": "预算：RTX 3050 笔记本 6 GB 显存（60W）。 Spike 方案：显存/延迟 × 长度 × 精度"},
            {"ru": "Решение — OmegaFold: single-sequence (без MSA), чистый PyTorch, резидентная загрузка весов",
             "zh": "选定 OmegaFold：单序列（无需 MSA）、纯 PyTorch、权重常驻显存"},
            {"ru": "ESMFold (3B) не помещается; AlphaFold2 требует MSA — оба отклонены decision record'ом",
             "zh": "ESMFold（3B）放不进显存；AlphaFold2 需要 MSA —— 均被决策记录否决"},
        ],
        (
            ["Модель / 模型", "Параметры / 参数", "MSA", "6 GB VRAM / 显存"],
            [
                ["ESMFold (полный / 完整)", "3B LM", "не нужен / 不需要", "не влезает / 超出"],
                ["OmegaFold", "~700M", "не нужен / 不需要", "помещается / 可行"],
                ["AlphaFold2", "93M", "нужен / 需要", "нет MSA / 无 MSA 输入"],
            ],
        ),
    ),
    (
        {"ru": "Архитектура", "zh": "系统架构"},
        [
            {"ru": "React + TypeScript (Vite) — рабочее место: ввод, мутации, 3D (3Dmol.js), обозреватель белка",
             "zh": "React + TypeScript（Vite）—— 工作台：输入、突变、3D（3Dmol.js）、蛋白质浏览器"},
            {"ru": "FastAPI — job-менеджер: SQLite-очередь, GPU-семафор (один CUDA-поток), артефакты на диске",
             "zh": "FastAPI —— 作业管理：SQLite 队列、GPU 信号量（单 CUDA 流）、产物落盘"},
            {"ru": "Вычислительное ядро: OmegaFold (PyTorch) + C++17/CUDA ядро Кабша (pybind11, zero-copy)",
             "zh": "计算核心：OmegaFold（PyTorch）+ C++17/CUDA Kabsch 核心（pybind11、零拷贝）"},
            {"ru": "Каждый ответ несёт тег engine (cuda/cpp/numpy) — правило честности проекта",
             "zh": "每个响应都带 engine 标签（cuda/cpp/numpy）—— 项目的诚实原则"},
        ],
        None,
    ),
    (
        {"ru": "Методика честных измерений", "zh": "严谨的测量方法"},
        [
            {"ru": "60-ваттный ноутбук троттлит: единичный замер врёт",
             "zh": "60W 笔记本存在降频：单次测量不可信"},
            {"ru": "Все числа — median + IQR по ≥5 повторам, 2 warmup отбрасываются",
             "zh": "所有数值均为 ≥5 次重复的 median + IQR，并剔除 2 次 warmup"},
            {"ru": "PCIe-копии считаются отдельно от device-resident пути — это два разных числа",
             "zh": "PCIe 拷贝与 device-resident 路径分开统计 —— 两个不同的数字"},
            {"ru": "GPU-таблицы снимаются на чистой VRAM (фоновые процессы контролируются)",
             "zh": "GPU 数据在干净显存下采集（控制后台进程）"},
        ],
        None,
    ),
    (
        {"ru": "Инференс фолдинга (median ± IQR)", "zh": "折叠推理性能（median ± IQR）"},
        [],
        (
            ["Профиль / 配置", "76 aa", "100 aa", "200 aa", "VRAM 76→200 / 显存"],
            [
                ["fp32-gpu", "11.59 ± 0.03 с", "18.59 ± 0.01 с", "79.70 ± 0.10 с", "3271→3905 MB"],
                ["fp16-gpu (autocast)", "8.72 ± 0.02 с", "13.98 ± 0.10 с", "58.97 ± 0.03 с", "4863→5227 MB"],
                ["cpu", "143.5 с", "—", "—", "—"],
            ],
        ),
    ),
    (
        {"ru": "Выводы по инференсу", "zh": "推理性能结论"},
        [
            {"ru": "GPU быстрее CPU в 12.4× уже на 76 остатках",
             "zh": "在 76 残基上 GPU 已比 CPU 快 12.4 倍"},
            {"ru": "fp16-autocast: стабильное ускорение 1.33×; плата — +1.5 GB VRAM (кэш autocast)",
             "zh": "fp16-autocast：稳定加速 1.33×；代价是 +1.5 GB 显存（autocast 缓存）"},
            {"ru": "Latency ~ O(N²): 76→200 aa даёт ×6.9 — квадратичный attention",
             "zh": "延迟约 O(N²)：76→200 残基放大 6.9 倍 —— attention 的平方复杂度"},
            {"ru": "300 aa вне интерактивного бюджета во всех профилях (fp32: 199 с / 5077 MB; fp16: OOM)",
             "zh": "300 aa 超出交互预算（fp32：199 秒 / 5077 MB；fp16：OOM）"},
        ],
        None,
    ),
    (
        {"ru": "Ядро Кабша: C++ vs CUDA (batched RMSD)", "zh": "Kabsch 核心：C++ 与 CUDA（批量 RMSD）"},
        [],
        (
            ["B × N", "numpy", "C++ OpenMP", "CUDA (PCIe)", "CUDA (resident)"],
            [
                ["64 × 76", "1.36 мс", "0.03 мс", "0.30 мс", "0.27 мс"],
                ["1024 × 256", "31.83 мс", "0.36 мс", "3.21 мс", "1.81 мс"],
                ["2048 × 512", "89.17 мс", "1.43 мс", "9.10 мс", "2.73 мс"],
                ["4096 × 1024", "287.81 мс", "5.59 мс", "27.78 мс", "6.15 мс"],
            ],
        ),
    ),
    (
        {"ru": "Выводы по ядру", "zh": "核心性能结论"},
        [
            {"ru": "Практический случай (1 пара WT/мутант) — 0.03 мс на C++, numpy в 45× медленнее",
             "zh": "实际场景（1 对 WT/突变体）C++ 仅 0.03 毫秒，numpy 慢 45 倍"},
            {"ru": "PCIe — главный налог GPU: ×4.5 к времени против resident (4096×1024)",
             "zh": "PCIe 是 GPU 的主要开销：相比 resident 慢 4.5 倍（4096×1024）"},
            {"ru": "Гипотеза «GPU быстрее на батчах» верна только для device-resident данных — в бэкенде zero-copy",
             "zh": "「GPU 批量更快」仅对 device-resident 数据成立 —— 后端因此采用零拷贝"},
            {"ru": "Точность ядер: CPU vs numpy ≤1e-9, CUDA ≤1e-5 + scipy cross-check",
             "zh": "核心精度：CPU 与 numpy 误差 ≤1e-9，CUDA ≤1e-5，并通过 scipy 交叉验证"},
        ],
        None,
    ),
    (
        {"ru": "e2e-верификация (убиквитин, fp32 GPU)", "zh": "端到端验证（泛素，fp32 GPU）"},
        [],
        (
            ["Мутация / 突变", "Global RMSD", "Local RMSD", "TM-score"],
            [
                ["I44A", "0.21 Å", "0.06 Å", "0.996"],
                ["I3L", "0.28 Å", "0.08 Å", "0.992"],
                ["P19G", "0.72 Å", "0.13 Å", "0.963"],
            ],
        ),
    ),
    (
        {"ru": "Научный вывод", "zh": "科学结论"},
        [
            {"ru": "Ожидание ТЗ «P19G ≥ 2 Å» не подтвердилось: реальная OmegaFold почти детерминирована",
             "zh": "技术任务书预期的「P19G ≥ 2 Å」未成立：真实 OmegaFold 几乎是确定性的"},
            {"ru": "Подтвердилось порядковое ранжирование из литературы: мутация пролина в петле даёт наибольший отклик (P19G в 2.6–3.4× больше)",
             "zh": "验证了文献中的排序假设：环区脯氨酸突变响应最大（P19G 为其他突变的 2.6–3.4 倍）"},
            {"ru": "Метрика осмысленно ранжирует мутации; абсолютные пороги оставлены с оговоркой про суб-Å эффекты",
             "zh": "该指标能对突变进行有效排序；绝对阈值保留，但注明亚埃级效应的说明"},
        ],
        None,
    ),
    (
        {"ru": "Обозреватель белка (Protein Viewer)", "zh": "蛋白质浏览器（Protein Viewer）"},
        [
            {"ru": "Аналог геномных браузеров (NCBI GDV) на белковой оси: единая система координат для всех данных",
             "zh": "蛋白质坐标轴上的基因组浏览器类比（NCBI GDV）：所有数据的统一坐标系"},
            {"ru": "Треки: последовательность, pLDDT, мутация, скан 19 замен, домены и варианты UniProt",
             "zh": "轨道：序列、pLDDT、突变、19 种替换扫描、UniProt 结构域与已知变异"},
            {"ru": "Кросс-хайлайт: клик по позиции синхронно подсвечивает 3D-структуру и все треки",
             "zh": "交叉高亮：点击位点同步高亮 3D 结构与所有轨道"},
            {"ru": "Рендеринг: canvas (данные) + SVG (интеракция) с единой функцией геометрии",
             "zh": "渲染：canvas（数据）+ SVG（交互），几何计算统一于单一函数"},
        ],
        None,
    ),
    (
        {"ru": "Живое демо", "zh": "现场演示"},
        [
            {"ru": "Пресет KRAS G12D → предсказание WT + мутант → наложение и метрики",
             "zh": "预设 KRAS G12D → 预测 WT + 突变体 → 叠合与指标"},
            {"ru": "Скан позиции: 19 замен, ранжирование по локальному отклику",
             "zh": "位点扫描：19 种替换，按局部响应排序"},
            {"ru": "Обозреватель белка: треки, окно ±50, кросс-хайлайт с 3D",
             "zh": "蛋白质浏览器：轨道、±50 窗口、交叉高亮"},
            {"ru": "(место для скриншотов после записи демо-видео)",
             "zh": "（录制演示视频后此处替换为截图）"},
        ],
        None,
    ),
    (
        {"ru": "Выводы", "zh": "结论"},
        [
            {"ru": "Платформа решает полный цикл: FASTA → структура → мутация → метрики → визуализация",
             "zh": "平台覆盖完整链路：FASTA → 结构 → 突变 → 指标 → 可视化"},
            {"ru": "OmegaFold + CUDA/C++ ядро дают интерактивный режим на 6-ватт… на 6-гигабайтном ноутбуке",
             "zh": "OmegaFold + C++/CUDA 核心使 6 GB 笔记本具备交互式分析能力"},
            {"ru": "Бенчмаркинг честный: median+IQR, PCIe отдельно, теги engine в каждом ответе",
             "zh": "基准测试严谨：median+IQR、PCIe 单列、每个响应带 engine 标签"},
            {"ru": "Научная ценность: инструмент ранжирует мутации согласованно с литературой",
             "zh": "科学价值：工具的突变排序与文献一致"},
        ],
        None,
    ),
    (
        {"ru": "Перспективы", "zh": "展望"},
        [
            {"ru": "UniProt-аннотации на оси обозревателя: домены и известные болезнетворные варианты",
             "zh": "浏览器坐标轴上的 UniProt 注释：结构域与已知致病突变"},
            {"ru": "Распознавание загруженных последовательностей (точное совпадение → аннотации; гомолог → справочная карточка)",
             "zh": "上传序列的识别（完全匹配 → 注释；同源蛋白 → 参考卡片）"},
            {"ru": "Карта уязвимости всего белка (агрегат pLDDT + домены + варианты)",
             "zh": "全蛋白脆弱性图谱（pLDDT + 结构域 + 变异的聚合）"},
            {"ru": "История прогонов как треки обозревателя",
             "zh": "历史作业作为浏览器轨道"},
        ],
        None,
    ),
]

THANKS = {"ru": "Спасибо за внимание!", "zh": "谢谢！"}
QUESTIONS = {"ru": "Вопросы?", "zh": "提问环节"}


# ---------------------------------------------------------------------------
# Рендер
# ---------------------------------------------------------------------------

def _style_text(tf, size, color=BLACK, bold=False, align=PP_ALIGN.LEFT):
    for p in tf.paragraphs:
        p.alignment = align
        for r in p.runs:
            r.font.name = FONT
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color


def title_slide(prs, lang):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    t, sub, foot = TITLE[lang]
    box = s.shapes.add_textbox(MARGIN, Inches(2.3), SLIDE_W - 2 * MARGIN, Inches(1.2))
    box.text_frame.text = t
    _style_text(box.text_frame, 44, BLACK, bold=True, align=PP_ALIGN.CENTER)
    box2 = s.shapes.add_textbox(MARGIN, Inches(3.6), SLIDE_W - 2 * MARGIN, Inches(1.0))
    box2.text_frame.word_wrap = True
    box2.text_frame.text = sub
    _style_text(box2.text_frame, 18, GREY, align=PP_ALIGN.CENTER)
    line = s.shapes.add_shape(1, SLIDE_W // 2 - Inches(1), Inches(4.8), Inches(2), Emu(19050))
    line.fill.solid(); line.fill.fore_color.rgb = RED; line.line.fill.background()
    box3 = s.shapes.add_textbox(MARGIN, Inches(6.4), SLIDE_W - 2 * MARGIN, Inches(0.5))
    box3.text_frame.text = foot
    _style_text(box3.text_frame, 12, GREY, align=PP_ALIGN.CENTER)


def bullets_slide(prs, lang, title, bullets, table=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head = s.shapes.add_textbox(MARGIN, Inches(0.35), SLIDE_W - 2 * MARGIN, Inches(0.8))
    head.text_frame.text = title[lang]
    _style_text(head.text_frame, 26, BLACK, bold=True)
    bar = s.shapes.add_shape(1, MARGIN, Inches(1.05), Inches(1.4), Emu(28575))
    bar.fill.solid(); bar.fill.fore_color.rgb = RED; bar.line.fill.background()

    top = Inches(1.35)
    if bullets:
        bh = Inches(5.4) if table is None else Inches(2.4)
        body = s.shapes.add_textbox(MARGIN, top, SLIDE_W - 2 * MARGIN, bh)
        tf = body.text_frame
        tf.word_wrap = True
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = "— " + b[lang]
            p.space_after = Pt(10)
        _style_text(tf, 17 if table is None else 15)

    if table is not None:
        headers, rows = table
        n_rows = len(rows) + 1
        th = Inches(0.42) * n_rows
        ty = top if not bullets else Inches(4.05)
        if bullets:
            ty = Inches(3.9) if n_rows <= 4 else Inches(4.3)
        gt = s.shapes.add_table(n_rows, len(headers), MARGIN, ty,
                                SLIDE_W - 2 * MARGIN, th).table
        for j, h in enumerate(headers):
            c = gt.cell(0, j)
            c.text = h
            _style_text(c.text_frame, 13, WHITE, bold=True)
            c.fill.solid(); c.fill.fore_color.rgb = BLACK
        for i, row in enumerate(rows, start=1):
            for j, cell in enumerate(row):
                c = gt.cell(i, j)
                c.text = cell
                _style_text(c.text_frame, 13)
                c.fill.solid()
                c.fill.fore_color.rgb = RGBColor(0xF5, 0xF5, 0xF5) if i % 2 else WHITE


def thanks_slide(prs, lang):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    box = s.shapes.add_textbox(MARGIN, Inches(2.8), SLIDE_W - 2 * MARGIN, Inches(1.2))
    box.text_frame.text = THANKS[lang]
    _style_text(box.text_frame, 40, BLACK, bold=True, align=PP_ALIGN.CENTER)
    box2 = s.shapes.add_textbox(MARGIN, Inches(4.2), SLIDE_W - 2 * MARGIN, Inches(0.6))
    box2.text_frame.text = QUESTIONS[lang]
    _style_text(box2.text_frame, 20, GREY, align=PP_ALIGN.CENTER)


def build(lang: str, path: Path):
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    title_slide(prs, lang)
    for title, bullets, table in SLIDES:
        bullets_slide(prs, lang, title, bullets, table)
    thanks_slide(prs, lang)
    prs.save(path)
    print(f"OK  {path.relative_to(ROOT)}  ({len(prs.slides._sldIdLst)} слайдов)")


if __name__ == "__main__":
    build("ru", OUT / "presentation_ru.pptx")
    build("zh", OUT / "presentation_zh.pptx")