// RoseGlyph: «роза ветров» позиции белка (dum.md §5).
// 19 лепестков в ФИКСИРОВАННОМ физхим-компасе (порядок не зависит от позиции)
// плюс выемка для слота WT. Длина лепестка = перцентильный ранг отклика,
// цвет = интенсивность отклика локального RMSD. Форма розы читается как
// сигнатура: «морской ёж» (болит каждая замена), «одна игла» (ломается одно
// химическое направление), «диск» (толерантно), «клевер» (сильно, но рвано).
// RoseGlyph：蛋白质位点的“风玫瑰”（dum.md §5）。
// 19 个花瓣位于固定的物理化学罗盘中（顺序与位置无关），外加 WT 槽位的缺口。
// 花瓣长度 = 响应的百分位排名，颜色 = 局部 RMSD 响应的强度。
// 玫瑰的形状即签名：“海胆”（每种替换都有响应）、“独针”（仅一个化学
// 方向断裂）、“圆盘”（耐受）、“三叶草”（强但参差）。
import { memo } from 'react'

// Фиксированный 20-направленный компас, общий с бэкендом
// (backend/app/services/sensitivity.py PETAL_DIRS) — держим синхронно.
// 固定的 20 方向罗盘，与后端共用
//（backend/app/services/sensitivity.py 的 PETAL_DIRS）——保持同步。
export const PETAL_DIRS = 'AVILMFWYSTNQDEKRHGCP'

// rank(x, arr): доля строго меньших по (n - 1) — побайтовый паритет с
// percentile_rank бэкенда и SensitivityCompare.rank(): ничьи оседают вниз,
// одиночный элемент отображается в 0.5.
// rank(x, arr)：严格小于的比例除以 (n - 1)——与后端 percentile_rank 和
// SensitivityCompare.rank() 逐字节一致：平局落在底部，单元素映射为 0.5。
export function rank(x: number, arr: number[]): number {
  const below = arr.reduce((n, v) => (v < x ? n + 1 : n), 0)
  return arr.length > 1 ? below / (arr.length - 1) : 0.5
}

// тепловая шкала: нейтральный серый → фирменный красный, по интенсивности 0..1
// 热度色带：中性灰 → 应用主色红，按强度 0..1
export function heatColor(intensity: number): string {
  const t = Math.max(0, Math.min(1, intensity))
  const from = [0xe5, 0xe5, 0xe5]
  const to = [0xb9, 0x1c, 0x1c]
  const c = from.map((f, i) => Math.round(f + (to[i] - f) * t))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

// квантованные корзины для 3D-раскраски (непрерывные диапазоны resi, ≤8 цветов)
// 3D 着色用的分档（连续 resi 区间，≤8 色）
export const HEAT_BUCKETS = 8
export function bucketColor(i: number): string {
  return heatColor((i + 0.5) / HEAT_BUCKETS)
}
export function bucketOf(intensity: number): number {
  return Math.min(HEAT_BUCKETS - 1, Math.max(0, Math.floor(intensity * HEAT_BUCKETS)))
}

export interface Petal {
  aa: string
  len: number // 0..1 — канал длины (перцентиль |ΔpLDDT_local|) | 0..1——长度通道（|ΔpLDDT_local| 百分位）
  intensity: number // 0..1 — канал цвета (перцентиль local RMSD) | 0..1——颜色通道（local RMSD 百分位）
  tip?: string // текст наведения | 悬停文本
}

export interface RoseGlyphProps {
  petals: Petal[] // 19 лепестков, порядок компаса без буквы WT | 19 个花瓣，罗盘顺序去掉 WT 字母
  wtSlot: number // индекс буквы WT в 20-слотовом компасе | WT 字母在 20 槽罗盘中的索引
  size?: number // px (по умолчанию 72) | 像素（默认 72）
  title?: string
}

function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const a = ((deg - 90) * Math.PI) / 180 // 0° = 12 часов, по часовой | 0° = 12 点方向，顺时针
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
}

// кольцевой клин от радиуса r0 до r1 между углами a0..a1 (в градусах)
// 角度 a0..a1（度）之间、半径 r0 到 r1 的环形扇形
function wedgePath(cx: number, cy: number, r0: number, r1: number, a0: number, a1: number): string {
  const [x0, y0] = polar(cx, cy, r1, a0)
  const [x1, y1] = polar(cx, cy, r1, a1)
  const [x2, y2] = polar(cx, cy, r0, a1)
  const [x3, y3] = polar(cx, cy, r0, a0)
  return [
    `M ${x0.toFixed(2)} ${y0.toFixed(2)}`,
    `A ${r1.toFixed(2)} ${r1.toFixed(2)} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`,
    `L ${x2.toFixed(2)} ${y2.toFixed(2)}`,
    `A ${r0.toFixed(2)} ${r0.toFixed(2)} 0 0 0 ${x3.toFixed(2)} ${y3.toFixed(2)}`,
    'Z',
  ].join(' ')
}

const STEP = 360 / 20

function RoseGlyph({ petals, wtSlot, size = 72, title }: RoseGlyphProps) {
  const s = size
  const c = s / 2
  const rMax = c - 3
  const r0 = rMax * 0.22
  const byAA = new Map(petals.map((p) => [p.aa, p]))

  return (
    <svg
      width={s}
      height={s}
      viewBox={`0 0 ${s} ${s}`}
      role="img"
      aria-label={title}
      className="shrink-0"
    >
      {title && <title>{title}</title>}
      {/* базовая окружность + внешние опорные кольца */}
      {/* 基准圆 + 外部参考环 */}
      <circle cx={c} cy={c} r={r0} fill="none" stroke="#e5e5e5" strokeWidth={0.8} />
      <circle cx={c} cy={c} r={rMax} fill="none" stroke="#f5f5f5" strokeWidth={0.8} />
      {PETAL_DIRS.split('').map((aa, slot) => {
        const a0 = slot * STEP
        if (slot === wtSlot) {
          // выемка WT: короткий фиксированный пенёк — собственный остаток позиции
          // WT 缺口：短的固定残段——位点自身的残基
          return (
            <path
              key={`wt-${slot}`}
              d={wedgePath(c, c, r0, r0 + (rMax - r0) * 0.12, a0 + 1.5, a0 + STEP - 1.5)}
              fill="#9ca3af"
              stroke="none"
            />
          )
        }
        const p = byAA.get(aa)
        if (!p || p.len <= 0) return null
        const r1 = r0 + (rMax - r0) * Math.min(1, Math.max(0.04, p.len))
        return (
          <path
            key={aa}
            d={wedgePath(c, c, r0, r1, a0 + 1.5, a0 + STEP - 1.5)}
            fill={heatColor(p.intensity)}
            stroke="none"
          >
            {p.tip && <title>{p.tip}</title>}
          </path>
        )
      })}
    </svg>
  )
}

export default memo(RoseGlyph)