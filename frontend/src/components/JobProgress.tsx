// JobProgress: честный прогресс задачи — один сегмент на реальный этап
// конвейера бэкенда (progress скачками + message), живой таймер и отмена.
// Без интерполяции и выдуманных процентов. Два вида: full (на странице анализа)
// и mini (полоса в сайдбаре — видна с любой страницы).
// JobProgress：诚实的任务进度——后端流水线每个真实阶段一段
//（progress 跳跃 + message），实时计时与取消。无插值、无编造百分比。
// 两种形态：full（分析页内）与 mini（侧栏横条——任意页面可见）。
import { useEffect, useState } from 'react'
import type { JobStatus } from '../lib/types'
import { useI18n, type Key } from '../i18n'

// Пороги этапов зеркалят значения progress из backend/app/routers/predict.py.
// Подписи берутся из словаря (строятся на каждый рендер, см. buildStages ниже).
// 阶段阈值与 backend/app/routers/predict.py 的 progress 值保持一致。
// 标签取自字典（每次渲染时构建，见下方 buildStages）。
const STAGE_KEYS: Record<string, { at: number; label: Key }[]> = {
  predict: [
    { at: 0.05, label: 'run.stage.model' },
    { at: 0.9, label: 'run.stage.pdb' },
  ],
  mutate: [
    { at: 0.1, label: 'run.stage.wt' },
    { at: 0.5, label: 'run.stage.mutant' },
    { at: 0.85, label: 'run.stage.align' },
    { at: 0.95, label: 'run.stage.metrics' },
  ],
  scan: [
    { at: 0.1, label: 'run.stage.wt' },
    { at: 0.9, label: 'run.stage.subs19' },
    { at: 0.95, label: 'run.stage.summary' },
  ],
  ensemble: [
    { at: 0.1, label: 'run.stage.wt' },
    { at: 0.9, label: 'run.stage.ens' },
    { at: 0.95, label: 'run.stage.summary' },
  ],
  map: [
    { at: 0.05, label: 'run.stage.wt' },
    { at: 0.9, label: 'run.stage.map' },
    { at: 0.99, label: 'run.stage.summary' },
  ],
  plm_screen: [
    { at: 0.35, label: 'run.stage.plm' },
    { at: 0.5, label: 'run.stage.wt' },
    { at: 0.95, label: 'run.stage.plmFolds' },
    { at: 0.99, label: 'run.stage.summary' },
  ],
}

// 'run.stage.pdb' / 'run.stage.wt' не зависят от языка, но тип Dict требует,
// чтобы каждый ключ существовал во всех трёх локалях — поэтому они и там.
// 'run.stage.pdb' / 'run.stage.wt' 与语言无关，但 Dict 类型要求
// 每个键在三种语言中都存在——所以它们也在那里。
function buildStages(t: (k: Key) => string): Record<string, { at: number; label: string }[]> {
  return Object.fromEntries(
    Object.entries(STAGE_KEYS).map(([kind, stages]) => [
      kind,
      stages.map((st) => ({ at: st.at, label: t(st.label) })),
    ]),
  )
}

function fmtElapsed(s: number): string {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${String(sec).padStart(2, '0')}`
}

export interface JobProgressProps {
  status: JobStatus | null
  error: string | null
  running: boolean
  onCancel: () => void
  // mini — полоса в сайдбаре без подписей этапов
  // mini——侧栏横条，无阶段标签
  variant?: 'full' | 'mini'
}

export default function JobProgress({
  status, error, running, onCancel, variant = 'full',
}: JobProgressProps) {
  const { t } = useI18n()
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

  const stages = status ? (buildStages(t)[status.kind] ?? []) : []
  const progress = status?.progress ?? 0
  const label = status?.status === 'queued'
    ? (status.message ?? t('run.queued'))
    : (status?.message ?? t('run.running'))

  if (variant === 'mini') {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-[11px] text-neutral-600">
          <span className="stage-active inline-block h-2 w-2 shrink-0 bg-neutral-400" />
          <span className="min-w-0 flex-1 truncate">{label}</span>
          <span className="mono shrink-0 text-neutral-500">{fmtElapsed(elapsed)}</span>
        </div>
        <div className="h-1 w-full border border-neutral-300 bg-white">
          <div className="h-full bg-neutral-900 transition-all" style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="border border-neutral-300 px-1.5 py-0.5 text-[10px] text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
        >
          {t('run.cancel')}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {running && (
        <div className="space-y-1.5 border border-neutral-200 p-3" data-demo="progress">
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="text-neutral-700">{label}</span>
            <span className="flex shrink-0 items-center gap-2">
              <span className="mono text-neutral-500">{fmtElapsed(elapsed)}</span>
              <button
                type="button"
                onClick={onCancel}
                className="border border-neutral-300 px-1.5 py-0.5 text-[10px] text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
              >
                {t('run.cancel')}
              </button>
            </span>
          </div>

          {/* один сегмент на реальный этап конвейера */}
          {/* 每个真实流水线阶段一段 */}
          <div className="flex gap-1">
            {stages.map((st) => {
              const passed = progress >= st.at && status?.status !== 'queued'
              const active = !passed && status?.status === 'running' && progress < st.at
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

          <div className="text-[10px] text-neutral-400">{t('run.progressNote')}</div>
        </div>
      )}

      {status?.status === 'cancelled' && (
        <div className="border border-neutral-300 bg-neutral-50 px-3 py-2 text-xs text-neutral-600">
          {t('run.cancelled')}
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
