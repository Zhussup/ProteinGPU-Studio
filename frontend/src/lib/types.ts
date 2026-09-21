// Shared API types mirroring backend/app/schemas.py
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

// POST /api/v1/scan — all 19 substitutions at one position
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

// POST /api/v1/ensemble — the mutagenesis-strength dial: K variants around one
// anchor position (μ simultaneous substitutions, Grantham/τ spectrum); the
// position's sensitivity = the DISTRIBUTION of responses, not two pictures.
export interface EnsembleMutation {
  position: number
  wt_aa: string
  mut_aa: string
}

export interface EnsembleRow {
  label: string // "I44A" | "I44A+L3M"
  mutations: EnsembleMutation[]
  mut_aa: string | null // μ=1 only — parity with ScanRow
  local_rmsd: number
  global_rmsd: number
  tm_score: number
  plddt_mut: number
  dplddt: number
  dplddt_local: number // mean ΔpLDDT over the anchor window (honest metric)
  engine: string
  interpretation: 'stable' | 'moderate' | 'critical'
  pdb_file: string // "ens_XX.pdb", Kabsch-aligned to the WT frame
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
  variants: EnsembleRow[] // strongest first (local_rmsd desc)
  stats: { local_rmsd: StatsBlock; dplddt: StatsBlock; dplddt_local: StatsBlock }
  headline: EnsembleHeadline
  dplddt_abs_mean_list: number[] // per-residue mean |ΔpLDDT| — the viewer track
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

// One row of the history panel (GET /api/v1/jobs)
export interface JobSummary {
  job_id: string
  kind: string
  status: 'queued' | 'running' | 'done' | 'error'
  label: string
  sequence: string
  position?: number | null
  mutant_aa?: string | null
  // dial params (ensemble jobs; null elsewhere)
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

// GET /api/v1/translate — DNA FASTA → codons → amino acids
export interface Codon {
  index: number
  codon: string
  aa: string // one-letter AA, "*" = stop
}

export interface TranslateResponse {
  dna: string
  protein: string
  orf_start: number
  codons: Codon[]
  warnings: string[]
}