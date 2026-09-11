// MutationPicker: position + residue selectors, demo preset chips, live seq preview.
import { AA_RE } from './SequenceInput'
import type { Preset } from '../lib/types'

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
  const wtAA = position >= 1 && position <= sequence.length ? sequence[position - 1] : '?'
  const posOk = position >= 1 && position <= sequence.length && AA_RE.test(sequence)

  const demoPresets = presets.filter((p) => p.position && p.mutant_aa)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-300">Мутация</label>
        <span className="mono text-xs text-slate-400">
          {posOk ? `${wtAA}${position}${mutantAA}` : '—'}
        </span>
      </div>

      <div className="flex items-end gap-2">
        <div>
          <div className="mb-1 text-[11px] text-slate-500">Позиция (1-based)</div>
          <input
            type="number"
            min={1}
            max={sequence.length || undefined}
            value={position || ''}
            onChange={(e) => onChange(parseInt(e.target.value, 10) || 0, mutantAA)}
            className="mono w-24 rounded-lg border border-slate-800 bg-[#0b0f14] px-3 py-2 text-sm outline-none focus:border-cyan-700"
          />
        </div>
        <div className="pb-2 text-slate-500">→</div>
        <div>
          <div className="mb-1 text-[11px] text-slate-500">Новый остаток</div>
          <select
            value={mutantAA}
            onChange={(e) => onChange(position, e.target.value)}
            className="mono w-24 rounded-lg border border-slate-800 bg-[#0b0f14] px-3 py-2 text-sm outline-none focus:border-cyan-700"
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
        <div className="mb-1.5 text-[11px] text-slate-500">Демо-пресеты (убиквитин, литературно обоснованные):</div>
        <div className="flex flex-wrap gap-1.5">
          {demoPresets.map((p) => (
            <button
              key={p.id}
              onClick={() => onApplyPreset(p)}
              title={p.description}
              className="mono rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-300 transition hover:border-cyan-600 hover:text-cyan-300"
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
    <div className="mono overflow-x-auto rounded-lg border border-slate-800 bg-[#0b0f14] px-3 py-2 text-xs whitespace-nowrap">
      {start > 0 && <span className="text-slate-600">…</span>}
      <span className="text-slate-400">{before}</span>
      <span className="rounded bg-red-900/60 px-0.5 font-bold text-red-300">{site}</span>
      <span className="text-slate-400">{after}</span>
      {end < sequence.length && <span className="text-slate-600">…</span>}
      <span className="ml-2 text-slate-600">[{start + 1}–{end}]</span>
    </div>
  )
}