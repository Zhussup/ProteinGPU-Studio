// Shared API types mirroring backend/app/schemas.py

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