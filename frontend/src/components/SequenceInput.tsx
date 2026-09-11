// SequenceInput: FASTA/RAW sequence entry (protein or DNA file upload),
// demo presets, and a DNA→codon→amino-acid translation window.
import { useMemo, useRef, useState } from 'react'
import type { Preset, TranslateResponse } from '../lib/types'
import { api } from '../lib/api'
import Modal from './Modal'
import TranslationPanel from './TranslationPanel'

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

  // DNA FASTA upload → codon/translation modal
  const fileRef = useRef<HTMLInputElement>(null)
  const [translation, setTranslation] = useState<TranslateResponse | null>(null)
  const [translating, setTranslating] = useState(false)
  const [transError, setTransError] = useState<string | null>(null)

  const onFile = async (f: File | undefined) => {
    if (!f) return
    setTranslating(true); setTransError(null)
    try {
      const text = await f.text()
      setTranslation(await api.translate(text))
    } catch (e) {
      setTransError(String(e))
    } finally {
      setTranslating(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-900">Последовательность (FASTA или raw)</label>
        <span className={`mono text-xs ${valid && lenOk ? 'text-neutral-900' : 'text-red-700'}`}>
          {len} aa {valid ? '' : '· недопустимые символы'} {lenOk ? '' : `· ${minLen}–${maxLen}`}
        </span>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        spellCheck={false}
        placeholder={">sp|P0CG48 ubiquitin\nMQIFVKTLTGK..."}
        className="mono w-full resize-y border border-neutral-300 bg-white p-3 text-xs text-neutral-900 outline-none focus:border-neutral-900"
      />
      <div className="flex flex-wrap items-center gap-1.5">
        {presets.map((p) => (
          <button
            key={p.id}
            onClick={() => onChange(`>${p.name}\n${p.sequence}`)}
            title={p.description}
            className="border border-neutral-300 px-2.5 py-1 text-xs text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
          >
            {p.name}
          </button>
        ))}
        <span className="mx-1 h-4 w-px bg-neutral-200" />
        <input
          ref={fileRef}
          type="file"
          accept=".fasta,.fa,.fna,.txt"
          className="hidden"
          onChange={(e) => void onFile(e.target.files?.[0])}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="border border-neutral-300 px-2.5 py-1 text-xs text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
        >
          {translating ? 'транслирую…' : 'Загрузить FASTA (ДНК)'}
        </button>
      </div>

      {transError && (
        <div className="border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">{transError}</div>
      )}

      {translation && (
        <Modal title="Трансляция: ДНК → кодоны → аминокислоты" onClose={() => setTranslation(null)} wide>
          <TranslationPanel
            data={translation}
            onUseProtein={(protein, dnaLen) => {
              onChange(`>переведено из ДНК (${dnaLen} nt)\n${protein}`)
              setTranslation(null)
            }}
          />
        </Modal>
      )}
    </div>
  )
}

export { AA_RE }