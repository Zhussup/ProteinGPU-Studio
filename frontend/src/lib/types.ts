// Общие типы API, зеркалящие backend/app/schemas.py
// 与 backend/app/schemas.py 对应的共享 API 类型
export type InferenceProfile = 'auto' | 'fp32-gpu' | 'fp16-gpu' | 'cpu' | 'dummy'

export interface RmsdResult {
  global_rmsd: number
  local_rmsd: number
  local_window: [number, number]
  tm_score: number
  plddt_wt: number
  plddt_mut: number
  interpretation: 'stable' | 'moderate' | 'critical'
  engine: string
}

export interface MutationResult {
  job_id: string
  status: string
  wt_sequence: string
  mutant_sequence: string
  position: number
  wt_aa: string
  mutant_aa: string
  model?: string
  rmsd?: RmsdResult
  summary?: string
  plddt_wt_list?: number[]
  plddt_mut_list?: number[]
}

// POST /api/v1/scan — все 19 замен в одной позиции
// POST /api/v1/scan —— 单个位点的全部 19 种替换
export interface ScanRow {
  mut_aa: string
  local_rmsd: number
  global_rmsd: number
  tm_score: number
  plddt_mut: number
  dplddt: number
  engine: string
  interpretation: 'stable' | 'moderate' | 'critical'
}

export interface ScanResult {
  wt_sequence: string
  position: number
  wt_aa: string
  model?: string
  wt_from_cache?: boolean
  rows: ScanRow[]
  plddt_wt?: number
  best: string
  summary: string
}

// POST /api/v1/ensemble — диск силы мутагенеза: K вариантов вокруг одной
// позиции-якоря (μ одновременных замен, спектр Грантэма/τ); чувствительность
// позиции = РАСПРЕДЕЛЕНИЕ откликов, а не две картинки.
// POST /api/v1/ensemble —— 突变强度拨盘：围绕一个锚定位点的 K 个变体
//（μ 个同时替换，Grantham/τ 谱）；位点的敏感性 = 响应的分布，而非两张图。
export interface EnsembleMutation {
  position: number
  wt_aa: string
  mut_aa: string
}

export interface EnsembleRow {
  label: string // "I44A" | "I44A+L3M"
  mutations: EnsembleMutation[]
  mut_aa: string | null // только μ=1 — паритет со ScanRow | 仅 μ=1——与 ScanRow 对齐
  local_rmsd: number
  global_rmsd: number
  tm_score: number
  plddt_mut: number
  dplddt: number
  dplddt_local: number // среднее ΔpLDDT по окну якоря (честная метрика) | 锚点窗口内的 ΔpLDDT 均值（诚实指标）
  engine: string
  interpretation: 'stable' | 'moderate' | 'critical'
  pdb_file: string // "ens_XX.pdb", выровнено по Kabsch к системе WT | "ens_XX.pdb"，已按 Kabsch 对齐到 WT 坐标系
}

export interface StatsBlock {
  mean: number
  std: number
  median: number
  iqr: number
  min: number
  max: number
}

export interface EnsembleHeadline {
  level: 'quiet' | 'moderate' | 'strong'
  width: 'narrow' | 'moderate' | 'wide'
  iqr_ratio: number
  median_local_rmsd: number
  median_abs_dplddt_local: number
}

export interface EnsembleResult {
  wt_sequence: string
  position: number
  wt_aa: string
  model?: string
  wt_from_cache?: boolean
  mode: 'sampled' | 'exhaustive'
  params: { mu: number; tau: number; k: number; seed: number }
  variants: EnsembleRow[] // сильнейшие первыми (local_rmsd по убыванию) | 最强优先（local_rmsd 降序）
  stats: { local_rmsd: StatsBlock; dplddt: StatsBlock; dplddt_local: StatsBlock }
  headline: EnsembleHeadline
  dplddt_abs_mean_list: number[] // среднее |ΔpLDDT| по остаткам — трек вьюера | 逐残基平均 |ΔpLDDT|——查看器轨道
  plddt_wt?: number
  plddt_wt_list?: number[]
  best: number
  summary: string
  pdb_files?: string[]
}

export interface PredictResponse {
  job_id: string
  status: string
  length: number
}

// POST /api/v1/scan_map — карта чувствительности / «роза ветров» (dum.md §5):
// каждая позиция характеризуется 19-вектором структурных откликов. Скаляр из
// вектора раскрашивает 3D-вид; сам вектор рисуется лепестковой розой;
// одна строка = одна строка будущего DMS-датасета.
// POST /api/v1/scan_map —— 敏感性图谱 / “风玫瑰”（dum.md §5）：
// 每个位置由 19 维结构响应向量刻画。标量给 3D 视图着色；向量本身
// 画成玫瑰花瓣；一行 = 未来 DMS 数据集的一行。
export interface MapRow {
  mut_aa: string
  grantham: number
  local_rmsd: number
  global_rmsd: number
  tm_score: number
  plddt_mut: number
  dplddt: number
  dplddt_local: number
  abs_dplddt_local: number
  pctl: number // ранг abs_dplddt_local среди откликов белка | abs_dplddt_local 在蛋白响应中的排名
  engine: string
  interpretation: 'stable' | 'moderate' | 'critical'
}

export interface MapStats {
  median_local_rmsd: number
  max_local_rmsd: number
  mean_local_rmsd: number
  median_abs_dplddt_local: number
  sharpness: number
  quadrant: 'hedgehog' | 'needle' | 'disk' | 'clover'
  pctl_v_max: number // внутрибелковый перцентиль max_local_rmsd | max_local_rmsd 的蛋白内百分位
  pctl_v_med: number // внутрибелковый перцентиль median_local_rmsd | median_local_rmsd 的蛋白内百分位
}

export interface MapPosition {
  pos: number
  wt_aa: string
  rows: MapRow[]
  stats: MapStats
}

export interface ScanMapResult {
  wt_sequence: string
  model?: string
  wt_from_cache?: boolean
  n_positions: number
  n_folds: number
  plddt_wt?: number
  plddt_wt_list?: number[]
  petal_dirs: string
  positions: MapPosition[]
  summary: string
  pdb_files?: string[]
  artifact_files?: string[]
}

export interface JobStatus {
  job_id: string
  kind: string
  status: 'queued' | 'running' | 'done' | 'error'
  progress: number
  message?: string | null
  error?: string | null
  created_at: string
  finished_at?: string | null
}

// Одна строка панели истории (GET /api/v1/jobs)
// 历史面板的一行（GET /api/v1/jobs）
export interface JobSummary {
  job_id: string
  kind: string
  status: 'queued' | 'running' | 'done' | 'error'
  label: string
  sequence: string
  position?: number | null
  mutant_aa?: string | null
  // параметры диска (ensemble-задачи; в остальных null)
  // 拨盘参数（ensemble 任务；其余为 null）
  mu?: number | null
  tau?: number | null
  k?: number | null
  mode?: string | null
  error?: string | null
  created_at: string
  finished_at?: string | null
}

export interface BenchmarkRow {
  profile: string
  length: number
  wall_median_s: number
  wall_iqr_s: number
  vram_peak_mb?: number | null
  repeats: number
}

export interface KernelRow {
  engine: string
  pairs: number
  atoms: number
  wall_median_s: number
  wall_iqr_s: number
}

export interface Preset {
  id: string
  name: string
  sequence: string
  description: string
  position?: number
  mutant_aa?: string
}

export interface GpuInfo {
  available: boolean
  name?: string
  capability?: string
  vram_total_mb?: number
  vram_free_mb?: number
  reason?: string
}

export interface PdbPayload {
  wt?: string
  mut?: string
  mutAligned?: string
}

// GET /api/v1/translate — ДНК FASTA → кодоны → аминокислоты
// GET /api/v1/translate —— DNA FASTA → 密码子 → 氨基酸
export interface Codon {
  index: number
  codon: string
  aa: string // однобуквенная АК, "*" = стоп | 单字母氨基酸，"*" 表示终止
}

export interface TranslateResponse {
  dna: string
  protein: string
  orf_start: number
  codons: Codon[]
  warnings: string[]
}