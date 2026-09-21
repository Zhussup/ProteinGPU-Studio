// MutagenesisDial: the INPUT side of the mutagenesis-strength dial (dum.md §2).
// How many and which mutations to generate: μ — simultaneous substitutions per
// variant (anchor + background), τ — the Grantham spectrum temperature
// (conservative ↔ radical), K — ensemble size. Plus a runtime estimate so
// "the dial" never launches a silent half-hour GPU job.
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

// Base per-fold wall time at 76 aa, from docs/benchmarks.md (median). "auto"
// is priced as fp32 — the conservative choice. dummy folds instantly.
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

  // (K+1) folds, quadratic in length (attention): measured 76→200 aa ×6.9
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

      {/* μ — simultaneous substitutions per variant */}
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

      {/* τ — Grantham spectrum temperature (the app's first range input) */}
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

      {/* K — ensemble size */}
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

      {/* honest runtime estimate — no silent half-hour jobs */}
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