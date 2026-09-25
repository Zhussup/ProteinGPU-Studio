// RunPanel: кнопки запуска (только WT / WT+мутант), честный прогресс этапов, бейдж GPU.
//
// Прогресс-бар намеренно НЕ плавная подделка: бэкенд сообщает реальные этапы
// конвейера (progress скачками + message через GET /jobs/{id}); мы рисуем один
// сегмент на этап — заполнен, когда пройден, пульсирует, когда активен — плюс
// живой таймер прошедшего времени. Без интерполяции, без выдуманных процентов.
// RunPanel：运行按钮（仅 WT / WT+突变体）、诚实的阶段进度、GPU 徽章。
//
// 进度条刻意不做平滑假象：后端报告真实流水线阶段
//（progress 跳跃 + GET /jobs/{id} 的 message）；每个阶段一段——
// 已过则填满，进行中则脉冲——外加实时耗时计时器。
// 无插值，无编造的百分比。
import { useEffect, useState } from 'react'
import type { InferenceProfile, JobStatus, GpuInfo } from '../lib/types'
import { useI18n, type Key } from '../i18n'

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
  onRunEnsemble: () => void
  onRunMap: () => void
  mapFrom: number
  mapTo: number
  seqLen: number
  onMapRangeChange: (from: number, to: number) => void
  onReset: () => void
}

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

// Подписи селектора профиля исполнения (семантика _prepare_model бэкенда).
// 运行配置选择器的标签（后端 _prepare_model 的语义）。
const PROFILE_OPTIONS: { id: InferenceProfile; label: Key }[] = [
  { id: 'auto', label: 'run.auto' },
  { id: 'fp32-gpu', label: 'run.profile.fp32' },
  { id: 'fp16-gpu', label: 'run.profile.fp16' },
  { id: 'cpu', label: 'run.profile.cpu' },
  { id: 'dummy', label: 'run.dummy' },
]

export default function RunPanel({
  canRun, running, status, error, gpu, profile, onProfileChange,
  onRunPredict, onRunMutate, onRunScan, onRunEnsemble, onRunMap,
  mapFrom, mapTo, seqLen, onMapRangeChange, onReset,
}: RunPanelProps) {
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

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2" data-demo="runrow">
        <button
          onClick={onRunPredict}
          disabled={!canRun || running}
          className="border border-neutral-300 px-4 py-2 text-sm text-neutral-800 transition hover:border-neutral-900 disabled:opacity-40"
        >
          {t('run.wtOnly')}
        </button>
        <button
          onClick={onRunMutate}
          disabled={!canRun || running}
          className="bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-neutral-700 disabled:opacity-40"
        >
          {t('run.wtMutant')}
        </button>
        <button
          onClick={onRunScan}
          disabled={!canRun || running}
          title={t('run.scanTitle')}
          className="border border-red-700 px-4 py-2 text-sm text-red-800 transition hover:bg-red-50 disabled:opacity-40"
        >
          {t('run.scan')}
        </button>
        <button
          onClick={onRunEnsemble}
          disabled={!canRun || running}
          title={t('run.ensembleTitle')}
          className="border border-neutral-900 px-4 py-2 text-sm text-neutral-900 transition hover:bg-neutral-100 disabled:opacity-40"
        >
          {t('run.ensemble')}
        </button>
        <button
          onClick={onRunMap}
          disabled={!canRun || running}
          title={t('run.mapTitle')}
          className="bg-red-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-600 disabled:opacity-40"
        >
          {t('run.map')}
        </button>
        {!running && status && (
          <button onClick={onReset} className="text-xs text-neutral-500 underline hover:text-neutral-900">
            {t('run.reset')}
          </button>
        )}
        {gpu && (
          <span className={`mono ml-auto border px-2 py-0.5 text-xs ${
            gpu.available ? 'border-neutral-900 text-neutral-900' : 'border-neutral-300 text-neutral-500'
          }`}>
            {gpu.available ? t('run.gpu', { name: gpu.name ?? '' }) : t('run.cpuOnly', { reason: gpu.reason ?? t('run.noCuda') })}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-neutral-600">
        <label htmlFor="profile-select">{t('run.profile')}</label>
        <select
          id="profile-select"
          value={profile}
          onChange={(e) => onProfileChange(e.target.value as InferenceProfile)}
          disabled={running}
          className="mono border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-900 focus:border-neutral-900"
        >
          {PROFILE_OPTIONS.map((o) => (
            <option key={o.id} value={o.id}>{t(o.label)}</option>
          ))}
        </select>
        <span className="text-[10px] text-neutral-400">
          {t('run.profileHint')}
        </span>
      </div>

      {/* диапазон scan-map: 19 фолдов на позицию — честная цена показана */}
      {/* scan-map 范围：每个位置 19 次折叠——如实显示代价 */}
      <div className="flex items-center gap-2 text-xs text-neutral-600">
        <label htmlFor="map-from">{t('run.mapRange')}</label>
        <input
          id="map-from"
          type="number"
          min={1}
          max={seqLen}
          value={mapFrom}
          onChange={(e) => onMapRangeChange(Math.max(1, Math.min(seqLen, Number(e.target.value) || 1)), mapTo)}
          disabled={running}
          className="mono w-16 border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-900 focus:border-neutral-900"
        />
        <span>—</span>
        <input
          id="map-to"
          type="number"
          min={1}
          max={seqLen}
          value={mapTo}
          onChange={(e) => onMapRangeChange(mapFrom, Math.max(1, Math.min(seqLen, Number(e.target.value) || 1)))}
          disabled={running}
          className="mono w-16 border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-900 focus:border-neutral-900"
        />
        <span className="text-[10px] text-neutral-400">
          {t('run.mapCount', {
            n: Math.max(0, Math.min(mapTo, seqLen) - Math.min(mapFrom, seqLen) + 1),
            folds: Math.max(0, Math.min(mapTo, seqLen) - Math.min(mapFrom, seqLen) + 1) * 19,
          })}
        </span>
      </div>

      {running && (
        <div className="space-y-1.5 border border-neutral-200 p-3" data-demo="progress">
          <div className="flex items-center justify-between text-xs">
            <span className="text-neutral-700">
              {status?.status === 'queued'
                ? (status.message ?? t('run.queued'))
                : (status?.message ?? t('run.running'))}
            </span>
            <span className="mono text-neutral-500">{fmtElapsed(elapsed)}</span>
          </div>

          {/* один сегмент на реальный этап конвейера */}
          {/* 每个真实流水线阶段一段 */}
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
            {t('run.progressNote')}
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