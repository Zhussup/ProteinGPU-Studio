// ProteinViewer geometry: the single source of pixel coordinates.
// The canvas layer draws data FROM these numbers, the SVG overlay places
// its hit zones BY them (docs/viewer_design.md §7) — the two coordinate
// systems physically cannot drift apart on resize or window change.

export type TrackId =
  | 'sequence'
  | 'plddt'
  | 'mutation'
  | 'scan'
  | 'domains'
  | 'variants'

export interface TrackDef {
  id: TrackId
  height: number
}

// Track registry, top to bottom. Adding a track = adding a row here plus a
// draw case; geometry needs no changes. (Labels live in the i18n dictionary
// under 'track.*' — ProteinViewer translates them.)
export const TRACKS: TrackDef[] = [
  { id: 'sequence', height: 30 },
  { id: 'plddt', height: 54 },
  { id: 'mutation', height: 24 },
  { id: 'scan', height: 54 },
  { id: 'domains', height: 26 },
  { id: 'variants', height: 26 },
]

export const AXIS_HEIGHT = 24
// side padding: room for tick/gridline labels (also used by the mini-map)
export const PAD_X = 28
const TRACK_GAP = 3
export const HALF_WINDOW = 50 // window mode: center ± HALF_WINDOW

// 1-based inclusive, per the project convention (same as rmsd.local_window)
export interface ViewerWindow {
  start: number
  end: number
}

export function computeWindow(
  mode: 'whole' | 'window',
  length: number,
  center: number,
): ViewerWindow {
  const len = Math.max(1, length)
  if (mode === 'whole' || len <= 2 * HALF_WINDOW + 1) return { start: 1, end: len }
  return {
    start: Math.max(1, center - HALF_WINDOW),
    end: Math.min(len, center + HALF_WINDOW),
  }
}

export interface Geometry {
  length: number
  win: ViewerWindow
  colW: number // px per residue in the current window
  plotX: number
  plotW: number
  width: number
  height: number
  xFor(pos: number): number // left edge of a residue's column
  centerFor(pos: number): number
  posAt(x: number): number | null // inverse, clamped to the window; null outside the plot
  trackTopOf(id: TrackId): number
}

export function buildGeometry(
  width: number,
  length: number,
  win: ViewerWindow,
  // left/right gutter; callers may widen it to fit translated track labels
  padX: number = PAD_X,
): Geometry {
  const plotX = padX
  const plotW = Math.max(1, width - 2 * padX)
  const span = win.end - win.start + 1
  const colW = plotW / span

  const trackTop = {} as Record<TrackId, number>
  let y = AXIS_HEIGHT + TRACK_GAP
  for (const t of TRACKS) {
    trackTop[t.id] = y
    y += t.height + TRACK_GAP
  }
  const height = y

  const xFor = (pos: number) => plotX + (pos - win.start) * colW
  const centerFor = (pos: number) => xFor(pos) + colW / 2
  const posAt = (x: number) => {
    if (x < plotX || x > plotX + plotW) return null
    const p = win.start + Math.floor((x - plotX) / colW)
    return Math.min(win.end, Math.max(win.start, p))
  }

  return {
    length,
    win,
    colW,
    plotX,
    plotW,
    width,
    height,
    xFor,
    centerFor,
    posAt,
    trackTopOf: (id) => trackTop[id],
  }
}

export function trackHeight(id: TrackId): number {
  return TRACKS.find((t) => t.id === id)!.height
}

// smallest tick step (in residues) whose labels are ≥ minPx apart
export function tickStep(span: number, plotW: number, minPx = 48): number {
  for (const step of [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000]) {
    if ((span / step) * minPx <= plotW) return step
  }
  return 1000
}

export function trackRect(
  g: Geometry,
  id: TrackId,
  pos: number,
): { x: number; y: number; w: number; h: number } {
  return { x: g.xFor(pos), y: g.trackTopOf(id), w: g.colW, h: trackHeight(id) }
}