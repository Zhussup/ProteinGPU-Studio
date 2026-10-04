// StructurePage: предсказание структуры и одна мутация — 3D-наложение,
// карточки RMSD/TM-score/pLDDT и 2D-браузер последовательности.
// Режим расчёта — явный выбор «Только WT / WT + мутант»: выбор остатка
// появляется только там, где он нужен.
// StructurePage：结构预测与单个突变——3D 叠加、RMSD/TM-score/pLDDT 卡片
// 与二维序列浏览器。计算模式为显式选择“仅 WT / WT + 突变体”：
// 残基选择只在需要时出现。
import { useState } from 'react'
import { useI18n } from '../i18n'
import { useWorkspace } from '../state/workspace'
import PageFrame from '../components/PageFrame'
import MutationPicker from '../components/MutationPicker'
import RunRow from '../components/RunRow'
import JobProgress from '../components/JobProgress'
import ResultTabs from '../components/ResultTabs'
import MoleculeViewer from '../components/MoleculeViewer'
import ProteinViewer from '../components/ProteinViewer'

type Mode = 'wt' | 'mut'

export default function StructurePage() {
  const { t } = useI18n()
  const ws = useWorkspace()
  // по умолчанию — «WT + мутант»: это основное действие страницы
  // 默认“WT + 突变体”：本页的主操作
  const [mode, setMode] = useState<Mode>('mut')
  const myKind = ws.jobStatus?.kind === 'predict' || ws.jobStatus?.kind === 'mutate'

  return (
    <PageFrame
      titleKey="nav.structure"
      leadKey="hint.structure"
      controls={
        <>
          {/* режим: только WT или WT + мутант */}
          {/* 模式：仅 WT 或 WT + 突变体 */}
          <div>
            <div className="mb-1.5 text-[11px] text-neutral-500">{t('struct.mode.title')}</div>
            <div className="flex" role="radiogroup" aria-label={t('struct.mode.title')}>
              {(['wt', 'mut'] as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="radio"
                  aria-checked={mode === m}
                  onClick={() => setMode(m)}
                  className={`flex-1 border px-2.5 py-1.5 text-xs transition first:border-r-0 ${
                    mode === m
                      ? 'border-neutral-900 bg-neutral-900 text-white'
                      : 'border-neutral-300 bg-white text-neutral-700 hover:border-neutral-900'
                  }`}
                >
                  {t(m === 'wt' ? 'run.wtOnly' : 'run.wtMutant')}
                </button>
              ))}
            </div>
          </div>

          {mode === 'mut' && (
            <MutationPicker
              sequence={ws.seqOk ? ws.seq : ''}
              position={ws.position}
              mutantAA={ws.mutantAA}
              onChange={(p, aa) => { ws.setPosition(p); ws.setMutantAA(aa) }}
              presets={ws.presets}
              onApplyPreset={ws.applyPreset}
            />
          )}

          <RunRow
            label={t(mode === 'wt' ? 'struct.run.wt' : 'struct.run.mut')}
            onClick={mode === 'wt' ? ws.runPredict : ws.runMutate}
          />

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
        wtPdb={ws.wtPdb}
        mutPdb={ws.mutPdb}
        aligned={true}
        mutationPosition={ws.position}
        residueScores={ws.mapPaint?.scores ?? null}
        scoreLabel={ws.mapPaint ? t('viewer.legendSensitivity') : undefined}
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
      {ws.result?.rmsd ? (
        <div className="panel p-4" data-demo="metrics">
          <h3 className="mb-3 text-sm font-medium text-neutral-900">{t('ws.overlayResult')}</h3>
          <ResultTabs result={ws.result} />
        </div>
      ) : (
        <div className="panel p-4 text-xs text-neutral-500">{t('ws.hint')}</div>
      )}
    </PageFrame>
  )
}
