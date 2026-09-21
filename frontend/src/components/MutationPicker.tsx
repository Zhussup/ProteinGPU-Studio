// MutationPicker: position + residue selectors, demo preset chips, live seq preview.
import { AA_RE } from './SequenceInput'
import type { Preset } from '../lib/types'
import { useI18n } from '../i18n'

const AAS = 'ACDEFGHIKLMNPQRSTVWY'.split('')

export interface MutationPickerProps {
  sequence: string // raw aa (already stripped)
  position: number
  mutantAA: string
  onChange: (position: number, mutantAA: string) => void
  presets: Preset[]
  onApplyPreset: (p: Preset) => void
}

export default function MutationPicker({
  sequence, position, mutantAA, onChange, presets, onApplyPreset,
}: MutationPickerProps) {
  const { t } = useI18n()
  const wtAA = position >= 1 && position <= sequence.length ? sequence[position - 1] : '?'
  const posOk = position >= 1 && position <= sequence.length && AA_RE.test(sequence)

  const demoPresets = presets.filter((p) => p.position && p.mutant_aa)

  return (
    <div className="space-y-3" data-demo="mutation">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-900">{t('mut.title')}</label>
        <span className="mono text-xs text-neutral-700">
          {posOk ? `${wtAA}${position}${mutantAA}` : '—'}
        </span>
      </div>

      <div className="flex items-end gap-2">
        <div>
          <div className="mb-1 text-[11px] text-neutral-500">{t('mut.position')}</div>
          <input
            type="number"
            min={1}
            max={sequence.length || undefined}
            value={position || ''}
            onChange={(e) => onChange(parseInt(e.target.value, 10) || 0, mutantAA)}
            className="mono w-24 border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-900"
          />
        </div>
        <div className="pb-2 text-neutral-400">→</div>
        <div>
          <div className="mb-1 text-[11px] text-neutral-500">{t('mut.newResidue')}</div>
          <select
            value={mutantAA}
            onChange={(e) => onChange(position, e.target.value)}
            className="mono w-24 border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-900"
          >
            {AAS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
      </div>

      {posOk && (
        <SequenceStrip sequence={sequence} position={position} />
      )}

      <div>
        <div className="mb-1.5 text-[11px] text-neutral-500">{t('mut.demoPresets')}</div>
        <div className="flex flex-wrap gap-1.5">
          {demoPresets.map((p) => (
            <button
              key={p.id}
              onClick={() => onApplyPreset(p)}
              title={p.description}
              className="mono border border-neutral-300 px-2.5 py-1 text-xs text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// SequenceStrip: one-letter sequence with the mutation site highlighted.
function SequenceStrip({ sequence, position }: { sequence: string; position: number }) {
  const start = Math.max(0, position - 11)
  const end = Math.min(sequence.length, position + 10)
  const before = sequence.slice(start, position - 1)
  const site = sequence[position - 1]
  const after = sequence.slice(position, end)

  return (
    <div className="mono overflow-x-auto border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs whitespace-nowrap">
      {start > 0 && <span className="text-neutral-400">…</span>}
      <span className="text-neutral-600">{before}</span>
      <span className="bg-neutral-900 px-0.5 font-bold text-white">{site}</span>
      <span className="text-neutral-600">{after}</span>
      {end < sequence.length && <span className="text-neutral-400">…</span>}
      <span className="ml-2 text-neutral-400">[{start + 1}–{end}]</span>
    </div>
  )
}