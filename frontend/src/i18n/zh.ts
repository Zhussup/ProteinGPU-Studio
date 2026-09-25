// zh: те же ключи, что в ru.ts (соответствие формы проверяется на этапе
// компиляции через Dict).
// zh：与 ru.ts 相同的键（通过 Dict 在编译期校验结构）。
import type { Dict } from './ru'

export const zh: Dict = {
  'common.close': '关闭',
  'common.chartLoading': '图表加载中…',
  'common.language': '界面语言',

  'app.subtitle': '结构预测 · 计算突变 · Kabsch/RMSD（CPU 与 CUDA）',
  'nav.workspace': '工作台',
  'nav.benchmarks': '基准测试',
  'health.ok': '后端可用',
  'health.down': '后端不可用——请启动 uvicorn',
  'health.checking': '检查中…',

  'seq.label': '序列（FASTA 或纯文本）',
  'seq.invalidChars': '· 含无效字符',
  'seq.lenRange': '· {min}–{max}',
  'seq.uploadFasta': '上传 FASTA（DNA 或蛋白）',
  'seq.uploading': '上传中…',
  'seq.translateTitle': '翻译：DNA → 密码子 → 氨基酸',
  'seq.translatedFromDna': '>由 DNA 翻译（{len} nt）',

  'mut.title': '突变',
  'mut.position': '位置（从 1 开始）',
  'mut.newResidue': '新残基',
  'mut.demoPresets': '演示预设（泛素，有文献依据）：',

  'dial.title': '突变强度旋钮',
  'dial.mode.exhaustive': '全部 19 种替换',
  'dial.modeExhaustiveTitle':
    'exhaustive 模式：该位点的全部 19 种单替换（「位点扫描」的超集）；不使用 μ/τ/K',
  'dial.mu': 'μ — 每个变体的同步替换数',
  'dial.muHint': '锚点 + (μ−1) 个背景',
  'dial.tau': 'τ — 替换谱温度（按 Grantham）',
  'dial.tauCons': '保守',
  'dial.tauRad': '激进',
  'dial.k': 'K — 变体数',
  'dial.seed': '种子',
  'dial.seedAuto': '自动',
  'dial.seedNote':
    '种子留空 → 配置（序列、位置、μ、τ、K）确定性地决定组合——重复运行结果相同；填数字为显式覆盖',
  'dial.estimateLabel': '耗时估计：',
  'dial.estimateInstant': '< 1 秒（dummy）',
  'dial.estimateWarn': '耗时较长——请减小 K、改用 fp16 或缩短组合',
  'dial.unit.sec': '秒',
  'dial.unit.min': '分钟',
  'dial.granthamNote':
    '替换按 Grantham 矩阵（理化距离，Grantham 1974）抽取：τ=0——仅保守半区，' +
    'τ=1——仅激进半区，τ=0.5——全部 19 种均匀抽取',

  'run.wtOnly': '仅 WT',
  'run.wtMutant': 'WT + 突变体',
  'run.scan': '位点扫描（19 个突变）',
  'run.scanTitle': '所选位点的全部 19 种氨基酸替换——排序筛选',
  'run.ensemble': '组合（旋钮）',
  'run.ensembleTitle':
    '围绕锚定位点生成 K 个变体：μ 个同步替换、Grantham 谱（τ），敏感性 = 响应的分布',
  'run.reset': '重置',
  'run.profile': '推理配置：',
  'run.profileHint': '应用于下一次运行；切换时会重新加载模型',
  'run.auto': 'auto——按配置文件',
  'run.profile.fp32': 'GPU fp32',
  'run.profile.fp16': 'GPU fp16',
  'run.profile.cpu': 'CPU',
  'run.dummy': 'dummy（测试）',
  'run.queued': '排队中…',
  'run.jobFailed': '任务出错',
  'run.running': '运行中…',
  'run.gpu': 'GPU：{name}',
  'run.cpuOnly': '仅 CPU：{reason}',
  'run.noCuda': '无 CUDA',
  'run.progressNote': '进度按真实流水线阶段显示，不做插值；推理需要数分钟，且在阶段内部不可再分',
  'run.stage.model': '模型',
  'run.stage.wt': 'WT',
  'run.stage.pdb': 'PDB',
  'run.stage.mutant': '突变体',
  'run.stage.align': '叠合',
  'run.stage.metrics': '指标',
  'run.stage.subs19': '19 个替换',
  'run.stage.ens': '变体',
  'run.stage.summary': '汇总',

  'ws.scanTitle': '位点 {pos} 扫描——全部 19 种替换',
  'ws.ensembleTitle': '位点 {pos} 组合——突变强度旋钮',
  'ws.overlayResult': '叠合结果',
  'ws.hint':
    '运行「WT + 突变体」后，这里会出现 global + local RMSD（±10 残基）、TM-score 和 pLDDT。' +
    '「位点扫描」会跑全部 19 种替换并按局部响应排序。' +
    '模型几乎是确定性的：在稳定折叠上，点突变的偏移在亚埃量级' +
    '（泛素：I44A 0.21 Å、I3L 0.28 Å、P19G 0.72 Å——响应最大）。' +
    '请以突变之间的 local RMSD 相对比较为准，而不是绝对阈值。',

  'res.verdict': '判定',
  'res.plddtWt': 'pLDDT（WT）',
  'res.plddtMut': 'pLDDT（突变体）',
  'res.alignEngine': '对齐引擎',
  'res.plddtProfile': '逐残基 pLDDT 曲线',
  'res.plddtNote':
    '灰色线为 WT，黑色线为突变体；红色标记为突变位置。' +
    '突变窗口内的置信度下降常常先于真实的结构变化',
  'res.sequences': '序列',
  'res.badge.stable': '稳定',
  'res.badge.moderate': '中等',
  'res.badge.critical': '严重',
  'res.help.q': '这是什么意思？',
  'res.localRmsd': 'Local RMSD（{a}–{b}）',
  'res.xaxis.residue': '残基序号',
  'res.trace.mutation': '突变',

  'help.global.title': 'Global RMSD',
  'help.global': [
    '最佳叠合（Kabsch 算法）后，**整个蛋白**中原子的平均"偏移"：成对 CA 原子之间的距离先平方、' +
    '再平均、最后取平方根。单位为埃（1 Å = 0.1 纳米 ≈ 原子尺寸）。',
    '参考值：0.2 Å——两个结构几乎一致；1–2 Å——明显的局部变化；超过 5 Å——不同的折叠方式。',
    '**为什么它不是主要指标：**全局 RMSD 对整个蛋白取平均，包括末端和环区，而模型绘制这些区域时' +
    '带有少量噪声。点突变的影响在其中被淹没——因此要看 local RMSD。',
  ],
  'help.local.title': 'Local RMSD（±10 残基窗口）',
  'help.local': [
    '同样的测量，但**只在突变位点 ±10 个残基的窗口内**。这是主要指标：它问的不是' +
    '"蛋白是否整体改变"，而是"蛋白在事件发生处是否改变"。',
    '判定阈值：小于 1 Å——"稳定"；1–2 Å——"中等"；2 Å 及以上——"严重"。',
    '**诚实的说明：**OmegaFold 几乎是确定性的——在稳定折叠上，点突变只带来亚埃级的偏移' +
    '（泛素：I44A 0.21 Å、I3L 0.28 Å、P19G 0.72 Å）。因此应在突变**彼此之间**比较，' +
    '而不是对照绝对阈值。',
  ],
  'help.tm.title': 'TM-score',
  'help.tm': [
    '衡量**全局折叠**是否一致（架构：螺旋和折叠片是否各就其位）的指标，按蛋白长度归一化。' +
    '范围 0–1。',
    '大于 0.9——同一折叠；0.5–0.9——可辨认但已变形；小于 0.5——两个结构折叠方式不同' +
    '（对点突变来说，这是令人担忧且几乎不可能出现的结果）。',
    '与 RMSD 不同，TM-score 不随蛋白长度增长——因此可用它比较不同大小的结构。',
  ],
  'help.plddt.title': 'pLDDT WT / mut',
  'help.plddt': [
    '**pLDDT** —— 神经网络对每个残基的自评置信度，0–100："我有多确信这一段就是这样折叠的"。' +
    '这里显示的是 WT 和突变体在整个结构上的平均值。',
    '数值很低（低于 60）是"模型在臆造，不要相信这张图"的信号。' +
    '对于泛素这类被充分研究的蛋白，pLDDT 通常在 90 以上。',
  ],
  'help.dplddt.title': 'ΔpLDDT',
  'help.dplddt': [
    '模型置信度的变化：**突变体 pLDDT − WT pLDDT**。',
    '为负——模型对突变体结构**更不确定**：突变落入了结构上重要的区域。' +
    '为正——突变使该区域"更有序"。对稳定蛋白而言，通常在 ±1–2 以内。',
    '在 OmegaFold 中，pLDDT 的下降常常先于真实的结构变化出现——这是一个有用的早期信号。',
  ],
  'help.ensemble.title': '突变强度旋钮',
  'help.ensemble': [
    '这里"效应强度"以**响应的分布**来度量，而不是用眼睛比较两张图。旋钮不是生成一个突变体，' +
    '而是生成 **K 个变体**：每个变体都在锚定位点带有替换（μ>1 时另加随机位点的背景替换），' +
    '替换本身按 **Grantham** 矩阵以温度 τ（保守 ↔ 激进）抽取。',
    '直方图展示所有变体的 local RMSD 与 |ΔpLDDT| 分布；中位数与 IQR 是其概括。' +
    '等级徽章："安静位点"（两个中位数均 < 1）、"强"（任一 ≥ 2），否则为"中等"。' +
    '离散度宽度 = local RMSD 的 IQR/中位数。',
    '**诚实层级：**局部 ΔpLDDT > local RMSD > global RMSD > TM——不用任何虚构的 0–100 评分。' +
    '位点之间只能在比较集合内按百分位比较：每个窗口都有各自的模型噪声底。',
  ],

  'scan.h.mutation': '突变',
  'scan.h.local': 'local RMSD，Å',
  'scan.h.global': 'global',
  'scan.h.tm': 'TM',
  'scan.h.dplddt': 'ΔpLDDT',
  'scan.h.verdict': '判定',
  'scan.strongest': '← 最强',
  'scan.rowTitle': '在三维查看器中显示叠合',
  'scan.v.stable': '稳定',
  'scan.v.moderate': '中等',
  'scan.v.critical': '严重',
  'scan.note':
    '表格按 local RMSD 排序（突变位点 ±10 残基窗口）；' +
    '点击行可将该突变体结构叠合到 WT 上',
  'scan.xaxis.subst': '替换 {wt} → X',

  'ens.exhaustiveNote': '「全部 19 种替换」模式——「位点扫描」的严格超集（μ=1，K=19）',
  'ens.seedLabel': '种子',
  'ens.level.quiet': '安静位点',
  'ens.level.moderate': '中等敏感性',
  'ens.level.strong': '强敏感性',
  'ens.width.label': '离散度',
  'ens.width.narrow': '离散度小',
  'ens.width.moderate': '离散度中',
  'ens.width.wide': '离散度大',
  'ens.help.q': '旋钮测量什么？',
  'ens.card.medLocal': 'local RMSD 中位数',
  'ens.card.iqr': 'IQR {v} Å',
  'ens.card.medDplddt': '窗口 |ΔpLDDT| 中位数',
  'ens.card.dplddtUnit': 'pLDDT 点',
  'ens.card.range': 'local RMSD 范围',
  'ens.card.k': '变体',
  'ens.card.spread': 'iqr/median {v}',
  'ens.hist.localTitle': '组合内 local RMSD 分布',
  'ens.hist.dplddtTitle': '窗口 |ΔpLDDT| 分布',
  'ens.hist.xaxisLocal': 'local RMSD，Å',
  'ens.hist.xaxisDplddt': '窗口 |ΔpLDDT|',
  'ens.hist.yaxis': '变体数',
  'ens.h.dplddtLocal': '窗口 ΔpLDDT',
  'ens.note':
    '表格按 local RMSD 排序；点击行可将该变体（ens_XX.pdb）叠合到 WT 上；' +
    'ΔpLDDT 为全蛋白平均，窗口 ΔpLDDT 为锚点 ±10 窗口平均',

  'sens.title': '位点敏感性（同一蛋白的组合）',
  'sens.h.position': '位置',
  'sens.h.medLocal': '中位 local RMSD',
  'sens.h.medDplddt': '中位 |ΔpLDDT|',
  'sens.h.sensitivity': '敏感性',
  'sens.note':
    '仅包含已运行过组合的位点；「敏感性」为比较集合内的百分位（local RMSD 与 |ΔpLDDT| 排名的均值），' +
    '旁边是原始中位数：每个窗口都有自己的模型噪声底，绝对数值不能直接比较',

  'hist.title': '历史',
  'hist.refresh': '刷新',
  'hist.empty': '暂无任务',
  'hist.kind.predict': '预测',
  'hist.kind.mutate': '突变',
  'hist.kind.scan': '扫描',
  'hist.kind.ensemble': '组合',
  'hist.restoreHint': '点击以恢复结果',
  'hist.noResult': '无结果',
  'hist.error': '错误',
  'hist.prediction': '预测 · {label}',

  'viewer.hint': '左键——旋转 · 滚轮——缩放 · 右键——平移',
  'viewer.empty': '运行预测后即可查看结构',
  'viewer.legendWt': 'WT（半透明）',
  'viewer.legendMut': '突变体',
  'viewer.legendMutation': '突变 {pos}',

  'tr.nucleotides': '**{n}** 个核苷酸',
  'tr.aaToStop': '**{n}** 个氨基酸（至终止密码子）',
  'tr.orfStart': '翻译从第 **{n}** 个核苷酸开始',
  'tr.useProtein': '→ 使用该蛋白（{n} aa）',
  'tr.tooShort': '蛋白过短（至少 10 个残基）',
  'tr.sendToWorkspace': '将蛋白发送到工作区',
  'tr.stop': '终止',
  'tr.codonTitle': '密码子 {i}：{codon} → {aa}',
  'tr.shownFirst': '仅显示前 {n}/{m} 个密码子——蛋白质按其翻译',
  'tr.proteinSeq': '蛋白序列（可复制）：',

  'cmp.title': '同一蛋白的多突变比较',
  'cmp.note':
    '由同一 WT 序列的历史运行汇总而来；按 local RMSD 排序——响应最大的区域在上面，' +
    '最小的在下面',

  'bench.inference': '推理：CPU 与 GPU',
  'bench.repeats': '重复次数（丢弃 2 次预热）',
  'bench.busy': '计算中…',
  'bench.runBenchmark': '运行基准测试',
  'bench.kernels': 'Kabsch 核：numpy / C++ / CUDA',
  'bench.pairs': '配对数（B）',
  'bench.atoms': '原子数（N）',
  'bench.runKernel': '运行核测试',
  'bench.xaxis.length': '长度（aa）',
  'bench.yaxis.latency': '延迟，秒（median±IQR/2）',
  'bench.yaxis.ms': '毫秒（median±IQR/2）',
  'bench.kernelInfo': '{pairs} 对 × {atoms} 原子',

  'pv.title': '蛋白浏览器',
  'pv.whole': '整个蛋白',
  'pv.window': '窗口 ±50',
  'pv.toMutation': '跳到突变',
  'pv.empty':
    '输入序列或运行任务——坐标轴上会出现序列、pLDDT、突变位点和扫描结果。',
  'pv.plddtNoData': '无数据——请运行「WT + 突变体」',
  'pv.scanNoData': '无数据——请运行「位点扫描」',
  'pv.variantsNoData': '无数据——请运行「组合」',
  'pv.variantsHeat': '组合：平均 |ΔpLDDT| {v}',
  'pv.ensAnchor': '组合锚定位点',
  'pv.uniprotPlaceholder': 'UniProt 注释——阶段 1.3',
  'pv.pos': '位置 {pos}：{aa}',
  'pv.mutation': '突变 {m}',
  'pv.inLocalWindow': '位于 local RMSD 窗口 {a}–{b} 内',
  'pv.scanWorst': '扫描：ΔpLDDT 最差——{list}',

  'track.sequence': '序列',
  'track.plddt': 'pLDDT（WT）',
  'track.mutation': '突变',
  'track.scan': '位点扫描（19 替换）',
  'track.domains': 'UniProt 结构域',
  'track.variants': '敏感性（组合）',

  // 敏感性图谱 / 「风向玫瑰」（dum.md §5）
  'run.map': '图谱（玫瑰）',
  'run.mapTitle':
    '敏感性图谱：区间位点 × 19 种替换——每个位点一个响应向量；' +
    '最昂贵的任务（每个位点 19 次折叠）',
  'run.stage.map': '图谱',
  'run.mapRange': '图谱位点',
  'run.mapCount': '{n} 位点 × 19 = {folds} 次折叠',
  'ws.mapTitle': '敏感性图谱——{n} 个位点 × 19 种替换',
  'hist.kind.map': '图谱',
  'viewer.legendSensitivity': '敏感性（0–1）',

  'map.metricLabel': '3D 着色标量：',
  'map.metric.vmax': 'max local RMSD',
  'map.metric.vmed': 'local RMSD 中位数',
  'map.paint': '着色 3D',
  'map.paintTitle': '按所选标量的百分位为 WT 结构着色',
  'map.clearPaint': '清除着色',
  'map.painted': '3D 已着色：{metric}（蛋白内百分位）',
  'map.csv': 'CSV（数据集）',
  'map.json': 'JSON',
  'map.heatmap': '热图：位点 × 罗盘方向（颜色 = |ΔpLDDT| 百分位）',
  'map.heatTip': '{m} · |ΔpLDDT| 百分位 {pctl} · RMSD {rmsd} Å',
  'map.heatLegend': '越热越脆弱',
  'map.h.pos': '位点',
  'map.h.rose': '玫瑰',
  'map.h.quadrant': '象限',
  'map.h.max': 'max local RMSD，Å',
  'map.h.med': 'local RMSD 中位数，Å',
  'map.h.pctl': '百分位',
  'map.roseTitle': '位点 {m} 的玫瑰',
  'map.detailTitle': '位点 {m} 的玫瑰',
  'map.detailMax': 'max local RMSD {v} Å',
  'map.detailMed': '中位数 {v} Å',
  'map.detailSharp': '尖锐度 {v}',
  'map.lenChannel': '花瓣长度——蛋白内 |ΔpLDDT| 百分位',
  'map.colorChannel': '颜色——位点内 local RMSD 百分位',
  'map.petalTip': '{m} · |ΔpLDDT| 百分位 {pctl} · RMSD {rmsd} Å',
  'map.quad.hedgehog': '海胆',
  'map.quad.needle': '尖针',
  'map.quad.disk': '圆盘',
  'map.quad.clover': '三叶草',
  'map.quad.hedgehogTitle': '任何替换都致伤',
  'map.quad.needleTitle': '仅一个化学方向致伤',
  'map.quad.diskTitle': '耐受位点',
  'map.quad.cloverTitle': '强烈但破碎——几片亮花瓣',
  'map.note':
    '长度与颜色均为百分位（蛋白内 / 位点内）：不同窗口的绝对数值不可直接比较；' +
    '点击行查看大玫瑰；CSV 正是未来数据集的行（每个位点 × 替换一行）',
}