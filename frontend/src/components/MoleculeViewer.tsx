// MoleculeViewer: 3Dmol.js wrapper on a white canvas.
// WT — translucent grey cartoon; mutant — dark grey/blue spectrum; mutated
// residue — red sticks. The backend serves an already-aligned mutant PDB
// (alignment is done by the C++/CUDA core) — no client-side math.
import { useEffect, useRef } from 'react'
// UMD bundle: importing defines window.$3Dmol
import '3dmol'
import { useI18n } from '../i18n'
import { bucketColor, bucketOf, HEAT_BUCKETS } from './RoseGlyph'

// 3dmol ships a UMD bundle; declare the minimal surface we use.
declare global {
  interface Window {
    $3Dmol?: {
      createViewer: (
        el: HTMLElement,
        cfg: Record<string, unknown>,
      ) => $3DmolViewer
      syncSurface: () => void
    }
  }
  interface $3DmolViewer {
    addModel(data: string, format: string): void
    addStyle(sel: Record<string, unknown>, style: Record<string, unknown>): void
    addSurface(
      type: number,
      style: Record<string, unknown>,
      sel?: Record<string, unknown>,
    ): void
    removeAllSurfaces(): void
    removeAllModels(): void
    zoomTo(): void
    zoom(factor?: number): void
    render(): void
    setBackgroundColor(color: string): void
    clear(): void
  }
}

const WT_COLOR = '#9ca3af' // light grey, translucent
const MUT_COLOR = '#1f2937' // near-black
const MUT_COLOR_ALT = '#374151' // fallback when not aligned
const MUTATION_COLOR = '#b91c1c' // strict red

export interface ViewerProps {
  wtPdb: string | null
  mutPdb: string | null
  aligned: boolean // true → mutPdb is the aligned variant
  mutationPosition?: number // 1-based
  height?: number
  // sensitivity paint (scan map): per-residue scalar 0..1 (null = unmeasured),
  // index 0 = residue 1; colors the WT cartoon by quantized heat buckets
  residueScores?: (number | null)[] | null
  scoreLabel?: string
}

// group measured residues into contiguous same-bucket runs → resi ranges
export function scoreRuns(scores: (number | null)[]): { start: number; end: number; bucket: number }[] {
  const runs: { start: number; end: number; bucket: number }[] = []
  let cur: { start: number; end: number; bucket: number } | null = null
  scores.forEach((v, i) => {
    if (v === null || v === undefined) { cur = null; return }
    const bucket = bucketOf(v)
    if (cur && cur.bucket === bucket) {
      cur.end = i + 1
    } else {
      cur = { start: i + 1, end: i + 1, bucket }
      runs.push(cur)
    }
  })
  return runs
}

export default function MoleculeViewer({
  wtPdb, mutPdb, aligned, mutationPosition, height = 420, residueScores, scoreLabel,
}: ViewerProps) {
  const { t } = useI18n()
  const hostRef = useRef<HTMLDivElement>(null)
  const glRef = useRef<$3DmolViewer | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host || !window.$3Dmol) return
    const gl = window.$3Dmol.createViewer(host, { backgroundColor: '#ffffff' })
    glRef.current = gl
    // e2e hook (?e2e in the URL): demo recordings drive rotate/zoom through
    // the viewer API — synthetic wheel events don't zoom in headless capture
    if (new URLSearchParams(window.location.search).has('e2e')) {
      ;(window as unknown as { __mol?: $3DmolViewer }).__mol = gl
    }
    return () => {
      gl.clear()
      glRef.current = null
    }
  }, [])

  useEffect(() => {
    const gl = glRef.current
    if (!gl || !wtPdb) return
    gl.clear()

    // WT: translucent grey cartoon backbone — or the sensitivity paint when
    // the scan map pushed per-residue scores (model: 0 keeps the mutant model
    // untouched; nulls stay on the base grey)
    gl.addModel(wtPdb, 'pdb')
    gl.addStyle({}, { cartoon: { color: WT_COLOR, opacity: 0.55 } })
    if (residueScores) {
      for (const run of scoreRuns(residueScores)) {
        gl.addStyle(
          { model: 0, resi: [`${run.start}-${run.end}`] },
          { cartoon: { color: bucketColor(run.bucket), opacity: 0.9 } },
        )
      }
    }

    // Mutant: aligned (or raw) model, dark cartoon — contrast on white
    const mut = mutPdb
    if (mut) {
      gl.addModel(mut, 'pdb')
      const sel: Record<string, unknown> = {}
      if (aligned) {
        gl.addStyle(sel, { cartoon: { colorscheme: 'spectrum', opacity: 0.95 } })
      } else {
        gl.addStyle(sel, { cartoon: { color: MUT_COLOR_ALT, opacity: 0.95 } })
      }
      // mutated residue as red sticks
      if (mutationPosition && mutationPosition >= 1) {
        gl.addStyle({ resi: mutationPosition }, {
          stick: { color: MUTATION_COLOR, radius: 0.25 },
          sphere: { color: MUTATION_COLOR, radius: 0.45 },
        })
      }
    }

    gl.zoomTo()
    gl.render()
  }, [wtPdb, mutPdb, aligned, mutationPosition, residueScores])

  const painted = !!residueScores && residueScores.some((v) => v !== null && v !== undefined)

  return (
    <div className="relative overflow-hidden border border-neutral-300 bg-white" data-demo="viewer">
      <div ref={hostRef} style={{ width: '100%', height }} className="cursor-grab" />
      <div className="pointer-events-none absolute right-2 bottom-2 border border-neutral-200 bg-white/85 px-2 py-1 text-[11px] text-neutral-500">
        {t('viewer.hint')}
      </div>
      {!wtPdb && (
        <div className="absolute inset-0 flex items-center justify-center text-neutral-400">
          {t('viewer.empty')}
        </div>
      )}
      {wtPdb && (mutPdb || painted) && (
        <div className="pointer-events-none absolute top-2 left-2 flex flex-col gap-1 text-[11px]">
          {painted ? (
            <LegendRamp label={scoreLabel ?? t('viewer.legendSensitivity')} />
          ) : (
            <Legend color={WT_COLOR} label={t('viewer.legendWt')} />
          )}
          {mutPdb && <Legend color={MUT_COLOR} label={t('viewer.legendMut')} />}
          {mutationPosition && mutPdb && <Legend color={MUTATION_COLOR} label={t('viewer.legendMutation', { pos: mutationPosition })} />}
        </div>
      )}
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5 border border-neutral-200 bg-white/85 px-2 py-0.5 text-neutral-700">
      <span className="inline-block h-2.5 w-2.5" style={{ background: color }} />
      {label}
    </div>
  )
}

// ramp legend for the sensitivity paint: the quantized heat buckets
function LegendRamp({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1.5 border border-neutral-200 bg-white/85 px-2 py-0.5 text-neutral-700">
      <span className="flex">
        {Array.from({ length: HEAT_BUCKETS }, (_, i) => (
          <span key={i} className="inline-block h-2.5 w-2" style={{ background: bucketColor(i) }} />
        ))}
      </span>
      {label}
    </div>
  )
}