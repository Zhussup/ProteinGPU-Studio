// ScanPanel: результаты насыщающего скана (все 19 замен).
// Ранжированная таблица + столбчатая диаграмма; клик по строке показывает
// этого мутанта во вьюере.
// ScanPanel：饱和扫描的结果（全部 19 种替换）。
// 排序表格 + 条形图；点击行可在查看器中显示该突变体。
import { Suspense, lazy } from 'react'
import type { ScanResult, ScanRow } from '../lib/types'
import { useI18n, type Key } from '../i18n'

const Plot = lazy(() => import('../components/PlotlyChart'))

const VERDICT_CLS: Record<ScanRow['interpretation'], string> = {
  stable: 'border border-neutral-300 text-neutral-500',
  moderate: 'bg-neutral-600 text-white',
  critical: 'bg-red-700 text-white',
}
const VERDICT_KEYS: Record<ScanRow['interpretation'], Key> = {
  stable: 'scan.v.stable',
  moderate: 'scan.v.moderate',
  critical: 'scan.v.critical',
}

export interface ScanPanelProps {
  result: ScanResult
  onPickRow: (mutAA: string) => void
  pickedAA?: string | null
}

export default function ScanPanel({ result, onPickRow, pickedAA }: ScanPanelProps) {
  const { t } = useI18n()
  const rows = result.rows

  return (
    <div className="space-y-4">
      <div className="border-l-2 border-neutral-900 bg-neutral-50 p-3 text-sm text-neutral-800">
        {result.summary}
      </div>

      <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
        <ScanChart rows={rows} wtAA={result.wt_aa} />
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
              <th className="px-2 py-1.5 text-center">{t('scan.h.verdict')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.mut_aa}
                onClick={() => onPickRow(r.mut_aa)}
                title={t('scan.rowTitle')}
                className={`cursor-pointer border-t border-neutral-100 hover:bg-neutral-100 ${
                  r.mut_aa === pickedAA ? 'bg-neutral-100' : 'bg-white'
                }`}
              >
                <td className="mono px-2 py-1.5 font-medium text-neutral-900">
                  {r.mut_aa} {i === 0 && <span className="text-[10px] text-neutral-500">{t('scan.strongest')}</span>}
                </td>
                <td className="mono px-2 py-1.5 text-right">{r.local_rmsd.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.global_rmsd.toFixed(2)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.tm_score.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.dplddt >= 0 ? `+${r.dplddt.toFixed(1)}` : r.dplddt.toFixed(1)}</td>
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
      <div className="text-[10px] text-neutral-400">
        {t('scan.note')}
      </div>
    </div>
  )
}

function ScanChart({ rows, wtAA }: { rows: ScanRow[]; wtAA: string }) {
  const { t } = useI18n()
  const data = [{
    x: rows.map((r) => r.mut_aa),
    y: rows.map((r) => r.local_rmsd),
    type: 'bar' as const,
    marker: {
      color: rows.map((_, i) => (i === 0 ? '#b91c1c' : '#111111')),
    },
  }]
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 50 },
    paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
    font: { color: '#525252', size: 11 },
    xaxis: { title: { text: t('scan.xaxis.subst', { wt: wtAA }) }, linecolor: '#d4d4d4' },
    yaxis: { title: { text: 'local RMSD, Å' }, gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
  }
  return <Plot data={data} layout={layout} />
}