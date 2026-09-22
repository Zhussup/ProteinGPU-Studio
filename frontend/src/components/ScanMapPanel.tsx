// ScanMapPanel: the sensitivity map / "wind rose" (dum.md §5).
// Heatmap (positions × compass directions), ranked table with rose-glyph
// sparklines, a big rose for the selected position, and "paint 3D" — pushes
// the per-residue sensitivity scalar into the molecule viewer.
import { Suspense, lazy, useMemo, useState } from 'react'
import type { MapPosition, ScanMapResult } from '../lib/types'
import { useI18n, type Interp, type Key } from '../i18n'
import RoseGlyph, { bucketColor, HEAT_BUCKETS, PETAL_DIRS, rank } from './RoseGlyph'

const Plot = lazy(() => import('./PlotlyChart'))

export type PaintMetric = 'v_max' | 'v_med'

// quadrant badges: hot → cold
const QUAD_CLS: Record<MapPosition['stats']['quadrant'], string> = {
  hedgehog: 'bg-red-700 text-white',
  needle: 'bg-neutral-900 text-white',
  clover: 'bg-neutral-600 text-white',
  disk: 'border border-neutral-300 text-neutral-500',
}
const QUAD_KEY: Record<MapPosition['stats']['quadrant'], Key> = {
  hedgehog: 'map.quad.hedgehog',
  needle: 'map.quad.needle',
  disk: 'map.quad.disk',
  clover: 'map.quad.clover',
}
const QUAD_TITLE: Record<MapPosition['stats']['quadrant'], Key> = {
  hedgehog: 'map.quad.hedgehogTitle',
  needle: 'map.quad.needleTitle',
  disk: 'map.quad.diskTitle',
  clover: 'map.quad.cloverTitle',
}

export interface ScanMapPanelProps {
  result: ScanMapResult
  jobId?: string | null
  paintedMetric: PaintMetric | null
  onPaint: (scores: (number | null)[], metric: PaintMetric) => void
  onClearPaint: () => void
}

export default function ScanMapPanel({ result, jobId, paintedMetric, onPaint, onClearPaint }: ScanMapPanelProps) {
  const { t } = useI18n()
  const [metric, setMetric] = useState<PaintMetric>('v_max')
  const positions = result.positions
  const L = result.wt_sequence.length

  // ranked rows for the table (desc by the chosen scalar)
  const sorted = useMemo(() => {
    const key = metric === 'v_max' ? 'pctl_v_max' : 'pctl_v_med'
    return [...positions].sort((a, b) => b.stats[key] - a.stats[key])
  }, [positions, metric])

  const [selectedPos, setSelectedPos] = useState<number | null>(null)
  const selected: MapPosition | undefined =
    positions.find((p) => p.pos === selectedPos) ?? sorted[0]

  const paint = () => {
    const key = metric === 'v_max' ? 'pctl_v_max' : 'pctl_v_med'
    const scores: (number | null)[] = new Array(L).fill(null)
    for (const p of positions) scores[p.pos - 1] = p.stats[key]
    onPaint(scores, metric)
  }

  return (
    <div className="space-y-4">
      <div className="border-l-2 border-neutral-900 bg-neutral-50 p-3 text-sm text-neutral-800">
        {result.summary}
      </div>

      {/* metric + 3D paint + dataset artifacts */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-neutral-500">{t('map.metricLabel')}</span>
        <button
          onClick={() => setMetric('v_max')}
          className={`border px-2 py-1 ${
            metric === 'v_max' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-300 text-neutral-700 hover:border-neutral-900'
          }`}
        >
          {t('map.metric.vmax')}
        </button>
        <button
          onClick={() => setMetric('v_med')}
          className={`border px-2 py-1 ${
            metric === 'v_med' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-300 text-neutral-700 hover:border-neutral-900'
          }`}
        >
          {t('map.metric.vmed')}
        </button>
        <button
          onClick={paint}
          title={t('map.paintTitle')}
          className="border border-red-700 px-2 py-1 text-red-800 hover:bg-red-50"
        >
          {t('map.paint')}
        </button>
        {paintedMetric && (
          <button onClick={onClearPaint} className="text-neutral-500 underline hover:text-neutral-900">
            {t('map.clearPaint')}
          </button>
        )}
        {jobId && (
          <span className="ml-auto flex gap-3">
            <a
              href={`/api/v1/files/${jobId}/scan_map.csv`}
              download
              className="text-neutral-500 underline hover:text-neutral-900"
            >
              {t('map.csv')}
            </a>
            <a
              href={`/api/v1/files/${jobId}/scan_map.json`}
              download
              className="text-neutral-500 underline hover:text-neutral-900"
            >
              {t('map.json')}
            </a>
          </span>
        )}
      </div>
      {paintedMetric && (
        <div className="text-[10px] text-neutral-400">
          {t('map.painted', { metric: paintedMetric === 'v_max' ? t('map.metric.vmax') : t('map.metric.vmed') })}
        </div>
      )}

      {/* heat map: positions × fixed compass directions (the length channel) */}
      <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
        <MapHeatmap result={result} />
      </Suspense>

      {/* big rose of the selected position */}
      {selected && <RoseDetail pos={selected} />}

      {/* ranked table with rose sparklines */}
      <div className="max-h-96 overflow-y-auto border border-neutral-200">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-neutral-100 text-neutral-600">
            <tr>
              <th className="px-2 py-1.5 text-left">{t('map.h.pos')}</th>
              <th className="px-2 py-1.5 text-left">{t('map.h.rose')}</th>
              <th className="px-2 py-1.5 text-left">{t('map.h.quadrant')}</th>
              <th className="px-2 py-1.5 text-right">{t('map.h.max')}</th>
              <th className="px-2 py-1.5 text-right">{t('map.h.med')}</th>
              <th className="px-2 py-1.5 text-right">{t('map.h.pctl')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const key = metric === 'v_max' ? 'pctl_v_max' : 'pctl_v_med'
              return (
                <tr
                  key={p.pos}
                  onClick={() => setSelectedPos(p.pos)}
                  className={`cursor-pointer border-t border-neutral-100 hover:bg-neutral-100 ${
                    selected?.pos === p.pos ? 'bg-neutral-100' : 'bg-white'
                  }`}
                >
                  <td className="mono px-2 py-1.5 font-medium text-neutral-900">
                    {p.wt_aa}
                    {p.pos}
                  </td>
                  <td className="px-2 py-1">
                    <TableRose p={p} />
                  </td>
                  <td className="px-2 py-1.5">
                    <span
                      className={`mono px-1.5 py-0.5 text-[10px] ${QUAD_CLS[p.stats.quadrant]}`}
                      title={t(QUAD_TITLE[p.stats.quadrant])}
                    >
                      {t(QUAD_KEY[p.stats.quadrant])}
                    </span>
                  </td>
                  <td className="mono px-2 py-1.5 text-right">{p.stats.max_local_rmsd.toFixed(2)}</td>
                  <td className="mono px-2 py-1.5 text-right text-neutral-500">{p.stats.median_local_rmsd.toFixed(2)}</td>
                  <td className="px-2 py-1.5">
                    <PctlBar v={p.stats[key]} />
                    <span className="mono ml-1 text-[10px] text-neutral-500">{p.stats[key].toFixed(2)}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="text-[10px] text-neutral-400">
        {t('map.note')}
      </div>
    </div>
  )
}

// one position's 19 rows as petals: length = |ΔpLDDT| percentile (backend
// pctl), color intensity = local RMSD rank within the position (same rank
// convention as the backend's percentile_rank). `fmt` localizes the hover tip.
export function petalsOf(p: MapPosition, fmt: (m: string, pctl: string, rmsd: string) => string) {
  return p.rows.map((r) => ({
    aa: r.mut_aa,
    len: r.pctl,
    intensity: rank(r.local_rmsd, p.rows.map((x) => x.local_rmsd)),
    tip: fmt(`${p.wt_aa}${p.pos}${r.mut_aa}`, r.pctl.toFixed(2), r.local_rmsd.toFixed(2)),
  }))
}

function TableRose({ p }: { p: MapPosition }) {
  const { t } = useI18n()
  return (
    <RoseGlyph
      petals={petalsOf(p, petalTip(t))}
      wtSlot={PETAL_DIRS.indexOf(p.wt_aa)}
      size={44}
      title={t('map.roseTitle', { m: `${p.wt_aa}${p.pos}` })}
    />
  )
}

// t-bound tip formatter shared by the table and the detail rose
function petalTip(t: (k: Key, params?: Interp) => string) {
  return (m: string, pctl: string, rmsd: string) => t('map.petalTip', { m, pctl, rmsd })
}

function RoseDetail({ pos }: { pos: MapPosition }) {
  const { t } = useI18n()
  return (
    <div className="flex items-start gap-4 border border-neutral-200 bg-neutral-50 p-3">
      <RoseGlyph petals={petalsOf(pos, petalTip(t))} wtSlot={PETAL_DIRS.indexOf(pos.wt_aa)} size={150} />
      <div className="min-w-0 flex-1 space-y-1.5 text-xs text-neutral-700">
        <div className="text-sm font-medium text-neutral-900">
          {t('map.detailTitle', { m: `${pos.wt_aa}${pos.pos}` })}
        </div>
        <div>
          <span className={`mono px-1.5 py-0.5 text-[10px] ${QUAD_CLS[pos.stats.quadrant]}`}>
            {t(QUAD_KEY[pos.stats.quadrant])}
          </span>
          <span className="ml-2 text-neutral-500">{t(QUAD_TITLE[pos.stats.quadrant])}</span>
        </div>
        <div>
          {t('map.detailMax', { v: pos.stats.max_local_rmsd.toFixed(2) })} ·{' '}
          {t('map.detailMed', { v: pos.stats.median_local_rmsd.toFixed(2) })} ·{' '}
          {t('map.detailSharp', { v: pos.stats.sharpness.toFixed(1) })}
        </div>
        <div className="text-[10px] text-neutral-500">
          {t('map.lenChannel')} · {t('map.colorChannel')}
        </div>
      </div>
    </div>
  )
}

function PctlBar({ v }: { v: number }) {
  return (
    <span className="inline-block h-1.5 w-14 align-middle bg-neutral-100">
      <span
        className="block h-full bg-neutral-900"
        style={{ width: `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%` }}
      />
    </span>
  )
}

// heat map: x = measured positions, y = the FIXED 20-letter compass; z = the
// length channel (per-row pctl of |ΔpLDDT_local|, null at the WT slot)
function MapHeatmap({ result }: { result: ScanMapResult }) {
  const { t } = useI18n()
  const positions = result.positions
  const dirs = PETAL_DIRS.split('')
  const z = dirs.map((aa) =>
    positions.map((p) => {
      const row = p.rows.find((r) => r.mut_aa === aa)
      return row ? row.pctl : null
    }),
  )
  const custom = dirs.map((aa) =>
    positions.map((p) => {
      const row = p.rows.find((r) => r.mut_aa === aa)
      return row ? t('map.heatTip', {
        m: `${p.wt_aa}${p.pos}${aa}`,
        pctl: row.pctl.toFixed(2),
        rmsd: row.local_rmsd.toFixed(2),
      }) : ''
    }),
  )
  const data = [{
    x: positions.map((p) => p.pos),
    y: dirs,
    z,
    customdata: custom,
    type: 'heatmap' as const,
    colorscale: [[0, '#ffffff'], [1, '#b91c1c']],
    zmin: 0,
    zmax: 1,
    hovertemplate: '%{customdata}<extra>pctl %{z}</extra>',
    colorbar: { thickness: 10, len: 0.9 },
  }]
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 40 },
    paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
    font: { color: '#525252', size: 11 },
    xaxis: { title: { text: t('res.xaxis.residue') }, linecolor: '#d4d4d4' },
    yaxis: { linecolor: '#d4d4d4' },
  }
  return (
    <div>
      <div className="mb-1 text-[11px] text-neutral-500">{t('map.heatmap')}</div>
      <Plot data={data} layout={layout} />
      {/* bucket legend for the 3D paint ramp */}
      <div className="mt-1 flex items-center gap-1 text-[10px] text-neutral-500">
        <span>0</span>
        {Array.from({ length: HEAT_BUCKETS }, (_, i) => (
          <span key={i} className="inline-block h-2.5 w-4" style={{ background: bucketColor(i) }} />
        ))}
        <span>1 · {t('map.heatLegend')}</span>
      </div>
    </div>
  )
}