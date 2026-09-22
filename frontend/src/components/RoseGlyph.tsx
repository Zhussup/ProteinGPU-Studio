// RoseGlyph: the "wind rose" of a protein position (dum.md §5).
// 19 petals in the FIXED physchem compass (position-independent order) plus a
// notch for the WT slot. Petal length = the response's percentile rank, petal
// color = intensity of the local RMSD response. The glyph's shape reads as a
// signature: "sea hedgehog" (every substitution hurts), "one needle" (a single
// chemical direction breaks), "disk" (tolerant), "clover" (strong but ragged).
import { memo } from 'react'

// Fixed 20-direction compass, shared with the backend
// (backend/app/services/sensitivity.py PETAL_DIRS) — keep in sync.
export const PETAL_DIRS = 'AVILMFWYSTNQDEKRHGCP'

// rank(x, arr): fraction strictly below over (n - 1) — byte-parity with the
// backend's percentile_rank and SensitivityCompare.rank(): ties sit at the
// bottom, a single element maps to 0.5.
export function rank(x: number, arr: number[]): number {
  const below = arr.reduce((n, v) => (v < x ? n + 1 : n), 0)
  return arr.length > 1 ? below / (arr.length - 1) : 0.5
}

// heat ramp: neutral grey → the app's red, by intensity 0..1
export function heatColor(intensity: number): string {
  const t = Math.max(0, Math.min(1, intensity))
  const from = [0xe5, 0xe5, 0xe5]
  const to = [0xb9, 0x1c, 0x1c]
  const c = from.map((f, i) => Math.round(f + (to[i] - f) * t))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

// quantized buckets for the 3D paint (contiguous resi ranges, ≤8 colors)
export const HEAT_BUCKETS = 8
export function bucketColor(i: number): string {
  return heatColor((i + 0.5) / HEAT_BUCKETS)
}
export function bucketOf(intensity: number): number {
  return Math.min(HEAT_BUCKETS - 1, Math.max(0, Math.floor(intensity * HEAT_BUCKETS)))
}

export interface Petal {
  aa: string
  len: number // 0..1 — length channel (|ΔpLDDT_local| percentile)
  intensity: number // 0..1 — color channel (local RMSD percentile)
  tip?: string // hover text
}

export interface RoseGlyphProps {
  petals: Petal[] // 19 petals, compass order minus the WT letter
  wtSlot: number // index of the WT letter in the 20-slot compass
  size?: number // px (default 72)
  title?: string
}

function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const a = ((deg - 90) * Math.PI) / 180 // 0° = 12 o'clock, clockwise
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
}

// annular wedge from radius r0 to r1 between angles a0..a1 (degrees)
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
      {/* baseline + outer reference rings */}
      <circle cx={c} cy={c} r={r0} fill="none" stroke="#e5e5e5" strokeWidth={0.8} />
      <circle cx={c} cy={c} r={rMax} fill="none" stroke="#f5f5f5" strokeWidth={0.8} />
      {PETAL_DIRS.split('').map((aa, slot) => {
        const a0 = slot * STEP
        if (slot === wtSlot) {
          // WT notch: a short fixed stub — the position's own residue
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