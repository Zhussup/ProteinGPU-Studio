// ProteinViewer: protein-sequence browser (docs/viewer_design.md).
// Canvas draws the data tracks; a transparent SVG overlay on top carries the
// interaction (click zones per residue, crosshair, tooltip). Both read pixel
// coordinates from lib/viewerGeometry — the single geometry source.
// Click anywhere = current position: the detail panel, the crosshair and
// MoleculeViewer's red sticks all follow it (cross-highlight, §4).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { MutationResult, ScanResult } from '../lib/types'
import { useI18n, type Key, type TFn } from '../i18n'
import {
  AXIS_HEIGHT, PAD_X, TRACKS, buildGeometry, computeWindow, tickStep, trackHeight,
  type Geometry, type TrackId,
} from '../lib/viewerGeometry'

const RED = '#b91c1c' // same strict red as MoleculeViewer
const INTERP_FILL: Record<'stable' | 'moderate' | 'critical', string> = {
  stable: '#d4d4d4',
  moderate: '#6b7280',
  critical: '#b91c1c',
}

// Track labels are drawn on the canvas — translated via the dictionary.
const TRACK_LABEL_KEYS: Record<TrackId, Key> = {
  sequence: 'track.sequence',
  plddt: 'track.plddt',
  mutation: 'track.mutation',
  scan: 'track.scan',
  domains: 'track.domains',
  variants: 'track.variants',
}

export interface ProteinViewerProps {
  sequence: string // protein letters, no FASTA header
  position: number // current position, 1-based (shared with MutationPicker → 3D)
  onPositionChange: (p: number) => void
  plddtWt?: number[] | null // index i = position i+1
  result?: MutationResult | null
  scan?: ScanResult | null
}

type ViewMode = 'whole' | 'window'

export default function ProteinViewer({
  sequence, position, onPositionChange, plddtWt, result, scan,
}: ProteinViewerProps) {
  const { t } = useI18n()
  const [mode, setMode] = useState<ViewMode>('whole')
  const [width, setWidth] = useState(0)
  const [hover, setHover] = useState<number | null>(null)
  // callback ref (not a mount-time effect): the host div mounts only once a
  // sequence exists — the empty-state branch returns early — so the
  // ResizeObserver must attach when the host appears, not on component mount.
  const [hostEl, setHostEl] = useState<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mapRef = useRef<HTMLCanvasElement>(null)

  const length = sequence.length
  const sc = scan ?? null
  // clamp defensively: the parent clamps too, but the sequence can change first
  const cur = Math.min(Math.max(1, position), Math.max(1, length))

  // ResizeObserver → width → geometry
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
  // left gutter: wide enough for the longest translated track name
  // (canvas-measured; CJK/Russian labels are wider than the default 28px)
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

  // --- canvas data layer ---
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

    // local RMSD window (±10 from the mutation site) — light band under data
    const lw = result?.rmsd?.local_window
    if (lw) drawBand(ctx, geom, lw[0], lw[1], '#f0f0f0')

    drawSequence(ctx, geom, sequence, cur)
    drawPlddt(ctx, geom, sequence, plddtWt, t)
    drawMutation(ctx, geom, mutation)
    drawScan(ctx, geom, sc, t)
    drawTrackPlaceholders(ctx, geom, t)

    if (hover) drawVLine(ctx, geom, hover, '#a3a3a3', true)
    drawVLine(ctx, geom, cur, '#111111', false)
  }, [geom, sequence, plddtWt, mutation, sc, result, hover, cur, t])

  // --- mini-map: orientation strip with the current window ---
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

  // --- SVG interaction layer: hit zones per visible residue ---
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
    ? describePosition(hover, sequence, plddtWt, mutation, sc, result, t)
    : null
  const curInfo = describePosition(cur, sequence, plddtWt, mutation, sc, result, t)

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

// --- draw helpers (all coordinates from Geometry) ---

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
  // track name on the left margin + hairline under each track
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
  if (g.colW < 8) return // letters unreadable — the axis + tooltip carry the info
  ctx.font = '11px ui-monospace, monospace'
  ctx.textAlign = 'center'
  for (let p = g.win.start; p <= g.win.end; p++) {
    if (p === cur) continue // drawn highlighted below
    ctx.fillStyle = '#404040'
    ctx.fillText(seq[p - 1], g.centerFor(p), mid)
  }
  // current position: black cell, white letter
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
  // gridlines at 50 / 90
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
      // pending mutation from the picker: outline only
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
  // label to the right of the marker (left if it would run off the plot)
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
  // domains/variants arrive with the UniProt stage (design doc §6, этап 1.3–1.4)
  for (const id of ['domains', 'variants'] as TrackId[]) {
    const top = g.trackTopOf(id)
    const h = trackHeight(id)
    ctx.fillStyle = '#a3a3a3'
    ctx.font = '9px ui-sans-serif, system-ui, sans-serif'
    ctx.fillText(t('pv.uniprotPlaceholder'), g.plotX + 16, top + h / 2)
  }
}

// --- detail panel / tooltip text ---

function describePosition(
  pos: number,
  seq: string,
  plddt: number[] | null | undefined,
  mutation: { position: number; wt_aa: string; mut_aa: string } | null,
  scan: ScanResult | null,
  result: MutationResult | null | undefined,
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