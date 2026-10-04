// EnsembleKnobs: входная сторона ручки силы мутагенеза (dum.md §2).
// Сколько и каких мутаций генерировать: μ — одновременных замен на вариант
// (якорь + фон), τ — температура спектра Грэнтэма (консервативные ↔
// радикальные), K — размер ансамбля. Плюс честная оценка времени, чтобы
// «ручка» никогда не запускала молча полчаса GPU-задачи.
//
// Режим — явный сегментированный выбор, а не загашенные поля: в режиме
// «все 19 замен» настройки μ/τ/K/seed не показываются вовсе, вместо них
// строка-резюме (что именно фиксировано и почему).
// EnsembleKnobs：突变强度旋钮的输入端（dum.md §2）。
// 生成多少、哪些突变：μ——每个变体的同时替换数（锚点 + 背景），
// τ——Grantham 谱温度（保守 ↔ 激进），K——ensemble 大小。
// 外加诚实时长估计，让“旋钮”绝不静默启动半小时的 GPU 任务。
//
// 模式是显式的分段选择，而不是置灰字段：在“全部 19 种替换”模式下
// 完全隐藏 μ/τ/K/seed，改为一行摘要（固定了什么、为什么）。
import { useI18n, type TFn } from '../i18n'
import type { InferenceProfile } from '../lib/types'

export type EnsembleMode = 'sampled' | 'exhaustive'

export interface EnsembleKnobsProps {
  seqLen: number
  profile: InferenceProfile
  mode: EnsembleMode
  mu: number
  tau: number
  k: number
  seed: number | null
  onMode: (m: EnsembleMode) => void
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

export default function EnsembleKnobs({
  seqLen, profile, mode, mu, tau, k, seed,
  onMode, onMu, onTau, onK, onSeed,
}: EnsembleKnobsProps) {
  const { t } = useI18n()
  const sampled = mode === 'sampled'
  const effK = sampled ? k : 19

  // (K+1) фолдов, квадратично по длине (attention): измерено 76→200 aa ×6.9
  // (K+1) 次折叠，随长度平方增长（attention）：实测 76→200 aa ×6.9
  const estS = (effK + 1) * BASE_S[profile] * Math.pow(Math.max(seqLen, 1) / 76, 2)
  const long = estS > 600

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-900">{t('dial.title')}</label>
      </div>

      {/* режим: случайный K-ансамбль либо полный перебор 19 замен */}
      {/* 模式：随机 K 变体 ensemble，或全部 19 种替换的穷举 */}
      <div className="flex" role="radiogroup" aria-label={t('dial.title')}>
        {(['sampled', 'exhaustive'] as EnsembleMode[]).map((m) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={mode === m}
            onClick={() => onMode(m)}
            className={`flex-1 border px-2.5 py-1.5 text-xs transition first:border-r-0 ${
              mode === m
                ? 'border-neutral-900 bg-neutral-900 text-white'
                : 'border-neutral-300 bg-white text-neutral-700 hover:border-neutral-900'
            }`}
          >
            {t(m === 'sampled' ? 'ens.mode.sampled' : 'ens.mode.exhaustive')}
          </button>
        ))}
      </div>

      {sampled ? (
        <>
          {/* μ — одновременных замен на вариант */}
          {/* μ——每个变体的同时替换数 */}
          <div>
            <div className="mb-1 text-[11px] text-neutral-500">{t('dial.mu')}</div>
            <div className="flex gap-1.5">
              {[1, 2, 3].map((m) => (
                <button
                  key={m}
                  onClick={() => onMu(m)}
                  className={`mono w-10 border px-2 py-1 text-xs transition ${
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

          {/* τ — температура спектра Грэнтэма */}
          {/* τ——Grantham 谱温度 */}
          <div>
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
              onChange={(e) => onTau(parseFloat(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-[10px] text-neutral-400">
              <span>{t('dial.tauCons')}</span>
              <span>{t('dial.tauRad')}</span>
            </div>
          </div>

          {/* K — размер ансамбля, seed — воспроизводимость */}
          {/* K——ensemble 大小，seed——可复现性 */}
          <div className="flex items-end gap-3">
            <div>
              <div className="mb-1 text-[11px] text-neutral-500">{t('dial.k')}</div>
              <input
                type="number"
                min={2}
                max={40}
                value={k}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10)
                  if (!Number.isNaN(v)) onK(Math.min(40, Math.max(2, v)))
                }}
                className="mono w-20 border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-900 disabled:bg-neutral-100"
              />
            </div>
            <div>
              <div className="mb-1 text-[11px] text-neutral-500">{t('dial.seed')}</div>
              <input
                type="number"
                value={seed ?? ''}
                placeholder={t('dial.seedAuto')}
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
        </>
      ) : (
        <div className="border border-neutral-200 bg-neutral-50 px-3 py-2 text-[11px] text-neutral-600">
          {t('ens.exhaustiveNote')}
        </div>
      )}

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
