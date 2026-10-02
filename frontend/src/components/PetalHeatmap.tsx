// PetalHeatmap: тепловая карта «позиции × фиксированный компас», вытянутая из
// ScanMapPanel (dum.md §5) и переиспользуемая панелью PLM-скрина. Точки входа
// дают сами значения: pctl — канал длины/цвета (0..1, null в слоте WT), tip —
// локализованный текст наведения. Компас — общий с бэкендом PETAL_DIRS.
// PetalHeatmap：“位置 × 固定罗盘”热图，自 ScanMapPanel 抽出，
// PLM 筛查面板复用。调用方提供数值：pctl 为长度/颜色通道（0..1，WT 槽为 null），
// tip 为本地化悬停文本。罗盘与后端共用。
import { Suspense, lazy } from 'react'
import { useI18n } from '../i18n'
import { HEAT_BUCKETS, bucketColor, PETAL_DIRS } from './RoseGlyph'

const Plot = lazy(() => import('./PlotlyChart'))

export interface PetalRow {
  mut_aa: string
  pctl: number
  tip: string
}

export interface PetalHeatmapProps {
  // позиции с 19 строками (компасный порядок, слот WT отсутствует)
  // 带 19 行（罗盘顺序，无 WT 槽位）的位置
  positions: { pos: number; rows: PetalRow[] }[]
  title: string
  xTitle: string
  legendText: string
}

export default function PetalHeatmap({ positions, title, xTitle, legendText }: PetalHeatmapProps) {
  const { t } = useI18n()
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
      return row ? row.tip : ''
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
    xaxis: { title: { text: xTitle }, linecolor: '#d4d4d4' },
    yaxis: { linecolor: '#d4d4d4' },
  }
  return (
    <div>
      <div className="mb-1 text-[11px] text-neutral-500">{title}</div>
      <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
        <Plot data={data} layout={layout} />
      </Suspense>
      {/* легенда корзин для шкалы 3D-раскраски */}
      {/* 3D 着色色带的分档图例 */}
      <div className="mt-1 flex items-center gap-1 text-[10px] text-neutral-500">
        <span>0</span>
        {Array.from({ length: HEAT_BUCKETS }, (_, i) => (
          <span key={i} className="inline-block h-2.5 w-4" style={{ background: bucketColor(i) }} />
        ))}
        <span>1 · {legendText}</span>
      </div>
    </div>
  )
}