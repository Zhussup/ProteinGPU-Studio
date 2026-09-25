// Тонкий API-клиент. Все запросы идут через Vite dev-прокси (/api → :8000).
// Эндпоинты, чьи ответы несут сгенерированный бэкендом текст, принимают ?lang=,
// чтобы текст приходил на активном языке UI (currentLang() читает localStorage).
// 轻量 API 客户端。所有请求经 Vite 开发代理（/api → :8000）。
// 返回后端生成文本的端点带 ?lang=，使文本以当前 UI 语言返回
//（currentLang() 读取 localStorage）。
import { currentLang } from '../i18n'
import type {
  GpuInfo, InferenceProfile, JobStatus, JobSummary, MutationResult,
  PredictResponse, Preset, TranslateResponse,
} from './types'

// имена артефактов, отдаваемые GET /api/v1/files/{job_id}/{fn}
// GET /api/v1/files/{job_id}/{fn} 提供的工件名称
export type MapArtifact = 'scan_map.json' | 'scan_map.csv' | 'scan_map_partial.json'

function withLang(url: string): string {
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}lang=${currentLang()}`
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* оставляем statusText */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => fetch('/api/v1/health').then((r) => json<{ status: string }>(r)),
  gpu: () => fetch(withLang('/api/v1/system/gpu')).then((r) => json<GpuInfo>(r)),
  presets: () =>
    fetch(withLang('/api/v1/system/presets')).then((r) => json<{ presets: Preset[] }>(r)),

  submitPredict: (sequence: string, profile?: InferenceProfile) =>
    fetch(withLang('/api/v1/predict'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence, profile }),
    }).then((r) => json<PredictResponse>(r)),

  submitMutate: (sequence: string, position: number, mutant_aa: string, profile?: InferenceProfile) =>
    fetch(withLang('/api/v1/mutate'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence, position, mutant_aa, profile }),
    }).then((r) => json<MutationResult>(r)),

  submitScan: (sequence: string, position: number, profile?: InferenceProfile) =>
    fetch(withLang('/api/v1/scan'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence, position, profile }),
    }).then((r) => json<{ job_id: string; status: string }>(r)),

  // positions: null → каждая позиция последовательности (дорого: 19 фолдов каждая)
  // positions: null → 序列的每个位置（代价高：每个位置 19 次折叠）
  submitScanMap: (sequence: string, positions: number[] | null, profile?: InferenceProfile) =>
    fetch(withLang('/api/v1/scan_map'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence, positions, profile }),
    }).then((r) => json<{ job_id: string; status: string }>(r)),

  mapArtifact: async (jobId: string, fn: MapArtifact) => {
    const res = await fetch(`/api/v1/files/${jobId}/${fn}`)
    if (!res.ok) throw new Error(`${res.status}: artifact fetch failed`)
    return res.text()
  },

  submitEnsemble: (
    sequence: string, position: number, mode: 'sampled' | 'exhaustive',
    mu: number, tau: number, k: number, seed: number | null,
    profile?: InferenceProfile,
  ) =>
    fetch(withLang('/api/v1/ensemble'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sequence, position, mode, mu, tau, k,
        seed: seed ?? undefined, profile,
      }),
    }).then((r) => json<{ job_id: string; status: string }>(r)),

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

  jobs: (limit = 20) =>
    fetch(`/api/v1/jobs?limit=${limit}`).then((r) => json<JobSummary[]>(r)),

  translate: (fasta: string) =>
    fetch(withLang('/api/v1/translate'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fasta }),
    }).then((r) => json<TranslateResponse>(r)),

  result: (jobId: string) =>
    fetch(withLang(`/api/v1/jobs/${jobId}/result`)).then((r) =>
      json<Record<string, unknown>>(r)),

  pdb: async (jobId: string, fn: 'wt.pdb' | 'mut.pdb' | 'mut_aligned.pdb' | `scan_${string}.pdb` | `ens_${string}.pdb`) => {
    const res = await fetch(`/api/v1/files/${jobId}/${fn}`)
    if (!res.ok) throw new Error(`${res.status}: PDB fetch failed`)
    return res.text()
  },
}