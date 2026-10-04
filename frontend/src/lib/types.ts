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

// POST /api/v1/ensemble — ручка силы мутагенеза: K вариантов вокруг одной
// позиции-якоря (μ одновременных замен, спектр Грантэма/τ); чувствительность
// позиции = РАСПРЕДЕЛЕНИЕ откликов, а не две картинки.
// POST /api/v1/ensemble —— 突变强度旋钮：围绕一个锚定位点的 K 个变体
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

// POST /api/v1/plm_screen — скрин всего белка из ОДНОГО forward-прохода PLM
// (zero-shot WT-margin): все 19×L замен с log-margin'ом, затем опциональное
// дофолдингом top-K самых повреждающих замен на позицию. Ключи совпадают с
// scan_map (rose/pctl/Paint 3D переиспользуются), структурные колонки есть
// только у сфолднутых строк.
// POST /api/v1/plm_screen —— 全蛋白筛选：一次 PLM 前向得到全部 19×L 替换的
// zero-shot WT-margin，随后可选地折叠每位置 top-K 最损伤替换。
// 键名与 scan_map 一致（rose/pctl/Paint 3D 复用），仅折叠行有结构列。
export interface PlmRow {
  mut_aa: string
  grantham: number
  sector: string
  plm_margin: number
  plm_logprob_alt: number
  plm_logprob_wt: number
  plm_damage: number
  pctl: number // ранг plm_damage среди замен белка | plm_damage 在蛋白替换中的排名
  // только у сфолднутых строк | 仅折叠行存在
  local_rmsd?: number
  global_rmsd?: number
  tm_score?: number
  plddt_mut?: number
  dplddt?: number
  dplddt_local?: number
  abs_dplddt_local?: number
  engine?: string
}

export interface PlmStats {
  plm_v_med: number
  plm_v_max: number
  plm_v_mean: number
  logprob_wt: number
  pctl_v_max: number
  pctl_v_med: number
}

export interface PlmPosition {
  pos: number
  wt_aa: string
  rows: PlmRow[]
  stats: PlmStats
}

export interface PlmScreenResult {
  kind: 'plm_screen'
  wt_sequence: string
  model?: string
  wt_from_cache?: boolean
  plm_scorer: string // "omegaplm-tied" | "dummy-plm" — честный ярлык скорера
  n_positions: number
  n_folds: number
  plm: { elapsed_s: number; device: string; n_forward: number }
  petal_dirs: string
  positions: PlmPosition[]
  plddt_wt?: number
  plddt_wt_list?: number[]
  folds: { planned: number; done: number; consistency_spearman: number | null }
  summary: string
  pdb_files?: string[]
  artifact_files?: string[]
}

// -- DMS-валидация против ProteinGym (вкладка «Валидация») -----------------
// -- 针对 ProteinGym 的 DMS 验证（“验证”标签页）---------------------------------
export interface DmsCorrelation {
  name: 'plm_all' | 'plddt_fold' | 'rmsd_fold' | 'pos_plm' | 'pos_struct_plm' | 'margin_rmsd'
  spearman: number | null
  n: number
  ci: [number, number] | null
  expected_sign: string
}

export interface DmsPerPosition {
  pos: number
  wt_aa: string
  v_med: number // медиана plm_damage позиции | 位置 plm_damage 中位数
  v_med_pctl: number
  mean_fitness_z: number
  n_obs: number
  top1: { mut_aa: string; local_rmsd: number | null; fitness_z: number } | null
}

export interface DmsPoint { x: number; y: number; label: string }

// оговорки приходят как i18n-ключи с параметрами — фронт резолвит t(key, params)
// 说明以带参数的 i18n 键到达——前端按当前语言解析
export interface DmsCaveat { key: string; params?: Record<string, string | number> }

export interface DmsValidationResult {
  kind: 'dms_validation'
  assay_id: string
  dms_meta: { seq_len: number; author_year: string; year: string }
  sequence: string
  model?: string
  plm_scorer: string
  mapping: 'exact-substring' | 'pairwise'
  counts: Record<string, number>
  n_rows: number
  n_positions: number
  assay_center: { mu: number; sd: number }
  correlations: DmsCorrelation[]
  per_position: DmsPerPosition[]
  scatter_plm: DmsPoint[]
  scatter_struct: DmsPoint[]
  caveats: DmsCaveat[]
  summary: string
  wt_from_cache: boolean | null
  pdb_files?: string[]
  artifact_files?: string[]
}

export interface AssayInfo {
  dms_id: string
  seq_len: number
  singles: number
  positions: number
  rows: number
  ok: boolean
}

export interface JobStatus {
  job_id: string
  kind: string
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
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
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
  label: string
  sequence: string
  position?: number | null
  mutant_aa?: string | null
  // параметры ручки (ensemble-задачи; в остальных null)
  // 旋钮参数（ensemble 任务；其余为 null）
  mu?: number | null
  tau?: number | null
  k?: number | null
  mode?: string | null
  // ручка PLM-скрина (plm_screen; в остальных null)
  // PLM 筛查旋钮（plm_screen；其余为 null）
  fold_top_k?: number | null
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