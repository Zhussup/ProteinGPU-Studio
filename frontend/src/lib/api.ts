// Thin API client. All calls go through the Vite dev proxy (/api → :8000).
import type {
  GpuInfo, JobStatus, MutationResult,
  PredictResponse, Preset,
} from './types'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* keep statusText */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => fetch('/api/v1/health').then((r) => json<{ status: string }>(r)),
  gpu: () => fetch('/api/v1/system/gpu').then((r) => json<GpuInfo>(r)),
  presets: () =>
    fetch('/api/v1/system/presets').then((r) => json<{ presets: Preset[] }>(r)),

  submitPredict: (sequence: string) =>
    fetch('/api/v1/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence }),
    }).then((r) => json<PredictResponse>(r)),

  submitMutate: (sequence: string, position: number, mutant_aa: string) =>
    fetch('/api/v1/mutate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence, position, mutant_aa }),
    }).then((r) => json<MutationResult>(r)),

  submitBenchmark: (sequence: string, profiles: string[], repeats = 5, lengths?: number[]) =>
    fetch('/api/v1/benchmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence, profiles, repeats, lengths }),
    }).then((r) => json<{ job_id: string; status: string }>(r)),

  submitKernelBench: (pairs: number, atoms: number, repeats = 9) =>
    fetch(`/api/v1/benchmark/kernels?pairs=${pairs}&atoms=${atoms}&repeats=${repeats}`, {
      method: 'POST',
    }).then((r) => json<{ job_id: string; status: string }>(r)),

  job: (jobId: string) =>
    fetch(`/api/v1/jobs/${jobId}`).then((r) => json<JobStatus>(r)),

  result: (jobId: string) =>
    fetch(`/api/v1/jobs/${jobId}/result`).then((r) =>
      json<Record<string, unknown>>(r)),

  pdb: async (jobId: string, fn: 'wt.pdb' | 'mut.pdb' | 'mut_aligned.pdb') => {
    const res = await fetch(`/api/v1/files/${jobId}/${fn}`)
    if (!res.ok) throw new Error(`${res.status}: PDB fetch failed`)
    return res.text()
  },
}