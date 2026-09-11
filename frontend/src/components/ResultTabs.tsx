// ResultTabs: RMSD cards + sequences + pLDDT after a mutation job.
import type { MutationResult } from '../lib/types'

const BADGE: Record<string, { cls: string; label: string }> = {
  stable: { cls: 'border border-neutral-900 text-neutral-900', label: 'стабильна' },
  moderate: { cls: 'bg-neutral-600 text-white', label: 'умеренно' },
  critical: { cls: 'bg-red-700 text-white', label: 'критично' },
}

export default function ResultTabs({ result }: { result: MutationResult | null }) {
  if (!result?.rmsd) return null
  const r = result.rmsd
  const badge = BADGE[r.interpretation] ?? BADGE.moderate

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Global RMSD" value={`${r.global_rmsd.toFixed(2)} Å`} />
        <Metric
          label={`Local RMSD (${r.local_window[0]}–${r.local_window[1]})`}
          value={`${r.local_rmsd.toFixed(2)} Å`}
        />
        <Metric label="TM-score" value={r.tm_score.toFixed(3)} />
        <div className="border border-neutral-200 bg-white p-3">
          <div className="text-[11px] text-neutral-500">Вердикт</div>
          <span className={`mono mt-2 inline-block px-2 py-0.5 text-xs font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs text-neutral-600 lg:grid-cols-4">
        <MetricSmall label="pLDDT WT" value={r.plddt_wt.toFixed(1)} />
        <MetricSmall label="pLDDT mut" value={r.plddt_mut.toFixed(1)} />
        <MetricSmall label="ΔpLDDT" value={(r.plddt_mut - r.plddt_wt).toFixed(1)} />
        <MetricSmall label="Движок выравнивания" value={r.engine} />
      </div>

      <details className="border border-neutral-200 bg-neutral-50 p-3 text-xs">
        <summary className="cursor-pointer text-neutral-600">Последовательности</summary>
        <div className="mono mt-2 space-y-2 break-all">
          <div>
            <span className="text-neutral-500">WT </span>
            <span className="text-neutral-800">{result.wt_sequence}</span>
          </div>
          <div>
            <span className="text-neutral-500">MUT </span>
            <span className="text-neutral-800">
              {result.mutant_sequence.slice(0, result.position - 1)}
              <b className="bg-red-700 px-0.5 text-white">{result.mutant_sequence[result.position - 1]}</b>
              {result.mutant_sequence.slice(result.position)}
            </span>
          </div>
        </div>
      </details>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-neutral-200 bg-white p-3">
      <div className="text-[11px] text-neutral-500">{label}</div>
      <div className="mono mt-1 text-xl text-neutral-900">{value}</div>
    </div>
  )
}

function MetricSmall({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-neutral-200 bg-white px-3 py-2">
      <span className="text-neutral-500">{label}: </span>
      <span className="mono text-neutral-800">{value}</span>
    </div>
  )
}