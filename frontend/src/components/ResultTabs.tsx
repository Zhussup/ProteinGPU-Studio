// ResultTabs: RMSD cards + summary + sequences + pLDDT after a mutation job.
// Each metric carries a "?" button opening a plain-language explanation modal.
import { Suspense, lazy, useState } from 'react'
import type { MutationResult } from '../lib/types'
import { renderBold, useI18n, type Key } from '../i18n'
import Modal from './Modal'

const Plot = lazy(() => import('./PlotlyChart'))

// Badge styling stays in the component; labels come from the dictionary.
const BADGE_CLS: Record<string, string> = {
  stable: 'border border-neutral-900 text-neutral-900',
  moderate: 'bg-neutral-600 text-white',
  critical: 'bg-red-700 text-white',
}
const BADGE_KEYS: Record<string, Key> = {
  stable: 'res.badge.stable',
  moderate: 'res.badge.moderate',
  critical: 'res.badge.critical',
}

// Plain-language explanations; shown via the "?" button on each metric.
// Paragraphs come from the locale dictionaries (tl()), **bold** spans are
// rendered by renderBold. Wording mirrors docs/ml_model_decision.md.
type HelpTopic = 'global' | 'local' | 'tm' | 'plddt' | 'dplddt'

function HelpBody({ topic }: { topic: HelpTopic }) {
  const { tl } = useI18n()
  const paras = tl(`help.${topic}` as Key)
  return (
    <>
      {paras.map((p, i) => (
        <p key={i} className={i < paras.length - 1 ? 'mb-2' : ''}>{renderBold(p)}</p>
      ))}
    </>
  )
}

function QuestionMark({ topic, onOpen, title }: { topic: HelpTopic; onOpen: (t: HelpTopic) => void; title: string }) {
  return (
    <button
      onClick={() => onOpen(topic)}
      title={title}
      className="ml-1 inline-flex h-4 w-4 items-center justify-center border border-neutral-300 text-[10px] leading-none text-neutral-500 hover:border-neutral-900 hover:text-neutral-900"
    >
      ?
    </button>
  )
}

export default function ResultTabs({ result }: { result: MutationResult | null }) {
  const { t } = useI18n()
  const [help, setHelp] = useState<HelpTopic | null>(null)
  if (!result?.rmsd) return null
  const r = result.rmsd
  const badgeCls = BADGE_CLS[r.interpretation] ?? BADGE_CLS.moderate
  const badgeKey = BADGE_KEYS[r.interpretation] ?? BADGE_KEYS.moderate

  return (
    <div className="space-y-4">
      {result.summary && (
        <div className="border-l-2 border-neutral-900 bg-neutral-50 p-3 text-sm text-neutral-800">
          {result.summary}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Global RMSD" value={`${r.global_rmsd.toFixed(2)} Å`} help="global" onHelp={setHelp} helpTitle={t('res.help.q')} />
        <Metric
          label={t('res.localRmsd', { a: r.local_window[0], b: r.local_window[1] })}
          value={`${r.local_rmsd.toFixed(2)} Å`}
          help="local"
          onHelp={setHelp}
          helpTitle={t('res.help.q')}
        />
        <Metric label="TM-score" value={r.tm_score.toFixed(3)} help="tm" onHelp={setHelp} helpTitle={t('res.help.q')} />
        <div className="border border-neutral-200 bg-white p-3">
          <div className="text-[11px] text-neutral-500">
            {t('res.verdict')} <QuestionMark topic="local" onOpen={setHelp} title={t('res.help.q')} />
          </div>
          <span className={`mono mt-2 inline-block px-2 py-0.5 text-xs font-medium ${badgeCls}`}>
            {t(badgeKey)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs text-neutral-600 lg:grid-cols-4">
        <MetricSmall label="pLDDT WT" value={r.plddt_wt.toFixed(1)} help="plddt" onHelp={setHelp} helpTitle={t('res.help.q')} />
        <MetricSmall label="pLDDT mut" value={r.plddt_mut.toFixed(1)} help="plddt" onHelp={setHelp} helpTitle={t('res.help.q')} />
        <MetricSmall label="ΔpLDDT" value={(r.plddt_mut - r.plddt_wt).toFixed(1)} help="dplddt" onHelp={setHelp} helpTitle={t('res.help.q')} />
        <MetricSmall label={t('res.alignEngine')} value={r.engine} />
      </div>

      {(result.plddt_wt_list && result.plddt_mut_list) && (
        <details open className="border border-neutral-200 bg-neutral-50 p-3">
          <summary className="cursor-pointer text-xs text-neutral-600">
            {t('res.plddtProfile')}
            <QuestionMark topic="plddt" onOpen={setHelp} title={t('res.help.q')} />
          </summary>
          <div className="mt-2">
            <Suspense fallback={<div className="py-10 text-center text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
              <PlddtChart
                wt={result.plddt_wt_list}
                mut={result.plddt_mut_list}
                position={result.position}
                wtAA={result.wt_aa}
                mutAA={result.mutant_aa}
              />
            </Suspense>
            <div className="mt-1 text-[10px] text-neutral-400">
              {t('res.plddtNote')}
            </div>
          </div>
        </details>
      )}

      <details className="border border-neutral-200 bg-neutral-50 p-3 text-xs">
        <summary className="cursor-pointer text-neutral-600">{t('res.sequences')}</summary>
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

      {help && (
        <Modal title={t(`help.${help}.title` as Key)} onClose={() => setHelp(null)}>
          <div className="space-y-2 text-sm text-neutral-800">
            <HelpBody topic={help} />
          </div>
        </Modal>
      )}
    </div>
  )
}

function Metric({ label, value, help, onHelp, helpTitle }: {
  label: string; value: string; help: HelpTopic; onHelp: (t: HelpTopic) => void; helpTitle: string
}) {
  return (
    <div className="border border-neutral-200 bg-white p-3">
      <div className="text-[11px] text-neutral-500">
        {label} <QuestionMark topic={help} onOpen={onHelp} title={helpTitle} />
      </div>
      <div className="mono mt-1 text-xl text-neutral-900">{value}</div>
    </div>
  )
}

// Per-residue pLDDT trace: WT (grey) vs mutant (black), mutation position marked.
function PlddtChart({ wt, mut, position, wtAA, mutAA }: {
  wt: number[]; mut: number[]; position: number; wtAA: string; mutAA: string
}) {
  const { t } = useI18n()
  const xs = wt.map((_, i) => i + 1)
  const data = [
    {
      x: xs, y: wt, type: 'scatter', mode: 'lines', name: 'WT',
      line: { color: '#9ca3af', width: 1.5 },
    },
    {
      x: xs, y: mut, type: 'scatter', mode: 'lines', name: `${wtAA}${position}${mutAA}`,
      line: { color: '#111111', width: 2 },
    },
    {
      x: [position, position], y: [
        Math.min(...wt, ...mut) - 2, Math.max(...wt, ...mut) + 2,
      ], type: 'scatter', mode: 'lines', name: t('res.trace.mutation'),
      line: { color: '#b91c1c', width: 1, dash: 'dot' }, showlegend: false,
    },
  ]
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 45 },
    paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
    font: { color: '#525252', size: 11 },
    xaxis: { title: { text: t('res.xaxis.residue') }, linecolor: '#d4d4d4' },
    yaxis: { title: { text: 'pLDDT' }, range: [0, 100], gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
    legend: { orientation: 'h', y: 1.15 },
  }
  return <Plot data={data} layout={layout} />
}

function MetricSmall({ label, value, help, onHelp, helpTitle }: {
  label: string; value: string; help?: HelpTopic; onHelp?: (t: HelpTopic) => void; helpTitle?: string
}) {
  return (
    <div className="border border-neutral-200 bg-white px-3 py-2">
      <span className="text-neutral-500">{label}:</span>{' '}
      {help && onHelp && <QuestionMark topic={help} onOpen={onHelp} title={helpTitle ?? ''} />}{' '}
      <span className="mono text-neutral-800">{value}</span>
    </div>
  )
}