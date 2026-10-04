// PlmPage: PLM-скрин всего белка. Бюджет фолдинга — явный выбор 0/1/2:
// ноль означает «только PLM, секунды» и подписан прямо у контрола.
// PlmPage：全蛋白 PLM 筛查。折叠预算为显式的 0/1/2 选择：
// 零表示“仅 PLM，数秒”，控件旁直接注明。
import { useI18n } from '../i18n'
import { useWorkspace } from '../state/workspace'
import PageFrame from '../components/PageFrame'
import RunRow from '../components/RunRow'
import JobProgress from '../components/JobProgress'
import PlmScreenPanel from '../components/PlmScreenPanel'
import MoleculeViewer from '../components/MoleculeViewer'

const TOP_K = [0, 1, 2]

export default function PlmPage() {
  const { t } = useI18n()
  const ws = useWorkspace()
  const myKind = ws.jobStatus?.kind === 'plm_screen'

  return (
    <PageFrame
      titleKey="nav.plm"
      leadKey="hint.plm"
      controls={
        <>
          <div className="space-y-2">
            <div className="text-[11px] text-neutral-500">{t('plm.foldLabel')}</div>
            <div className="flex" role="radiogroup" aria-label={t('plm.foldLabel')}>
              {TOP_K.map((k) => (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={ws.plmTopK === k}
                  onClick={() => ws.setPlmTopK(k)}
                  disabled={ws.jobRunning}
                  className={`mono flex-1 border px-2.5 py-1.5 text-xs transition first:border-r-0 disabled:opacity-40 ${
                    ws.plmTopK === k
                      ? 'border-neutral-900 bg-neutral-900 text-white'
                      : 'border-neutral-300 bg-white text-neutral-700 hover:border-neutral-900'
                  }`}
                >
                  {k}
                </button>
              ))}
            </div>
            <div className="text-[10px] text-neutral-400">{t('plm.foldHintZero')}</div>
          </div>

          <RunRow label={t('plm.run')} onClick={ws.runPlm} tone="danger" />
          {myKind && (
            <JobProgress
              status={ws.jobStatus}
              error={ws.jobError}
              running={ws.jobRunning}
              onCancel={ws.cancelJob}
            />
          )}
        </>
      }
    >
      <MoleculeViewer
        height={320}
        wtPdb={ws.wtPdb}
        mutPdb={ws.mutPdb}
        aligned={true}
        mutationPosition={ws.position}
        residueScores={ws.mapPaint?.scores ?? null}
        scoreLabel={ws.mapPaint ? t('viewer.legendSensitivity') : undefined}
      />
      {ws.plmResult ? (
        <div className="panel p-4">
          <h3 className="mb-3 text-sm font-medium text-neutral-900">
            {t('ws.plmTitle', { n: ws.plmResult.n_positions })}
          </h3>
          <PlmScreenPanel
            result={ws.plmResult}
            jobId={ws.activeJobId}
            paintedMetric={
              ws.mapPaint?.metric === 'plm_v_max' || ws.mapPaint?.metric === 'plm_v_med'
                ? ws.mapPaint.metric
                : null
            }
            onPaint={(scores, metric) => ws.setMapPaint({ scores, metric })}
            onClearPaint={() => ws.setMapPaint(null)}
          />
        </div>
      ) : (
        <div className="panel p-4 text-xs text-neutral-500">{t('page.noResult')}</div>
      )}
    </PageFrame>
  )
}
