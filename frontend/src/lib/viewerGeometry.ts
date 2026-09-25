// Геометрия ProteinViewer: единственный источник пиксельных координат.
// Слой canvas рисует данные ПО этим числам, SVG-оверлей расставляет свои
// зоны клика ПО ним (docs/viewer_design.md §7) — две системы координат
// физически не могут разъехаться при ресайзе или смене окна.
// ProteinViewer 几何：像素坐标的唯一来源。
// canvas 层依据这些数字绘制数据，SVG 覆盖层据此放置点击区域
//（docs/viewer_design.md §7）——两套坐标系在缩放或窗口变化时物理上不可能错位。

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

// Реестр треков, сверху вниз. Добавить трек = добавить строку здесь и кейс
// отрисовки; геометрия правок не требует. (Подписи живут в i18n-словаре
// под ключами 'track.*' — ProteinViewer их переводит.)
// 轨道注册表，自上而下。新增轨道 = 在此加一行并加一个绘制分支；
// 几何无需改动。（标签存于 i18n 字典的 'track.*' 键下——由 ProteinViewer 翻译。）
export const TRACKS: TrackDef[] = [
  { id: 'sequence', height: 30 },
  { id: 'plddt', height: 54 },
  { id: 'mutation', height: 24 },
  { id: 'scan', height: 54 },
  { id: 'domains', height: 26 },
  { id: 'variants', height: 26 },
]

export const AXIS_HEIGHT = 24
// боковой отступ: место для подписей тиков/сетку (используется и мини-картой)
// 侧边留白：容纳刻度/网格线标签（小地图同样使用）
export const PAD_X = 28
const TRACK_GAP = 3
export const HALF_WINDOW = 50 // режим окна: центр ± HALF_WINDOW | 窗口模式：中心 ± HALF_WINDOW

// с 1, включительно — по конвенции проекта (как rmsd.local_window)
// 从 1 开始、含端点——项目约定（同 rmsd.local_window）
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
  colW: number // px на остаток в текущем окне | 当前窗口内每个残基的像素宽
  plotX: number
  plotW: number
  width: number
  height: number
  xFor(pos: number): number // левый край колонки остатка | 残基列的左边缘
  centerFor(pos: number): number
  posAt(x: number): number | null // обратная функция, зажата в окно; null вне графика | 逆映射，钳制在窗口内；图外为 null
  trackTopOf(id: TrackId): number
}

export function buildGeometry(
  width: number,
  length: number,
  win: ViewerWindow,
  // левый/правый отступ; вызывающий может расширить под переведённые подписи треков
  // 左右留白；调用方可加宽以容纳翻译后的轨道标签
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

// наименьший шаг тика (в остатках), при котором подписи ≥ minPx друг от друга
// 最小刻度步长（以残基计），使标签间距 ≥ minPx
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