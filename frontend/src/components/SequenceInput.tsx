// SequenceInput: FASTA/RAW sequence entry + demo presets (ubiquitin WT & mutants).
import { useMemo } from 'react'
import type { Preset } from '../lib/types'

const AA_RE = /^[ACDEFGHIKLMNPQRSTVWY]+$/

export function stripFasta(text: string): string {
  return text
    .split('\n')
    .filter((l) => !l.trim().startsWith('>'))
    .join('')
    .replace(/\s+/g, '')
    .toUpperCase()
}

export interface SequenceInputProps {
  value: string
  onChange: (seq: string) => void
  presets: Preset[]
  minLen: number
  maxLen: number
}

export default function SequenceInput({ value, onChange, presets, minLen, maxLen }: SequenceInputProps) {
  const raw = useMemo(() => stripFasta(value), [value])
  const valid = AA_RE.test(raw)
  const len = raw.length
  const lenOk = len >= minLen && len <= maxLen

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-slate-300">Последовательность (FASTA или raw)</label>
        <span className={`mono text-xs ${valid && lenOk ? 'text-emerald-400' : 'text-slate-500'}`}>
          {len} aa {valid ? '' : '· недопустимые символы'} {lenOk ? '' : `· ${minLen}–${maxLen}`}
        </span>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        spellCheck={false}
        placeholder={">sp|P0CG48 ubiquitin\nMQIFVKTLTGK..."}
        className="mono w-full resize-y rounded-lg border border-slate-800 bg-[#0b0f14] p-3 text-xs text-slate-200 outline-none focus:border-cyan-700"
      />
      <div className="flex flex-wrap gap-1.5">
        {presets.map((p) => (
          <button
            key={p.id}
            onClick={() => onChange(`>${p.name}\n${p.sequence}`)}
            title={p.description}
            className="rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-300 transition hover:border-cyan-600 hover:text-cyan-300"
          >
            {p.name}
          </button>
        ))}
      </div>
    </div>
  )
}

export { AA_RE }