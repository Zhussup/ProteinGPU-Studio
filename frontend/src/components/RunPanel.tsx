// RunPanel: run buttons (WT only / WT+мутант), progress bar, GPU badge.
import type { JobStatus, GpuInfo } from '../lib/types'

export interface RunPanelProps {
  canRun: boolean
  running: boolean
  status: JobStatus | null
  error: string | null
  gpu: GpuInfo | null
  onRunPredict: () => void
  onRunMutate: () => void
  onReset: () => void
}

export default function RunPanel({
  canRun, running, status, error, gpu, onRunPredict, onRunMutate, onReset,
}: RunPanelProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onRunPredict}
          disabled={!canRun || running}
          className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 disabled:opacity-40"
        >
          Только WT
        </button>
        <button
          onClick={onRunMutate}
          disabled={!canRun || running}
          className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-cyan-600 disabled:opacity-40"
        >
          WT + мутант
        </button>
        {!running && status && (
          <button onClick={onReset} className="text-xs text-slate-500 underline hover:text-slate-300">
            сброс
          </button>
        )}
        {gpu && (
          <span className={`ml-auto rounded-full px-2 py-0.5 text-xs ${gpu.available ? 'bg-emerald-900/50 text-emerald-400' : 'bg-amber-900/40 text-amber-400'}`}>
            {gpu.available ? `GPU: ${gpu.name}` : `CPU-only: ${gpu.reason ?? 'нет CUDA'}`}
          </span>
        )}
      </div>

      {running && (
        <div className="space-y-1">
          <div className="h-1.5 overflow-hidden rounded bg-slate-800">
            <div
              className="h-full bg-cyan-500 transition-all duration-500"
              style={{ width: `${Math.round((status?.progress ?? 0) * 100)}%` }}
            />
          </div>
          <div className="text-xs text-slate-500">
            {status?.status === 'queued' ? 'в очереди…' : status?.message ?? 'выполняется…'}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}
    </div>
  )
}