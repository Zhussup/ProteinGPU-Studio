// ScanMapPanel: карта чувствительности / «роза ветров» (dum.md §5).
// Тепловая карта (позиции × направления компаса), ранжированная таблица со
// спарклайнами-розами, большая роза для выбранной позиции и «раскрасить 3D» —
// проталкивает скаляр чувствительности по остаткам во вьюер молекулы.
// ScanMapPanel：敏感性图谱 / “风玫瑰”（dum.md §5）。
// 热图（位点 × 罗盘方向）、带玫瑰小图的排序表格、所选位点的大玫瑰，
// 以及“着色 3D”——把逐残基敏感性标量推入分子查看器。
import { Suspense, lazy, useMemo, useState } from 'react'
import type { MapPosition, ScanMapResult } from '../lib/types'
import { useI18n, type Interp, type Key } from '../i18n'
import RoseGlyph, { bucketColor, HEAT_BUCKETS, PETAL_DIRS, rank } from './RoseGlyph'

const Plot = lazy(() => import('./PlotlyChart'))

export type PaintMetric = 'v_max' | 'v_med'

// бейджи квадрантов: горячий → холодный
// 象限徽章：热 → 冷
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

  // отсортированные строки для таблицы (по убыванию выбранного скаляра)
  // 表格的排序行（按所选标量降序）
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

      {/* метрика + раскраска 3D + артефакты датасета */}
      {/* 指标 + 3D 着色 + 数据集工件 */}
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

      {/* тепловая карта: позиции × фиксированные направления компаса (канал длины) */}
      {/* 热图：位置 × 固定罗盘方向（长度通道） */}
      <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
        <MapHeatmap result={result} />
      </Suspense>

      {/* большая роза выбранной позиции */}
      {/* 所选位点的大玫瑰 */}
      {selected && <RoseDetail pos={selected} />}

      {/* ранжированная таблица со спарклайнами-розами */}
      {/* 带玫瑰小图的排序表格 */}
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

// 19 строк позиции как лепестки: длина = перцентиль |ΔpLDDT| (pctl бэкенда),
// интенсивность цвета = ранг local RMSD внутри позиции (та же конвенция rank,
// что у percentile_rank бэкенда). `fmt` локализует текст наведения.
// 以花瓣呈现某位点的 19 行：长度 = |ΔpLDDT| 百分位（后端 pctl），
// 颜色强度 = 位点内 local RMSD 的排名（与后端 percentile_rank 同一
// 约定）。`fmt` 用于本地化悬停提示。
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

// привязанный к t форматтер подсказок, общий для таблицы и детальной розы
// 表格与详情玫瑰共享的、绑定 t 的提示格式化器
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

// тепловая карта: x = измеренные позиции, y = ФИКСИРОВАННЫЙ 20-буквенный компас;
// z = канал длины (по-строчный pctl |ΔpLDDT_local|, null в слоте WT)
// 热图：x = 已测位置，y = 固定的 20 字母罗盘；
// z = 长度通道（|ΔpLDDT_local| 的逐行 pctl，WT 槽位为 null）
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
      {/* легенда корзин для шкалы 3D-раскраски */}
      {/* 3D 着色色带的分档图例 */}
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