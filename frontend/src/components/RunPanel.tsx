// RunPanel: run buttons (WT only / WT+мутант), honest stage progress, GPU badge.
//
// The progress bar is deliberately NOT a smooth fake: the backend reports real
// pipeline stages (progress jumps + message via GET /jobs/{id}); we render one
// segment per stage — filled when passed, pulsing while active — plus a live
// elapsed timer. No interpolation, no invented percentages.
import { useEffect, useState } from 'react'
import type { InferenceProfile, JobStatus, GpuInfo } from '../lib/types'

export interface RunPanelProps {
  canRun: boolean
  running: boolean
  status: JobStatus | null
  error: string | null
  gpu: GpuInfo | null
  profile: InferenceProfile
  onProfileChange: (p: InferenceProfile) => void
  onRunPredict: () => void
  onRunMutate: () => void
  onRunScan: () => void
  onReset: () => void
}

// Stage thresholds mirror backend/app/routers/predict.py progress values.
const STAGES: Record<string, { at: number; label: string }[]> = {
  predict: [
    { at: 0.05, label: 'модель' },
    { at: 0.9, label: 'PDB' },
  ],
  mutate: [
    { at: 0.1, label: 'WT' },
    { at: 0.5, label: 'мутант' },
    { at: 0.85, label: 'наложение' },
    { at: 0.95, label: 'метрики' },
  ],
  scan: [
    { at: 0.1, label: 'WT' },
    { at: 0.9, label: '19 замен' },
    { at: 0.95, label: 'итог' },
  ],
}

function fmtElapsed(s: number): string {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${String(sec).padStart(2, '0')}`
}

// Labels for the runtime profile selector (backend _prepare_model semantics).
const PROFILE_OPTIONS: { id: InferenceProfile; label: string }[] = [
  { id: 'auto', label: 'auto — как в конфиге' },
  { id: 'fp32-gpu', label: 'GPU fp32' },
  { id: 'fp16-gpu', label: 'GPU fp16' },
  { id: 'cpu', label: 'CPU' },
  { id: 'dummy', label: 'dummy (тест)' },
]

export default function RunPanel({
  canRun, running, status, error, gpu, profile, onProfileChange,
  onRunPredict, onRunMutate, onRunScan, onReset,
}: RunPanelProps) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!running) {
      setElapsed(0)
      return
    }
    setElapsed(0)
    const t0 = Date.now()
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000)
    return () => clearInterval(iv)
  }, [running, status?.job_id])

  const stages = status ? (STAGES[status.kind] ?? []) : []
  const progress = status?.progress ?? 0

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onRunPredict}
          disabled={!canRun || running}
          className="border border-neutral-300 px-4 py-2 text-sm text-neutral-800 transition hover:border-neutral-900 disabled:opacity-40"
        >
          Только WT
        </button>
        <button
          onClick={onRunMutate}
          disabled={!canRun || running}
          className="bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-40"
        >
          WT + мутант
        </button>
        <button
          onClick={onRunScan}
          disabled={!canRun || running}
          title="все 19 аминокислотных замен в выбранной позиции — ранжированный скрининг"
          className="border border-red-700 px-4 py-2 text-sm text-red-800 transition hover:bg-red-50 disabled:opacity-40"
        >
          Скан позиции (19 мутаций)
        </button>
        {!running && status && (
          <button onClick={onReset} className="text-xs text-neutral-500 underline hover:text-neutral-900">
            сброс
          </button>
        )}
        {gpu && (
          <span className={`mono ml-auto border px-2 py-0.5 text-xs ${
            gpu.available ? 'border-neutral-900 text-neutral-900' : 'border-neutral-300 text-neutral-500'
          }`}>
            {gpu.available ? `GPU: ${gpu.name}` : `CPU-only: ${gpu.reason ?? 'нет CUDA'}`}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-neutral-600">
        <label htmlFor="profile-select">Профиль инференса:</label>
        <select
          id="profile-select"
          value={profile}
          onChange={(e) => onProfileChange(e.target.value as InferenceProfile)}
          disabled={running}
          className="mono border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-900 focus:border-neutral-900"
        >
          {PROFILE_OPTIONS.map((o) => (
            <option key={o.id} value={o.id}>{o.label}</option>
          ))}
        </select>
        <span className="text-[10px] text-neutral-400">
          применяется к следующему запуску; модель перезагружается при смене
        </span>
      </div>

      {running && (
        <div className="space-y-1.5 border border-neutral-200 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-neutral-700">
              {status?.status === 'queued'
                ? (status.message ?? 'в очереди…')
                : (status?.message ?? 'выполняется…')}
            </span>
            <span className="mono text-neutral-500">{fmtElapsed(elapsed)}</span>
          </div>

          {/* one segment per real pipeline stage */}
          <div className="flex gap-1">
            {stages.map((st) => {
              const passed = progress >= st.at && status?.status !== 'queued'
              const active = !passed && status?.status === 'running' &&
                progress < st.at
              return (
                <div key={st.label} className="flex-1">
                  <div className={`h-1.5 border ${
                    passed
                      ? 'border-neutral-900 bg-neutral-900'
                      : active
                        ? 'stage-active border-neutral-900 bg-neutral-400'
                        : 'border-neutral-300 bg-white'
                  }`} />
                  <div className={`mt-1 text-[10px] ${
                    passed ? 'text-neutral-900' : active ? 'text-neutral-700' : 'text-neutral-400'
                  }`}>{st.label}</div>
                </div>
              )
            })}
          </div>

          <div className="text-[10px] text-neutral-400">
            прогресс — по реальным этапам пайплайна, без интерполяции; инференс занимает
            минуты и внутри этапа неразбиваем
          </div>
        </div>
      )}

      {error && (
        <div className="border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
          {error}
        </div>
      )}
    </div>
  )
}