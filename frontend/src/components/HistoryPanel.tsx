// HistoryPanel: recent jobs (from SQLite via GET /api/v1/jobs). Click a done
// job to restore its result into the workspace — sequence, mutation, PDBs.
import type { JobSummary } from '../lib/types'
import { useI18n, type Key } from '../i18n'

export interface HistoryPanelProps {
  jobs: JobSummary[]
  currentJobId?: string | null
  onRestore: (job: JobSummary) => void
  onRefresh: () => void
}

const STATUS_MARK: Record<JobSummary['status'], string> = {
  done: 'bg-neutral-900',
  error: 'bg-red-700',
  running: 'stage-active bg-neutral-400',
  queued: 'bg-neutral-300',
}

const KIND_KEYS: Record<string, Key> = {
  predict: 'hist.kind.predict',
  mutate: 'hist.kind.mutate',
  scan: 'hist.kind.scan',
  ensemble: 'hist.kind.ensemble',
  scan_map: 'hist.kind.map',
}

// "2026-09-11T14:23:05" → "11.09 14:23"
function shortTime(iso: string): string {
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)} ${iso.slice(11, 16)}`
}

export default function HistoryPanel({ jobs, currentJobId, onRestore, onRefresh }: HistoryPanelProps) {
  const { t } = useI18n()
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-900">{t('hist.title')}</label>
        <button
          onClick={onRefresh}
          className="text-[11px] text-neutral-500 underline hover:text-neutral-900"
        >
          {t('hist.refresh')}
        </button>
      </div>

      {jobs.length === 0 ? (
        <div className="text-xs text-neutral-400">{t('hist.empty')}</div>
      ) : (
        <div className="max-h-56 overflow-y-auto border border-neutral-200">
          {jobs.map((j) => {
            const restorable = j.status === 'done'
            const current = j.job_id === currentJobId
            return (
              <button
                key={j.job_id}
                onClick={() => restorable && onRestore(j)}
                disabled={!restorable}
                title={j.error ?? `${t(KIND_KEYS[j.kind])} · ${restorable ? t('hist.restoreHint') : t('hist.noResult')}`}
                className={`flex w-full items-center gap-2 border-b border-neutral-100 px-2.5 py-1.5 text-left text-xs last:border-b-0 ${
                  restorable ? 'hover:bg-neutral-100' : 'cursor-default'
                } ${current ? 'bg-neutral-100' : 'bg-white'}`}
              >
                <span className={`inline-block h-2 w-2 shrink-0 ${STATUS_MARK[j.status] ?? 'bg-neutral-300'}`} />
                <span className="mono w-16 shrink-0 font-medium text-neutral-900">
                  {j.kind === 'mutate' || j.kind === 'ensemble' || j.kind === 'scan_map' ? j.label : 'WT'}
                </span>
                <span className="flex-1 truncate text-neutral-500">
                  {j.status === 'error'
                    ? (j.error ?? t('hist.error'))
                    : j.kind === 'predict'
                      ? t('hist.prediction', { label: j.label })
                      : `${j.sequence.length} aa`}
                </span>
                <span className="mono shrink-0 text-neutral-400">{shortTime(j.created_at)}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}