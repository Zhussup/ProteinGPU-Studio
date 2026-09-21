// EnsemblePanel: results of a mutagenesis-strength ensemble run (dum.md §2/§6).
// The position's sensitivity is the DISTRIBUTION of responses across K variants
// — medians, IQR, histograms — never a two-structure eyeball comparison.
// Clicking a row overlays that variant's aligned PDB on the WT in 3D.
import { Suspense, lazy, useState } from 'react'
import type { EnsembleResult, EnsembleRow } from '../lib/types'
import { renderBold, useI18n, type Key } from '../i18n'
import Modal from './Modal'

const Plot = lazy(() => import('../components/PlotlyChart'))

const VERDICT_CLS: Record<EnsembleRow['interpretation'], string> = {
  stable: 'border border-neutral-300 text-neutral-500',
  moderate: 'bg-neutral-600 text-white',
  critical: 'bg-red-700 text-white',
}
const VERDICT_KEYS: Record<EnsembleRow['interpretation'], Key> = {
  stable: 'scan.v.stable',
  moderate: 'scan.v.moderate',
  critical: 'scan.v.critical',
}
const LEVEL_CLS: Record<EnsembleResult['headline']['level'], string> = {
  quiet: 'border border-neutral-300 text-neutral-500',
  moderate: 'bg-neutral-600 text-white',
  strong: 'bg-red-700 text-white',
}
const LEVEL_KEYS: Record<EnsembleResult['headline']['level'], Key> = {
  quiet: 'ens.level.quiet',
  moderate: 'ens.level.moderate',
  strong: 'ens.level.strong',
}
const WIDTH_KEYS: Record<EnsembleResult['headline']['width'], Key> = {
  narrow: 'ens.width.narrow',
  moderate: 'ens.width.moderate',
  wide: 'ens.width.wide',
}

export interface EnsemblePanelProps {
  result: EnsembleResult
  onPickRow: (index: number) => void
  pickedIndex?: number | null
}

export default function EnsemblePanel({ result, onPickRow, pickedIndex }: EnsemblePanelProps) {
  const { t, tl } = useI18n()
  const [help, setHelp] = useState(false)
  const { stats, headline } = result
  const exhaustive = result.mode === 'exhaustive'

  return (
    <div className="space-y-4" data-demo="ensemble">
      <div className="border-l-2 border-neutral-900 bg-neutral-50 p-3 text-sm text-neutral-800">
        {result.summary}
      </div>

      {/* the dial configuration that produced this ensemble */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-500">
        {exhaustive ? (
          <span>{t('ens.exhaustiveNote')}</span>
        ) : (
          <>
            <span className="mono">μ = {result.params.mu}</span>
            <span className="mono">τ = {result.params.tau.toFixed(2)}</span>
            <span className="mono">K = {result.params.k}</span>
            <span className="mono">{t('ens.seedLabel')}: {result.params.seed}</span>
          </>
        )}
        <span className="ml-auto flex items-center gap-1.5">
          <span className={`mono px-2 py-0.5 text-[10px] ${LEVEL_CLS[headline.level]}`}>
            {t(LEVEL_KEYS[headline.level])}
          </span>
          <span className="mono border border-neutral-300 px-2 py-0.5 text-[10px] text-neutral-500">
            {t(WIDTH_KEYS[headline.width])}
          </span>
          <button
            onClick={() => setHelp(true)}
            title={t('ens.help.q')}
            className="inline-flex h-4 w-4 items-center justify-center border border-neutral-300 text-[10px] leading-none text-neutral-500 hover:border-neutral-900 hover:text-neutral-900"
          >
            ?
          </button>
        </span>
      </div>

      {/* the four honest numbers: medians + spread, no invented 0-100 score */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="border border-neutral-200 bg-white p-3">
          <div className="text-[11px] text-neutral-500">{t('ens.card.medLocal')}</div>
          <div className="mono mt-1 text-xl text-neutral-900">
            {stats.local_rmsd.median.toFixed(2)} Å
          </div>
          <div className="mono mt-0.5 text-[10px] text-neutral-400">
            {t('ens.card.iqr', { v: stats.local_rmsd.iqr.toFixed(2) })}
          </div>
        </div>
        <div className="border border-neutral-200 bg-white p-3">
          <div className="text-[11px] text-neutral-500">{t('ens.card.medDplddt')}</div>
          <div className="mono mt-1 text-xl text-neutral-900">
            {headline.median_abs_dplddt_local.toFixed(2)}
          </div>
          <div className="mono mt-0.5 text-[10px] text-neutral-400">{t('ens.card.dplddtUnit')}</div>
        </div>
        <div className="border border-neutral-200 bg-white p-3">
          <div className="text-[11px] text-neutral-500">{t('ens.card.range')}</div>
          <div className="mono mt-1 text-xl text-neutral-900">
            {stats.local_rmsd.min.toFixed(2)}–{stats.local_rmsd.max.toFixed(2)}
          </div>
          <div className="mono mt-0.5 text-[10px] text-neutral-400">Å</div>
        </div>
        <div className="border border-neutral-200 bg-white p-3">
          <div className="text-[11px] text-neutral-500">{t('ens.card.k')}</div>
          <div className="mono mt-1 text-xl text-neutral-900">{result.variants.length}</div>
          <div className="mono mt-0.5 text-[10px] text-neutral-400">
            {t('ens.card.spread', { v: headline.iqr_ratio.toFixed(2) })}
          </div>
        </div>
      </div>

      <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
        <Hist
          title={t('ens.hist.localTitle')}
          values={result.variants.map((v) => v.local_rmsd)}
          xTitle={t('ens.hist.xaxisLocal')}
          yTitle={t('ens.hist.yaxis')}
        />
      </Suspense>
      <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
        <Hist
          title={t('ens.hist.dplddtTitle')}
          values={result.variants.map((v) => Math.abs(v.dplddt_local))}
          xTitle={t('ens.hist.xaxisDplddt')}
          yTitle={t('ens.hist.yaxis')}
        />
      </Suspense>

      <div className="max-h-80 overflow-y-auto border border-neutral-200">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-neutral-100 text-neutral-600">
            <tr>
              <th className="px-2 py-1.5 text-left">{t('scan.h.mutation')}</th>
              <th className="px-2 py-1.5 text-right">{t('scan.h.local')}</th>
              <th className="px-2 py-1.5 text-right">{t('scan.h.global')}</th>
              <th className="px-2 py-1.5 text-right">{t('scan.h.tm')}</th>
              <th className="px-2 py-1.5 text-right">{t('scan.h.dplddt')}</th>
              <th className="px-2 py-1.5 text-right">{t('ens.h.dplddtLocal')}</th>
              <th className="px-2 py-1.5 text-center">{t('scan.h.verdict')}</th>
            </tr>
          </thead>
          <tbody>
            {result.variants.map((r, i) => (
              <tr
                key={`${r.label}-${i}`}
                onClick={() => onPickRow(i)}
                title={t('scan.rowTitle')}
                className={`cursor-pointer border-t border-neutral-100 hover:bg-neutral-100 ${
                  i === pickedIndex ? 'bg-neutral-100' : 'bg-white'
                }`}
              >
                <td className="mono px-2 py-1.5 font-medium text-neutral-900">
                  {r.label} {i === 0 && (
                    <span className="text-[10px] text-neutral-500">{t('scan.strongest')}</span>
                  )}
                </td>
                <td className="mono px-2 py-1.5 text-right">{r.local_rmsd.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.global_rmsd.toFixed(2)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.tm_score.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">
                  {r.dplddt >= 0 ? `+${r.dplddt.toFixed(1)}` : r.dplddt.toFixed(1)}
                </td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">
                  {Math.abs(r.dplddt_local).toFixed(2)}
                </td>
                <td className="px-2 py-1.5 text-center">
                  <span className={`mono px-1.5 py-0.5 text-[10px] ${VERDICT_CLS[r.interpretation]}`}>
                    {t(VERDICT_KEYS[r.interpretation])}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-[10px] text-neutral-400">{t('ens.note')}</div>

      {help && (
        <Modal title={t('help.ensemble.title')} onClose={() => setHelp(false)}>
          <div className="space-y-2 text-sm text-neutral-800">
            {tl('help.ensemble').map((p, i) => (
              <p key={i}>{renderBold(p)}</p>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}

// Histogram of one response metric across the ensemble (Plotly, canonical idiom).
function Hist({ title, values, xTitle, yTitle }: {
  title: string; values: number[]; xTitle: string; yTitle: string
}) {
  const data = [{
    x: values,
    type: 'histogram' as const,
    nbinsx: 12,
    marker: { color: '#111111' },
  }]
  const layout = {
    margin: { t: 24, r: 10, b: 40, l: 50 },
    title: { text: title, font: { size: 12, color: '#404040' } },
    paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
    font: { color: '#525252', size: 11 },
    xaxis: { title: { text: xTitle }, linecolor: '#d4d4d4' },
    yaxis: { title: { text: yTitle }, gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
    bargap: 0.08,
  }
  return <Plot data={data} layout={layout} />
}