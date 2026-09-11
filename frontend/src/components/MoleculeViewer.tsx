// MoleculeViewer: 3Dmol.js wrapper.
// WT — translucent grey cartoon; mutant — color spectrum; mutated residue —
// red sticks. The backend serves an already-aligned mutant PDB (alignment is
// done by the C++/CUDA core) — no client-side math.
import { useEffect, useRef } from 'react'
// UMD bundle: importing defines window.$3Dmol
import '3dmol'

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

export interface ViewerProps {
  wtPdb: string | null
  mutPdb: string | null
  aligned: boolean // true → mutPdb is the aligned variant
  mutationPosition?: number // 1-based
  height?: number
}

export default function MoleculeViewer({
  wtPdb, mutPdb, aligned, mutationPosition, height = 420,
}: ViewerProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const glRef = useRef<$3DmolViewer | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host || !window.$3Dmol) return
    const gl = window.$3Dmol.createViewer(host, { backgroundColor: '#0b0f14' })
    glRef.current = gl
    return () => {
      gl.clear()
      glRef.current = null
    }
  }, [])

  useEffect(() => {
    const gl = glRef.current
    if (!gl || !wtPdb) return
    gl.clear()

    // WT: translucent grey cartoon backbone
    gl.addModel(wtPdb, 'pdb')
    gl.addStyle({}, { cartoon: { color: '#8b98a5', opacity: 0.55 } })

    // Mutant: aligned (or raw) model, spectrum cartoon
    const mut = mutPdb
    if (mut) {
      gl.addModel(mut, 'pdb')
      const sel: Record<string, unknown> = {}
      if (aligned) {
        gl.addStyle(sel, { cartoon: { colorscheme: 'spectrum', opacity: 0.95 } })
      } else {
        gl.addStyle(sel, { cartoon: { color: '#3ddbd9', opacity: 0.95 } })
      }
      // mutated residue as red sticks
      if (mutationPosition && mutationPosition >= 1) {
        gl.addStyle({ resi: mutationPosition }, {
          stick: { color: '#ff5257', radius: 0.25 },
          sphere: { color: '#ff5257', radius: 0.45 },
        })
      }
    }

    gl.zoomTo()
    gl.render()
  }, [wtPdb, mutPdb, aligned, mutationPosition])

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-[#0b0f14]">
      <div ref={hostRef} style={{ width: '100%', height }} className="cursor-grab" />
      <div className="pointer-events-none absolute right-2 bottom-2 rounded bg-black/50 px-2 py-1 text-[11px] text-slate-400">
        ЛКМ — поворот · колесо — зум · ПКМ — сдвиг
      </div>
      {!wtPdb && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-600">
          Запустите предсказание, чтобы увидеть структуру
        </div>
      )}
      {wtPdb && mutPdb && (
        <div className="pointer-events-none absolute top-2 left-2 flex flex-col gap-1 text-[11px]">
          <Legend color="#8b98a5" label="WT (полупрозрачный)" />
          <Legend color="#3ddbd9" label="Мутант" />
          {mutationPosition && <Legend color="#ff5257" label={`Мутация ${mutationPosition}`} />}
        </div>
      )}
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded bg-black/50 px-2 py-0.5 text-slate-300">
      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </div>
  )
}