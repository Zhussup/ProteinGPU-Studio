// MutagenesisDial: ВХОДНАЯ сторона ручки силы мутагенеза (dum.md §2).
// Сколько и каких мутаций генерировать: μ — одновременных замен на вариант
// (якорь + фон), τ — температура спектра Грэнтэма (консервативные ↔
// радикальные), K — размер ансамбля. Плюс оценка времени исполнения, чтобы
// «ручка» никогда не запускала молча полчаса GPU-задачи.
// MutagenesisDial：突变强度旋钮的输入端（dum.md §2）。
// 生成多少、哪些突变：μ——每个变体的同时替换数（锚点 + 背景），
// τ——Grantham 谱温度（保守 ↔ 激进），K——ensemble 大小。
// 外加运行时长估计，让“旋钮”绝不静默启动半小时的 GPU 任务。
import { useI18n, type TFn } from '../i18n'
import type { InferenceProfile } from '../lib/types'

export interface MutagenesisDialProps {
  seqLen: number
  profile: InferenceProfile
  exhaustive: boolean
  mu: number
  tau: number
  k: number
  seed: number | null
  onExhaustive: (v: boolean) => void
  onMu: (v: number) => void
  onTau: (v: number) => void
  onK: (v: number) => void
  onSeed: (v: number | null) => void
}

// Базовое время фолда на 76 aa, из docs/benchmarks.md (median). "auto"
// оценивается по fp32 — консервативный выбор. dummy сворачивается мгновенно.
// 76 aa 的单次折叠基准耗时，来自 docs/benchmarks.md（median）。
// "auto" 按 fp32 计价——保守选择。dummy 瞬间完成。
const BASE_S: Record<InferenceProfile, number> = {
  auto: 11.59, 'fp32-gpu': 11.59, 'fp16-gpu': 8.72, cpu: 143.5, dummy: 0.05,
}

function fmtSeconds(t: TFn, s: number): string {
  if (s < 90) return `${Math.max(1, Math.round(s))} ${t('dial.unit.sec')}`
  const m = Math.round(s / 60)
  return `${m} ${t('dial.unit.min')}`
}

export default function MutagenesisDial({
  seqLen, profile, exhaustive, mu, tau, k, seed,
  onExhaustive, onMu, onTau, onK, onSeed,
}: MutagenesisDialProps) {
  const { t } = useI18n()

  // (K+1) фолдов, квадратично по длине (attention): измерено 76→200 aa ×6.9
  // (K+1) 次折叠，随长度平方增长（attention）：实测 76→200 aa ×6.9
  const estS = (k + 1) * BASE_S[profile] * Math.pow(Math.max(seqLen, 1) / 76, 2)
  const long = estS > 600

  return (
    <div className="space-y-3" data-demo="dial">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-900">{t('dial.title')}</label>
        <button
          type="button"
          onClick={() => onExhaustive(!exhaustive)}
          title={t('dial.modeExhaustiveTitle')}
          className={`border px-2.5 py-1 text-xs transition ${
            exhaustive
              ? 'border-neutral-900 bg-neutral-900 text-white'
              : 'border-neutral-300 bg-white text-neutral-700 hover:border-neutral-900'
          }`}
        >
          {t('dial.mode.exhaustive')}
        </button>
      </div>

      {/* μ — одновременных замен на вариант */}
      {/* μ——每个变体的同时替换数 */}
      <div>
        <div className="mb-1 text-[11px] text-neutral-500">{t('dial.mu')}</div>
        <div className="flex gap-1.5">
          {[1, 2, 3].map((m) => (
            <button
              key={m}
              disabled={exhaustive}
              onClick={() => onMu(m)}
              className={`mono w-10 border px-2 py-1 text-xs transition disabled:opacity-40 ${
                mu === m
                  ? 'border-neutral-900 bg-neutral-900 text-white'
                  : 'border-neutral-300 bg-white text-neutral-700 hover:border-neutral-900'
              }`}
            >
              {m}
            </button>
          ))}
          <span className="ml-1 self-center text-[10px] text-neutral-400">
            {t('dial.muHint')}
          </span>
        </div>
      </div>

      {/* τ — температура спектра Грэнтэма (первый range-инпут приложения) */}
      {/* τ——Grantham 谱温度（本应用的第一个 range 控件） */}
      <div className={exhaustive ? 'opacity-40' : ''}>
        <div className="mb-1 flex items-baseline justify-between text-[11px] text-neutral-500">
          <span>{t('dial.tau')}</span>
          <span className="mono text-xs text-neutral-900">τ = {tau.toFixed(2)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={tau}
          disabled={exhaustive}
          onChange={(e) => onTau(parseFloat(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-[10px] text-neutral-400">
          <span>{t('dial.tauCons')}</span>
          <span>{t('dial.tauRad')}</span>
        </div>
      </div>

      {/* K — размер ансамбля */}
      {/* K——ensemble 大小 */}
      <div className="flex items-end gap-3">
        <div className={exhaustive ? 'opacity-40' : ''}>
          <div className="mb-1 text-[11px] text-neutral-500">{t('dial.k')}</div>
          <input
            type="number"
            min={2}
            max={40}
            value={k}
            disabled={exhaustive}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10)
              if (!Number.isNaN(v)) onK(Math.min(40, Math.max(2, v)))
            }}
            className="mono w-20 border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-900 disabled:bg-neutral-100"
          />
        </div>
        <div className={exhaustive ? 'opacity-40' : ''}>
          <div className="mb-1 text-[11px] text-neutral-500">{t('dial.seed')}</div>
          <input
            type="number"
            value={seed ?? ''}
            placeholder={t('dial.seedAuto')}
            disabled={exhaustive}
            onChange={(e) => {
              if (e.target.value === '') { onSeed(null); return }
              const v = parseInt(e.target.value, 10)
              if (!Number.isNaN(v)) onSeed(Math.abs(v))
            }}
            className="mono w-28 border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none placeholder:text-neutral-300 focus:border-neutral-900 disabled:bg-neutral-100"
          />
        </div>
      </div>
      <div className="text-[10px] text-neutral-400">{t('dial.seedNote')}</div>

      {/* честная оценка времени — никаких молчаливых задач на полчаса */}
      {/* 诚实的时长估计——绝不静默启动半小时任务 */}
      <div className="border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px] text-neutral-600">
        <span className="text-neutral-400">{t('dial.estimateLabel')}</span>{' '}
        <span className={`mono ${long ? 'text-red-700' : 'text-neutral-900'}`}>
          ≈ {profile === 'dummy' ? t('dial.estimateInstant') : fmtSeconds(t, estS)}
        </span>
        {long && <div className="mt-0.5 text-red-700">{t('dial.estimateWarn')}</div>}
      </div>

      <div className="text-[10px] text-neutral-400">{t('dial.granthamNote')}</div>
    </div>
  )
}