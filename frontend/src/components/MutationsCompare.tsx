// MutationsCompare: cross-mutation table built from completed mutate jobs on
// the same WT sequence. The point: absolute RMSD thresholds don't hold for a
// near-deterministic model — relative ordering between mutations does.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { JobSummary, MutationResult } from '../lib/types'

interface Row {
  jobId: string
  label: string          // I44A etc.
  local: number
  global: number
  tm: number
  dplddt: number
  interpretation: string
}

const BADGE_CLS: Record<string, string> = {
  stable: 'border border-neutral-300 text-neutral-500',
  moderate: 'bg-neutral-600 text-white',
  critical: 'bg-red-700 text-white',
}

export default function MutationsCompare({ jobs, wtSequence }: {
  jobs: JobSummary[]
  wtSequence: string
}) {
  const [rows, setRows] = useState<Row[] | null>(null)

  useEffect(() => {
    if (!wtSequence) { setRows(null); return }
    let cancelled = false
    const done = jobs.filter(
      (j) => j.kind === 'mutate' && j.status === 'done' && j.sequence === wtSequence,
    )
    if (done.length < 2) { setRows(null); return }
    Promise.all(
      done.map(async (j): Promise<Row | null> => {
        try {
          const res = await api.result(j.job_id) as unknown as MutationResult
          if (!res.rmsd) return null
          return {
            jobId: j.job_id,
            label: `${res.wt_aa}${res.position}${res.mutant_aa}`,
            local: res.rmsd.local_rmsd,
            global: res.rmsd.global_rmsd,
            tm: res.rmsd.tm_score,
            dplddt: res.rmsd.plddt_mut - res.rmsd.plddt_wt,
            interpretation: res.rmsd.interpretation,
          }
        } catch { return null }
      }),
    ).then((rs) => {
      if (cancelled) return
      const good = rs.filter((r): r is Row => r !== null)
      setRows(good.length >= 2 ? good.sort((a, b) => b.local - a.local) : null)
    })
    return () => { cancelled = true }
  }, [jobs, wtSequence])

  if (!rows) return null

  return (
    <div className="panel p-4">
      <h3 className="mb-3 text-sm font-medium text-neutral-900">Сравнение мутаций одного белка</h3>
      <div className="border border-neutral-200">
        <table className="w-full text-xs">
          <thead className="bg-neutral-100 text-neutral-600">
            <tr>
              <th className="px-2 py-1.5 text-left">мутация</th>
              <th className="px-2 py-1.5 text-right">local RMSD, Å</th>
              <th className="px-2 py-1.5 text-right">global</th>
              <th className="px-2 py-1.5 text-right">TM</th>
              <th className="px-2 py-1.5 text-right">ΔpLDDT</th>
              <th className="px-2 py-1.5 text-center">вердикт</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.jobId} className="border-t border-neutral-100">
                <td className="mono px-2 py-1.5 font-medium text-neutral-900">{r.label}</td>
                <td className="mono px-2 py-1.5 text-right">{r.local.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.global.toFixed(2)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.tm.toFixed(3)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.dplddt >= 0 ? `+${r.dplddt.toFixed(1)}` : r.dplddt.toFixed(1)}</td>
                <td className="px-2 py-1.5 text-center">
                  <span className={`mono px-1.5 py-0.5 text-[10px] ${BADGE_CLS[r.interpretation] ?? ''}`}>
                    {r.interpretation === 'stable' ? 'стаб.' : r.interpretation === 'moderate' ? 'умерен.' : 'крит.'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-1 text-[10px] text-neutral-400">
        собрано из истории прогонов на той же WT-последовательности; сортировка по локальному
        RMSD — самый отзывчивый участок, наименее отзывчивый внизу
      </div>
    </div>
  )
}