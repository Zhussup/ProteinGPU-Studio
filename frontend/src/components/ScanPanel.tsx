// ScanPanel: results of the saturation scan (all 19 substitutions).
// Ranked table + bar chart; clicking a row shows that mutant in the viewer.
import { Suspense, lazy } from 'react'
import type { ScanResult, ScanRow } from '../lib/types'

const Plot = lazy(() => import('../components/PlotlyChart'))

const VERDICT_CLS: Record<ScanRow['interpretation'], string> = {
  stable: 'border border-neutral-300 text-neutral-500',
  moderate: 'bg-neutral-600 text-white',
  critical: 'bg-red-700 text-white',
}
const VERDICT_LABEL = { stable: 'стаб.', moderate: 'умерен.', critical: 'крит.' }

export interface ScanPanelProps {
  result: ScanResult
  onPickRow: (mutAA: string) => void
  pickedAA?: string | null
}

export default function ScanPanel({ result, onPickRow, pickedAA }: ScanPanelProps) {
  const rows = result.rows

  return (
    <div className="space-y-4">
      <div className="border-l-2 border-neutral-900 bg-neutral-50 p-3 text-sm text-neutral-800">
        {result.summary}
      </div>

      <Suspense fallback={<div className="text-xs text-neutral-400">график загружается…</div>}>
        <ScanChart rows={rows} wtAA={result.wt_aa} />
      </Suspense>

      <div className="max-h-80 overflow-y-auto border border-neutral-200">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-neutral-100 text-neutral-600">
            <tr>
              <th className="px-2 py-1.5 text-left">мутация</th>
              <th className="px-2 py-1.5 text-right">local RMSD, Å</th>
              <th className="px-2 py-1.5 text-right">global</th>
              <th className="px-2 py-1.5 text-right">TM</th>
              <th className="px-2 py-1.5 text-right">ΔpLDDT</th>
              <th className="px-2 py-1.5 text-center">вердикт</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.mut_aa}
                onClick={() => onPickRow(r.mut_aa)}
                title="показать наложение в вьюере"
                className={`cursor-pointer border-t border-neutral-100 hover:bg-neutral-100 ${
                  r.mut_aa === pickedAA ? 'bg-neutral-100' : 'bg-white'
                }`}
              >
                <td className="mono px-2 py-1.5 font-medium text-neutral-900">
                  {r.mut_aa} {i === 0 && <span className="text-[10px] text-neutral-500">← сильнейший</span>}
                </td>
                <td className="mono px-2 py-1.5 text-right">{r.local_rmsd.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.global_rmsd.toFixed(2)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.tm_score.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.dplddt >= 0 ? `+${r.dplddt.toFixed(1)}` : r.dplddt.toFixed(1)}</td>
                <td className="px-2 py-1.5 text-center">
                  <span className={`mono px-1.5 py-0.5 text-[10px] ${VERDICT_CLS[r.interpretation]}`}>
                    {VERDICT_LABEL[r.interpretation]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-[10px] text-neutral-400">
        таблица отсортирована по локальному RMSD (окно ±10 от мутации); клик по строке —
        наложение этой мутантной структуры на WT
      </div>
    </div>
  )
}

function ScanChart({ rows, wtAA }: { rows: ScanRow[]; wtAA: string }) {
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
    xaxis: { title: { text: `замена ${wtAA} → X` }, linecolor: '#d4d4d4' },
    yaxis: { title: { text: 'local RMSD, Å' }, gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
  }
  return <Plot data={data} layout={layout} />
}