// EnsemblePage: ансамбль вариантов вокруг позиции. Режим «случайный K» или
// «все 19 замен» — явный выбор, который ПОДМЕНЯЕТ поля: в полном переборе
// μ/τ/K/seed не показываются вовсе (вместо них строка-резюме).
// EnsemblePage：位点周围的变体组合。“随机 K”或“全部 19 种替换”为显式选择，
// 并替换字段：穷举模式下完全不显示 μ/τ/K/seed（改为一行摘要）。
import { useI18n } from '../i18n'
import { useWorkspace } from '../state/workspace'
import PageFrame from '../components/PageFrame'
import PositionControl from '../components/PositionControl'
import EnsembleKnobs from '../components/EnsembleKnobs'
import RunRow from '../components/RunRow'
import JobProgress from '../components/JobProgress'
import EnsemblePanel from '../components/EnsemblePanel'
import MoleculeViewer from '../components/MoleculeViewer'
import ProteinViewer from '../components/ProteinViewer'

export default function EnsemblePage() {
  const { t } = useI18n()
  const ws = useWorkspace()
  const myKind = ws.jobStatus?.kind === 'ensemble'

  return (
    <PageFrame
      titleKey="nav.ensemble"
      leadKey="hint.ensemble"
      controls={
        <>
          <PositionControl
            sequence={ws.seqOk ? ws.seq : ''}
            position={ws.position}
            onChange={ws.setPosition}
          />
          <EnsembleKnobs
            seqLen={ws.seq.length}
            profile={ws.profile}
            mode={ws.dialExhaustive ? 'exhaustive' : 'sampled'}
            mu={ws.dialMu}
            tau={ws.dialTau}
            k={ws.dialK}
            seed={ws.dialSeed}
            onMode={(m) => ws.setDialExhaustive(m === 'exhaustive')}
            onMu={ws.setDialMu}
            onTau={ws.setDialTau}
            onK={ws.setDialK}
            onSeed={ws.setDialSeed}
          />
          <RunRow label={t('ens.run')} onClick={ws.runEnsemble} tone="outline" />
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
      {ws.ensembleResult ? (
        <div className="panel p-4">
          <h3 className="mb-3 text-sm font-medium text-neutral-900">
            {t('ws.ensembleTitle', { pos: ws.ensembleResult.position })}
          </h3>
          <EnsemblePanel
            result={ws.ensembleResult}
            onPickRow={ws.pickEnsembleRow}
            pickedIndex={ws.pickedEnsIdx}
          />
        </div>
      ) : (
        <div className="panel p-4 text-xs text-neutral-500">{t('page.noResult')}</div>
      )}
    </PageFrame>
  )
}
