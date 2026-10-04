// ScanPage: насыщающий скан одной позиции — все 19 замен, ранжирование по
// локальному отклику, клик по строке показывает мутанта в 3D.
// ScanPage：单位点饱和扫描——全部 19 种替换，按局部响应排序，
// 点击行可在 3D 中显示该突变体。
import { useState } from 'react'
import { useI18n } from '../i18n'
import { useWorkspace } from '../state/workspace'
import PageFrame from '../components/PageFrame'
import PositionControl from '../components/PositionControl'
import RunRow from '../components/RunRow'
import JobProgress from '../components/JobProgress'
import ScanPanel from '../components/ScanPanel'
import MoleculeViewer from '../components/MoleculeViewer'
import ProteinViewer from '../components/ProteinViewer'

export default function ScanPage() {
  const { t } = useI18n()
  const ws = useWorkspace()
  const [pickedAA, setPickedAA] = useState<string | null>(null)
  const myKind = ws.jobStatus?.kind === 'scan'

  return (
    <PageFrame
      titleKey="nav.scan"
      leadKey="hint.scan"
      controls={
        <>
          <PositionControl
            sequence={ws.seqOk ? ws.seq : ''}
            position={ws.position}
            onChange={ws.setPosition}
          />
          <RunRow label={t('scan.run')} onClick={ws.runScan} tone="danger" />
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
      />
      <ProteinViewer
        sequence={ws.seqOk ? ws.seq : ''}
        position={ws.position}
        onPositionChange={ws.setPosition}
        plddtWt={ws.result?.plddt_wt_list ?? null}
        result={ws.result}
        scan={ws.scanResult}
        ensemble={ws.ensembleResult}
      />
      {ws.scanResult ? (
        <div className="panel p-4">
          <h3 className="mb-3 text-sm font-medium text-neutral-900">
            {t('ws.scanTitle', { pos: ws.scanResult.position })}
          </h3>
          <ScanPanel
            result={ws.scanResult}
            pickedAA={pickedAA}
            onPickRow={(aa) => { setPickedAA(aa); ws.pickScanRow(aa) }}
          />
        </div>
      ) : (
        <div className="panel p-4 text-xs text-neutral-500">{t('page.noResult')}</div>
      )}
    </PageFrame>
  )
}
