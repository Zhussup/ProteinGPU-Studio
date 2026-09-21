// TranslationPanel: DNA FASTA → codon table → amino acids (modal content).
// The backend does the genetic-code translation (POST /api/v1/translate);
// this is purely presentational.
import type { TranslateResponse } from '../lib/types'
import { renderBold, useI18n } from '../i18n'

export interface TranslationPanelProps {
  data: TranslateResponse
  onUseProtein: (protein: string, dnaLen: number) => void
}

export default function TranslationPanel({ data, onUseProtein }: TranslationPanelProps) {
  const { t } = useI18n()
  // cap rendering: thousands of cells would freeze the tab
  const shown = data.codons.slice(0, 400)
  const proteinLen = data.protein.length

  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-600">
        <span>{renderBold(t('tr.nucleotides', { n: data.dna.length }))}</span>
        <span>·</span>
        <span>{renderBold(t('tr.aaToStop', { n: proteinLen }))}</span>
        <span>·</span>
        <span>{renderBold(t('tr.orfStart', { n: data.orf_start + 1 }))}</span>
        <button
          onClick={() => onUseProtein(data.protein, data.dna.length)}
          disabled={proteinLen < 10}
          className="ml-auto bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-neutral-700 disabled:opacity-40"
          title={proteinLen < 10 ? t('tr.tooShort') : t('tr.sendToWorkspace')}
        >
          {t('tr.useProtein', { n: proteinLen })}
        </button>
      </div>

      {data.warnings.length > 0 && (
        <div className="border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {data.warnings.map((w, i) => <div key={i}>{w}</div>)}
        </div>
      )}

      {/* codon table: triplet on top, amino acid below; stop codons in red */}
      <div className="grid gap-px border border-neutral-200 bg-neutral-200" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(64px, 1fr))' }}>
        {shown.map((c) => {
          const stop = c.aa === '*'
          return (
            <div
              key={c.index}
              className={`bg-white px-1.5 py-1 text-center ${stop ? 'bg-red-50' : ''}`}
              title={t('tr.codonTitle', { i: c.index, codon: c.codon, aa: stop ? t('tr.stop') : c.aa })}
            >
              <div className="mono text-[11px] text-neutral-500">#{c.index}</div>
              <div className="mono text-sm font-medium text-neutral-900">{c.codon}</div>
              <div className={`mono text-base font-semibold ${stop ? 'text-red-700' : 'text-neutral-700'}`}>
                {stop ? '■' : c.aa}
              </div>
            </div>
          )
        })}
      </div>
      {data.codons.length > shown.length && (
        <div className="text-xs text-neutral-500">
          {t('tr.shownFirst', { n: shown.length, m: data.codons.length })}
        </div>
      )}

      <div className="border border-neutral-200 bg-neutral-50 p-3">
        <div className="mb-1 text-[11px] text-neutral-500">{t('tr.proteinSeq')}</div>
        <div className="mono break-all text-xs text-neutral-900">{data.protein}</div>
      </div>
    </div>
  )
}