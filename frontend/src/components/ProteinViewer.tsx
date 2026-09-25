// ProteinViewer: обозреватель белковой последовательности (docs/viewer_design.md).
// Canvas рисует информационные треки; прозрачный SVG-оверлей сверху несёт
// интеракцию (зоны клика по остатку, перекрестие, тултип). Оба читают пиксельные
// координаты из lib/viewerGeometry — единственный источник геометрии.
// Клик в любом месте = текущая позиция: панель деталей, перекрестие и красные
// стики MoleculeViewer следуют за ней (кросс-хайлайт, §4).
// ProteinViewer：蛋白质序列浏览器（docs/viewer_design.md）。
// canvas 绘制数据轨道；上方透明 SVG 覆盖层承载交互（逐残基点击区、
// 十字线、提示框）。两者均从 lib/viewerGeometry 读取像素坐标——几何唯一来源。
// 点击任意位置 = 当前位置：详情面板、十字线与 MoleculeViewer 的红色
// 棍棒随之联动（交叉高亮，§4）。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { EnsembleResult, MutationResult, ScanResult } from '../lib/types'
import { useI18n, type Key, type TFn } from '../i18n'
import {
  AXIS_HEIGHT, PAD_X, TRACKS, buildGeometry, computeWindow, tickStep, trackHeight,
  type Geometry, type TrackId,
} from '../lib/viewerGeometry'

const RED = '#b91c1c' // тот же строгий красный, что в MoleculeViewer | 与 MoleculeViewer 相同的严格红
const INTERP_FILL: Record<'stable' | 'moderate' | 'critical', string> = {
  stable: '#d4d4d4',
  moderate: '#6b7280',
  critical: '#b91c1c',
}

// Подписи треков рисуются на canvas — переводятся через словарь.
// 轨道标签绘制在 canvas 上——通过字典翻译。
const TRACK_LABEL_KEYS: Record<TrackId, Key> = {
  sequence: 'track.sequence',
  plddt: 'track.plddt',
  mutation: 'track.mutation',
  scan: 'track.scan',
  domains: 'track.domains',
  variants: 'track.variants',
}

export interface ProteinViewerProps {
  sequence: string // буквы белка, без FASTA-заголовка | 蛋白字母，无 FASTA 头
  position: number // текущая позиция, с 1 (разделяется с MutationPicker → 3D) | 当前位置，从 1 起（与 MutationPicker → 3D 共享）
  onPositionChange: (p: number) => void
  plddtWt?: number[] | null // индекс i = позиция i+1 | 索引 i = 位置 i+1
  result?: MutationResult | null
  scan?: ScanResult | null
  ensemble?: EnsembleResult | null
}

type ViewMode = 'whole' | 'window'

export default function ProteinViewer({
  sequence, position, onPositionChange, plddtWt, result, scan, ensemble,
}: ProteinViewerProps) {
  const { t } = useI18n()
  const [mode, setMode] = useState<ViewMode>('whole')
  const [width, setWidth] = useState(0)
  const [hover, setHover] = useState<number | null>(null)
  // callback-ref (не эффект на монтирование): хост-див появляется лишь когда
  // есть последовательность — пустая ветка возвращается раньше — поэтому
  // ResizeObserver должен подключаться при появлении хоста, а не на маунт компонента.
  // 使用回调 ref（而非挂载时的 effect）：宿主 div 只在有序列时才挂载——
  // 空状态分支提前返回——因此 ResizeObserver 应在宿主出现时附加，
  // 而不是在组件挂载时。
  const [hostEl, setHostEl] = useState<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mapRef = useRef<HTMLCanvasElement>(null)

  const length = sequence.length
  const sc = scan ?? null
  const en = ensemble ?? null
  // зажимаем defensively: родитель тоже зажимает, но последовательность может измениться первой
  // 防御性钳制：父组件也会钳制，但序列可能先变化
  const cur = Math.min(Math.max(1, position), Math.max(1, length))

  // ResizeObserver → ширина → геометрия
  // ResizeObserver → 宽度 → 几何
  useEffect(() => {
    if (!hostEl) return
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setWidth(e.contentRect.width)
    })
    ro.observe(hostEl)
    return () => ro.disconnect()
  }, [hostEl])

  const win = useMemo(
    () => computeWindow(mode, length, cur),
    [mode, length, cur],
  )
  // левый отступ: достаточно широкий для самого длинного переведённого названия трека
  // (замеряем на canvas; подписи CJK/русские шире дефолтных 28px)
  // 左留白：足够容纳最长的已翻译轨道名
  //（用 canvas 测量；CJK/俄语标签比默认 28px 宽）
  const padX = useMemo(() => {
    const ctx = document.createElement('canvas').getContext('2d')
    if (!ctx) return PAD_X
    ctx.font = '9px ui-sans-serif, system-ui, sans-serif'
    let w = 0
    for (const tr of TRACKS) {
      w = Math.max(w, ctx.measureText(t(TRACK_LABEL_KEYS[tr.id])).width)
    }
    return Math.max(PAD_X, Math.ceil(w) + 6)
  }, [t])
  const geom = useMemo<Geometry | null>(
    () => (width > 0 && length > 0 ? buildGeometry(width, length, win, padX) : null),
    [width, length, win, padX],
  )

  const mutation = useMemo(() => {
    if (result) return { position: result.position, wt_aa: result.wt_aa, mut_aa: result.mutant_aa }
    if (length > 0 && position >= 1 && position <= length) {
      return { position, wt_aa: sequence[position - 1], mut_aa: '' }
    }
    return null
  }, [result, position, sequence, length])

  // --- слой данных на canvas ---
  // --- canvas 数据层 ---
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !geom) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = geom.width * dpr
    canvas.height = geom.height * dpr
    canvas.style.width = `${geom.width}px`
    canvas.style.height = `${geom.height}px`
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, geom.width, geom.height)
    ctx.font = '10px ui-monospace, monospace'
    ctx.textBaseline = 'middle'

    drawAxis(ctx, geom)
    drawTracksBackground(ctx, geom, t)

    // окно локального RMSD (±10 от сайта мутации) — светлая полоса под данными
    // 局部 RMSD 窗口（距突变位点 ±10）——数据下方的浅色条带
    const lw = result?.rmsd?.local_window
    if (lw) drawBand(ctx, geom, lw[0], lw[1], '#f0f0f0')

    drawSequence(ctx, geom, sequence, cur)
    drawPlddt(ctx, geom, sequence, plddtWt, t)
    drawMutation(ctx, geom, mutation)
    drawScan(ctx, geom, sc, t)
    drawVariants(ctx, geom, en, t)
    drawTrackPlaceholders(ctx, geom, t)

    if (hover) drawVLine(ctx, geom, hover, '#a3a3a3', true)
    drawVLine(ctx, geom, cur, '#111111', false)
  }, [geom, sequence, plddtWt, mutation, sc, en, result, hover, cur, t])

  // --- мини-карта: полоса ориентирования с текущим окном ---
  // --- 小地图：带当前窗口的定位条 ---
  const mapH = 20
  useEffect(() => {
    const canvas = mapRef.current
    if (!canvas || width === 0 || length === 0) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = mapH * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${mapH}px`
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, mapH)

    const x0 = padX
    const w = width - 2 * x0
    ctx.fillStyle = '#e5e5e5'
    ctx.fillRect(x0, 7, w, 6)
    const wx = x0 + ((win.start - 1) / length) * w
    const ww = ((win.end - win.start + 1) / length) * w
    ctx.strokeStyle = '#111111'
    ctx.lineWidth = 1
    ctx.strokeRect(wx + 0.5, 4.5, Math.max(2, ww - 1), 11)
    if (length > 1) {
      ctx.fillStyle = '#737373'
      ctx.font = '9px ui-monospace, monospace'
      ctx.textBaseline = 'top'
      ctx.fillText('1', x0, 7)
      const last = String(length)
      ctx.fillText(last, x0 + w - last.length * 6, 7)
    }
  }, [width, length, win, padX])

  const onMapClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (length === 0) return
    const rect = e.currentTarget.getBoundingClientRect()
    const frac = (e.clientX - rect.left - padX) / (rect.width - 2 * padX)
    const pos = Math.round(1 + Math.min(1, Math.max(0, frac)) * (length - 1))
    if (length > 2 * 50 + 1) setMode('window')
    onPositionChange(pos)
  }, [length, onPositionChange, padX])

  // --- SVG-слой интеракции: зоны попадания на каждый видимый остаток ---
  // --- SVG 交互层：每个可见残基的点击区 ---
  const hitZones = useMemo(() => {
    if (!geom) return []
    const zones: { pos: number; x: number; w: number }[] = []
    for (let p = win.start; p <= win.end; p++) zones.push({ pos: p, x: geom.xFor(p), w: geom.colW })
    return zones
  }, [geom, win])

  if (length === 0) {
    return (
      <div className="panel p-4">
        <Header mode={mode} length={0} onMode={() => {}} onToMutation={() => {}} mutation={null} />
        <div className="text-xs text-neutral-500">
          {t('pv.empty')}
        </div>
      </div>
    )
  }

  const hoverInfo = hover && geom
    ? describePosition(hover, sequence, plddtWt, mutation, sc, result, en, t)
    : null
  const curInfo = describePosition(cur, sequence, plddtWt, mutation, sc, result, en, t)

  return (
    <div className="panel p-4">
      <Header
        mode={mode}
        length={length}
        onMode={(m) => setMode(m)}
        onToMutation={() => {
          if (mutation) {
            if (length > 2 * 50 + 1) setMode('window')
            onPositionChange(mutation.position)
          }
        }}
        mutation={mutation}
      />

      <div ref={setHostEl} className="relative select-none" style={{ height: geom?.height ?? 0 }}>
        <canvas ref={canvasRef} className="block" />
        {geom && (
          <svg
            className="absolute inset-0"
            width={geom.width}
            height={geom.height}
            onMouseLeave={() => setHover(null)}
          >
            {hitZones.map((z) => (
              <rect
                key={z.pos}
                x={z.x}
                y={AXIS_HEIGHT}
                width={z.w}
                height={geom.height - AXIS_HEIGHT}
                fill="transparent"
                onMouseEnter={() => setHover(z.pos)}
                onClick={() => onPositionChange(z.pos)}
              />
            ))}
          </svg>
        )}
        {hoverInfo && geom && (
          <div
            className="pointer-events-none absolute z-10 border border-neutral-300 bg-white px-2 py-1 text-[11px] leading-tight text-neutral-700 shadow-sm"
            style={{
              left: Math.min(Math.max(geom.centerFor(hover!), 60), geom.width - 60),
              top: AXIS_HEIGHT + 4,
              transform: 'translateX(-50%)',
            }}
          >
            {hoverInfo}
          </div>
        )}
      </div>

      <canvas ref={mapRef} className="block cursor-pointer" onClick={onMapClick} />

      <div className="mt-3 border-t border-neutral-200 pt-3 text-[11px] leading-relaxed text-neutral-700">
        {curInfo}
      </div>
    </div>
  )
}

function Header({
  mode, length, onMode, onToMutation, mutation,
}: {
  mode: ViewMode
  length: number
  onMode: (m: ViewMode) => void
  onToMutation: () => void
  mutation: { position: number; wt_aa: string; mut_aa: string } | null
}) {
  const { t } = useI18n()
  const windowable = length > 2 * 50 + 1
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-sm font-medium text-neutral-900">{t('pv.title')}</h3>
      <div className="flex items-center gap-1 text-[11px]">
        <button
          className={`border px-2 py-0.5 ${mode === 'whole' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-300 bg-white text-neutral-700'}`}
          onClick={() => onMode('whole')}
        >
          {t('pv.whole')}
        </button>
        <button
          disabled={!windowable}
          className={`border px-2 py-0.5 disabled:opacity-40 ${mode === 'window' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-300 bg-white text-neutral-700'}`}
          onClick={() => onMode('window')}
        >
          {t('pv.window')}
        </button>
        {mutation && (
          <button className="border border-neutral-300 bg-white px-2 py-0.5 text-neutral-700" onClick={onToMutation}>
            {t('pv.toMutation')}
          </button>
        )}
      </div>
    </div>
  )
}

// --- хелперы отрисовки (все координаты из Geometry) ---
// --- 绘制辅助函数（所有坐标来自 Geometry） ---

function drawAxis(ctx: CanvasRenderingContext2D, g: Geometry) {
  const step = tickStep(g.win.end - g.win.start + 1, g.plotW)
  ctx.fillStyle = '#737373'
  ctx.strokeStyle = '#d4d4d4'
  ctx.textAlign = 'center'
  ctx.beginPath()
  for (let p = Math.ceil(g.win.start / step) * step; p <= g.win.end; p += step) {
    const x = g.centerFor(p)
    ctx.fillText(String(p), x, AXIS_HEIGHT / 2)
    ctx.moveTo(x + 0.5, AXIS_HEIGHT - 5)
    ctx.lineTo(x + 0.5, AXIS_HEIGHT)
  }
  ctx.stroke()
  ctx.textAlign = 'left'
}

function drawTracksBackground(
  ctx: CanvasRenderingContext2D, g: Geometry, t: TFn,
) {
  // название трека в левом поле + волосяная линия под каждым треком
  // 左侧边距的轨道名 + 每条轨道下的细线
  ctx.font = '9px ui-sans-serif, system-ui, sans-serif'
  for (const tr of TRACKS) {
    const top = g.trackTopOf(tr.id)
    ctx.fillStyle = '#a3a3a3'
    ctx.textAlign = 'right'
    ctx.save()
    ctx.translate(g.plotX - 4, top + tr.height / 2)
    ctx.fillText(t(TRACK_LABEL_KEYS[tr.id]), 0, 0)
    ctx.restore()
    ctx.strokeStyle = '#f0f0f0'
    ctx.beginPath()
    ctx.moveTo(g.plotX, top + tr.height + 1.5)
    ctx.lineTo(g.width, top + tr.height + 1.5)
    ctx.stroke()
  }
  ctx.textAlign = 'left'
}

function drawBand(
  ctx: CanvasRenderingContext2D, g: Geometry, start: number, end: number, color: string,
) {
  const x0 = g.xFor(Math.max(g.win.start, start))
  const x1 = g.xFor(Math.min(g.win.end, end) + 1)
  ctx.fillStyle = color
  for (const t of TRACKS) {
    const top = g.trackTopOf(t.id)
    ctx.fillRect(x0, top, x1 - x0, trackHeight(t.id))
  }
}

function drawVLine(
  ctx: CanvasRenderingContext2D, g: Geometry, pos: number, color: string, dashed: boolean,
) {
  const x = Math.round(g.centerFor(pos)) + 0.5
  ctx.strokeStyle = color
  ctx.setLineDash(dashed ? [3, 3] : [])
  ctx.beginPath()
  ctx.moveTo(x, AXIS_HEIGHT)
  ctx.lineTo(x, g.height)
  ctx.stroke()
  ctx.setLineDash([])
}

function drawSequence(
  ctx: CanvasRenderingContext2D, g: Geometry, seq: string, cur: number,
) {
  const top = g.trackTopOf('sequence')
  const h = trackHeight('sequence')
  const mid = top + h / 2 + 5
  if (g.colW < 8) return // буквы нечитаемы — ось и тултип несут информацию | 字母不可读——坐标轴与提示框承载信息
  ctx.font = '11px ui-monospace, monospace'
  ctx.textAlign = 'center'
  for (let p = g.win.start; p <= g.win.end; p++) {
    if (p === cur) continue // нарисован подсвеченным ниже | 在下方以高亮绘制
    ctx.fillStyle = '#404040'
    ctx.fillText(seq[p - 1], g.centerFor(p), mid)
  }
  // текущая позиция: чёрная ячейка, белая буква
  // 当前位置：黑底白字
  ctx.fillStyle = '#111111'
  ctx.fillRect(g.xFor(cur), top + 2, g.colW, h - 4)
  ctx.fillStyle = '#ffffff'
  ctx.fillText(seq[cur - 1], g.centerFor(cur), mid)
  ctx.textAlign = 'left'
}

function drawPlddt(
  ctx: CanvasRenderingContext2D, g: Geometry, seq: string,
  plddt: number[] | null | undefined, t: TFn,
) {
  const top = g.trackTopOf('plddt')
  const h = trackHeight('plddt')
  const baseline = top + h - 3
  const inner = h - 12
  // сетка на 50 / 90
  // 50 / 90 处的网格线
  ctx.strokeStyle = '#e5e5e5'
  ctx.setLineDash([2, 3])
  for (const v of [50, 90]) {
    const y = baseline - (v / 100) * inner
    ctx.beginPath()
    ctx.moveTo(g.plotX, y)
    ctx.lineTo(g.width, y)
    ctx.stroke()
    ctx.fillStyle = '#a3a3a3'
    ctx.fillText(String(v), g.plotX, y - 5)
  }
  ctx.setLineDash([])

  if (!plddt || plddt.length !== seq.length) {
    ctx.fillStyle = '#a3a3a3'
    ctx.fillText(t('pv.plddtNoData'), g.plotX + 16, top + h / 2)
    return
  }
  ctx.fillStyle = '#111111'
  const bw = Math.max(1, g.colW * 0.7)
  for (let p = g.win.start; p <= g.win.end; p++) {
    const v = plddt[p - 1]
    if (v == null) continue
    const bh = Math.max(1, (v / 100) * inner)
    ctx.fillRect(g.xFor(p) + (g.colW - bw) / 2, baseline - bh, bw, bh)
  }
  ctx.strokeStyle = '#d4d4d4'
  ctx.beginPath()
  ctx.moveTo(PAD_X, baseline + 0.5)
  ctx.lineTo(g.width, baseline + 0.5)
  ctx.stroke()
}

function drawMutation(
  ctx: CanvasRenderingContext2D,
  g: Geometry,
  mutation: { position: number; wt_aa: string; mut_aa: string } | null,
) {
  const top = g.trackTopOf('mutation')
  const h = trackHeight('mutation')
  if (!mutation || !mutation.mut_aa) {
    if (mutation) {
      // ожидаемая мутация из пикера: только контур
      // 来自选择器的待定突变：仅描边
      ctx.strokeStyle = RED
      ctx.strokeRect(g.xFor(mutation.position) + 1, top + 3, Math.max(2, g.colW - 2), h - 6)
    }
    return
  }
  const m = mutation
  const x = g.xFor(m.position)
  const w = Math.max(2, g.colW)
  ctx.fillStyle = RED
  ctx.fillRect(x, top + 3, w, h - 6)
  // подпись справа от маркера (слева, если выйдет за график)
  // 标签在标记右侧（若超出图区则放左侧）
  ctx.fillStyle = RED
  ctx.font = '10px ui-monospace, monospace'
  const label = `${m.wt_aa}${m.position}${m.mut_aa}`
  const lx = x + w + 5
  ctx.fillText(label, lx <= g.width - 40 ? lx : x - 5 - label.length * 6, top + h / 2)
}

function drawScan(
  ctx: CanvasRenderingContext2D, g: Geometry, scan: ScanResult | null, t: TFn,
) {
  const top = g.trackTopOf('scan')
  const h = trackHeight('scan')
  if (!scan) {
    ctx.fillStyle = '#a3a3a3'
    ctx.fillText(t('pv.scanNoData'), g.plotX + 16, top + h / 2)
    return
  }
  const rows = scan.rows
  const cellH = h / rows.length
  const x = g.xFor(scan.position)
  const w = Math.max(2, g.colW - 1)
  rows.forEach((row, i) => {
    ctx.fillStyle = INTERP_FILL[row.interpretation]
    ctx.fillRect(x, top + i * cellH, w, Math.max(1, cellH - 0.5))
  })
  ctx.fillStyle = '#737373'
  ctx.font = '9px ui-monospace, monospace'
  ctx.fillText(`scan @ ${scan.position}`, x + w + 4, top + 6)
}

function drawTrackPlaceholders(
  ctx: CanvasRenderingContext2D, g: Geometry, t: TFn,
) {
  // трек доменов появится вместе с этапом UniProt (design doc §6, этап 1.3)
  // 域轨道随 UniProt 阶段出现（设计文档 §6，阶段 1.3）
  const top = g.trackTopOf('domains')
  const h = trackHeight('domains')
  ctx.fillStyle = '#a3a3a3'
  ctx.font = '9px ui-sans-serif, system-ui, sans-serif'
  ctx.fillText(t('pv.uniprotPlaceholder'), g.plotX + 16, top + h / 2)
}

// трек вариантов: средний |ΔpLDDT| по остаткам по всему ансамблю (dum.md §6 —
// честная картина чувствительности), тепловая полоса светло-серый → строгий
// красный, нормированная на максимум ВНУТРИ ЭТОГО ансамбля.
// 变体轨道：整个 ensemble 的逐残基平均 |ΔpLDDT|（dum.md §6——
// 诚实的敏感性图），热度条从浅灰到严格红，按本 ensemble 内的最大值归一化。
const HEAT_LO = [0xf5, 0xf5, 0xf5]
const HEAT_HI = [0xb9, 0x1c, 0x1c]

function heatColor(frac: number): string {
  const c = HEAT_LO.map((lo, i) => Math.round(lo + (HEAT_HI[i] - lo) * frac))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

function drawVariants(
  ctx: CanvasRenderingContext2D, g: Geometry, ens: EnsembleResult | null, t: TFn,
) {
  const top = g.trackTopOf('variants')
  const h = trackHeight('variants')
  const list = ens?.dplddt_abs_mean_list
  if (!list || list.length !== g.length) {
    ctx.fillStyle = '#a3a3a3'
    ctx.font = '9px ui-sans-serif, system-ui, sans-serif'
    ctx.fillText(t('pv.variantsNoData'), g.plotX + 16, top + h / 2)
    return
  }
  const pad = 3
  const stripH = Math.max(4, h - 2 * pad)
  const max = Math.max(...list)
  for (let p = g.win.start; p <= g.win.end; p++) {
    // guard ≈0 → всё белое (плоский профиль не несёт информации)
    // 防护 ≈0 → 全白（平坦剖面不含信息）
    const frac = max > 1e-9 ? Math.min(1, Math.max(0, list[p - 1] / max)) : 0
    ctx.fillStyle = heatColor(frac)
    ctx.fillRect(g.xFor(p), top + pad, Math.max(1, g.colW - 0.5), stripH)
  }
  // якорь: с контуром, как у всех прочих маркеров сайта
  // 锚点：与其他位点标记一样描边
  const x = g.xFor(ens!.position)
  const w = Math.max(2, g.colW - 0.5)
  ctx.strokeStyle = '#111111'
  ctx.strokeRect(x + 0.5, top + pad + 0.5, w - 1, stripH - 1)
  ctx.fillStyle = '#737373'
  ctx.font = '9px ui-monospace, monospace'
  ctx.fillText(`ens @ ${ens!.position}`, x + w + 4, top + 6)
}

// --- панель деталей / текст тултипа ---
// --- 详情面板 / 提示框文本 ---

function describePosition(
  pos: number,
  seq: string,
  plddt: number[] | null | undefined,
  mutation: { position: number; wt_aa: string; mut_aa: string } | null,
  scan: ScanResult | null,
  result: MutationResult | null | undefined,
  ens: EnsembleResult | null,
  t: TFn,
): string {
  const aa = seq[pos - 1] ?? '?'
  const parts: string[] = []
  parts.push(t('pv.pos', { pos, aa }))

  const p = plddt?.[pos - 1]
  if (p != null) parts.push(`pLDDT ${p.toFixed(1)}`)

  if (mutation && mutation.position === pos && mutation.mut_aa) {
    parts.push(t('pv.mutation', { m: `${mutation.wt_aa}${pos}${mutation.mut_aa}` }))
  }

  if (result?.rmsd) {
    const [a, b] = result.rmsd.local_window
    if (pos >= a && pos <= b) parts.push(t('pv.inLocalWindow', { a, b }))
  }

  if (ens?.dplddt_abs_mean_list && ens.dplddt_abs_mean_list.length === seq.length) {
    const v = ens.dplddt_abs_mean_list[pos - 1]
    if (v != null) {
      parts.push(t('pv.variantsHeat', { v: v.toFixed(2) }))
      if (ens.position === pos) parts.push(t('pv.ensAnchor'))
    }
  }

  if (scan && scan.position === pos) {
    const worst = [...scan.rows].sort((r1, r2) => r2.dplddt - r1.dplddt).slice(0, 3)
    parts.push(
      t('pv.scanWorst', {
        list: worst.map((r) => `${r.mut_aa} (${r.dplddt >= 0 ? '+' : ''}${r.dplddt.toFixed(2)})`).join(', '),
      }),
    )
  }
  return parts.join(' · ')
}