// SensitivityPage: карта чувствительности диапазона позиций (19 фолдов на
// позицию). Диапазон и его честная цена — здесь же; «окрасить 3D» красит
// вьюер этой страницы тем же каналом, что и в структуре.
// SensitivityPage：区间位点的敏感性图谱（每个位点 19 次折叠）。
// 区间及其如实代价就在本页；“着色 3D”用与结构页相同的通道给本页查看器着色。
import { useI18n } from '../i18n'
import { useWorkspace } from '../state/workspace'
import PageFrame from '../components/PageFrame'
import RunRow from '../components/RunRow'
import JobProgress from '../components/JobProgress'
import ScanMapPanel from '../components/ScanMapPanel'
import MoleculeViewer from '../components/MoleculeViewer'

export default function SensitivityPage() {
  const { t } = useI18n()
  const ws = useWorkspace()
  const myKind = ws.jobStatus?.kind === 'scan_map'
  const n = Math.max(0, Math.min(ws.mapTo, ws.seq.length) - Math.min(ws.mapFrom, ws.seq.length) + 1)

  return (
    <PageFrame
      titleKey="nav.sensitivity"
      leadKey="hint.sensitivity"
      controls={
        <>
          {/* диапазон scan-map: 19 фолдов на позицию — честная цена показана */}
          {/* scan-map 范围：每个位置 19 次折叠——如实显示代价 */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-neutral-600">
              <label htmlFor="map-from">{t('run.mapRange')}</label>
              <input
                id="map-from"
                type="number"
                min={1}
                max={ws.seq.length}
                value={ws.mapFrom}
                onChange={(e) => ws.setMapRange(
                  Math.max(1, Math.min(ws.seq.length, Number(e.target.value) || 1)),
                  ws.mapTo,
                )}
                disabled={ws.jobRunning}
                className="mono w-16 border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-900 focus:border-neutral-900"
              />
              <span>—</span>
              <input
                id="map-to"
                type="number"
                min={1}
                max={ws.seq.length}
                value={ws.mapTo}
                onChange={(e) => ws.setMapRange(
                  ws.mapFrom,
                  Math.max(1, Math.min(ws.seq.length, Number(e.target.value) || 1)),
                )}
                disabled={ws.jobRunning}
                className="mono w-16 border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-900 focus:border-neutral-900"
              />
            </div>
            <div className="text-[10px] text-neutral-400">
              {t('run.mapCount', { n, folds: n * 19 })}
            </div>
          </div>

          <RunRow label={t('map.run')} onClick={ws.runMap} tone="dangerFill" />
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
      {ws.mapResult ? (
        <div className="panel p-4">
          <h3 className="mb-3 text-sm font-medium text-neutral-900">
            {t('ws.mapTitle', { n: ws.mapResult.n_positions })}
          </h3>
          <ScanMapPanel
            result={ws.mapResult}
            jobId={ws.activeJobId}
            paintedMetric={
              ws.mapPaint?.metric === 'v_max' || ws.mapPaint?.metric === 'v_med'
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
