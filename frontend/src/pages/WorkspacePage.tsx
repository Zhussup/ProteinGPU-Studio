// WorkspacePage: последовательность → мутация → запуск → 3D-оверлей + карточки RMSD + история.
// WorkspacePage：序列 → 突变 → 运行 → 3D 叠加 + RMSD 卡片 + 历史。
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useJob } from '../lib/useJob'
import { useI18n } from '../i18n'
import type {
  EnsembleResult, GpuInfo, InferenceProfile, JobSummary, MutationResult,
  Preset, ScanMapResult, ScanResult,
} from '../lib/types'
import SequenceInput, { stripFasta } from '../components/SequenceInput'
import MutationPicker from '../components/MutationPicker'
import MutagenesisDial from '../components/MutagenesisDial'
import RunPanel from '../components/RunPanel'
import ResultTabs from '../components/ResultTabs'
import ScanPanel from '../components/ScanPanel'
import ScanMapPanel, { type PaintMetric } from '../components/ScanMapPanel'
import EnsemblePanel from '../components/EnsemblePanel'
import MoleculeViewer from '../components/MoleculeViewer'
import ProteinViewer from '../components/ProteinViewer'
import HistoryPanel from '../components/HistoryPanel'
import MutationsCompare from '../components/MutationsCompare'
import SensitivityCompare from '../components/SensitivityCompare'

const LIMITS = { min: 10, max: 600 }

export default function WorkspacePage() {
  const { t, lang } = useI18n()
  const [input, setInput] = useState('')
  const [position, setPosition] = useState(44)
  const [mutantAA, setMutantAA] = useState('A')
  const [profile, setProfile] = useState<InferenceProfile>('auto')
  const [presets, setPresets] = useState<Preset[]>([])
  const [gpu, setGpu] = useState<GpuInfo | null>(null)
  const [result, setResult] = useState<MutationResult | null>(null)
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [ensembleResult, setEnsembleResult] = useState<EnsembleResult | null>(null)
  const [pickedEnsIdx, setPickedEnsIdx] = useState<number | null>(null)
  // карта чувствительности (dum.md §5): 19-векторы по позициям + 3D-раскраска
  // 敏感性图谱（dum.md §5）：逐位点 19 维向量 + 3D 着色
  const [mapResult, setMapResult] = useState<ScanMapResult | null>(null)
  const [mapPaint, setMapPaint] = useState<{ scores: (number | null)[]; metric: PaintMetric } | null>(null)
  const [mapFrom, setMapFrom] = useState(1)
  const [mapTo, setMapTo] = useState(76)
  // ручка мутагенеза (dum.md §2): μ = одновременных замен, τ = температура
  // спектра Грэнтэма, K = размер ансамбля; exhaustive = все 19 замен
  // 突变旋钮（dum.md §2）：μ = 同时替换数，τ = Grantham 谱温度，
  // K = ensemble 大小；exhaustive = 全部 19 种替换
  const [dialExhaustive, setDialExhaustive] = useState(false)
  const [dialMu, setDialMu] = useState(1)
  const [dialTau, setDialTau] = useState(0.5)
  const [dialK, setDialK] = useState(20)
  const [dialSeed, setDialSeed] = useState<number | null>(null)
  const [wtPdb, setWtPdb] = useState<string | null>(null)
  const [mutPdb, setMutPdb] = useState<string | null>(null)
  const [history, setHistory] = useState<JobSummary[]>([])
  // выполненная задача, чью панель результата/скана показываем — перезапрашивается при смене языка
  // 正在展示结果/扫描面板的已完成任务——切换语言时重新请求
  const [resultJob, setResultJob] = useState<{ id: string; kind: string } | null>(null)
  const job = useJob()

  const loadHistory = useCallback(() => {
    api.jobs(20).then(setHistory).catch(() => {})
  }, [])

  useEffect(() => {
    api.presets().then((r) => setPresets(r.presets)).catch(() => {})
    api.gpu().then(setGpu).catch(() => {})
  }, [loadHistory, lang]) // повторный запрос при смене языка: тексты пресетов приходят с бэкенда | 切换语言时重新请求：预设文本由后端返回

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const seq = stripFasta(input)
  const seqOk = seq.length >= LIMITS.min && seq.length <= LIMITS.max && /^[ACDEFGHIKLMNPQRSTVWY]+$/.test(seq)
  const posOk = position >= 1 && position <= seq.length
  const canRun = seqOk && posOk

  // держим позицию мутации валидной, когда приходит более короткая/длинная последовательность
  // 序列变长/变短时，保持突变位置有效
  useEffect(() => {
    if (seq.length >= 1 && position > seq.length) setPosition(seq.length)
    if (position < 1 && seq.length >= 1) setPosition(1)
  }, [seq.length, position])

  // диапазон scan-map следует за последовательностью: это диапазон ЕЁ позиций
  // scan-map 范围跟随序列：它是序列自身位置的区间
  useEffect(() => {
    setMapFrom(1)
    setMapTo(seq.length)
  }, [seq.length])

  const applyPreset = useCallback((p: Preset) => {
    setInput(`>${p.name}\n${p.sequence}`)
    if (p.position) setPosition(p.position)
    if (p.mutant_aa) setMutantAA(p.mutant_aa)
  }, [])

  const afterDone = useCallback(async (jobId: string, kind: string) => {
    try {
      if (kind === 'mutate') {
        setResult(await api.result(jobId) as unknown as MutationResult)
        setMutPdb(await api.pdb(jobId, 'mut_aligned.pdb'))
        setResultJob({ id: jobId, kind })
      } else if (kind === 'scan') {
        const res = await api.result(jobId) as unknown as ScanResult
        setScanResult(res)
        setMutPdb(await api.pdb(jobId, `scan_${res.best}.pdb`))
        setResultJob({ id: jobId, kind })
      } else if (kind === 'ensemble') {
        const res = await api.result(jobId) as unknown as EnsembleResult
        setEnsembleResult(res)
        setPickedEnsIdx(0)
        if (res.variants[0]) {
          setMutPdb(await api.pdb(jobId, res.variants[0].pdb_file as `ens_${string}.pdb`))
        }
        setResultJob({ id: jobId, kind })
      } else if (kind === 'scan_map') {
        const res = await api.result(jobId) as unknown as ScanMapResult
        setMapResult(res)
        setMapPaint(null)
        setResultJob({ id: jobId, kind })
      }
      setWtPdb(await api.pdb(jobId, 'wt.pdb'))
    } catch { /* файлы могут отсутствовать для прогонов только-WT */ }
  }, [])

  const runPredict = () => {
    setResult(null); setMutPdb(null); setScanResult(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    setMapResult(null); setMapPaint(null)
    job.run(() => api.submitPredict(seq, profile === 'auto' ? undefined : profile))
  }

  const runMutate = () => {
    setResult(null); setScanResult(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    setMapResult(null); setMapPaint(null)
    job.run(() => api.submitMutate(seq, position, mutantAA, profile === 'auto' ? undefined : profile))
  }

  const runScan = () => {
    setResult(null); setScanResult(null); setMutPdb(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    setMapResult(null); setMapPaint(null)
    job.run(() => api.submitScan(seq, position, profile === 'auto' ? undefined : profile))
  }

  const runEnsemble = () => {
    setResult(null); setScanResult(null); setMutPdb(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    setMapResult(null); setMapPaint(null)
    const mode = dialExhaustive ? 'exhaustive' as const : 'sampled' as const
    job.run(() => api.submitEnsemble(
      seq, position, mode,
      dialExhaustive ? 1 : dialMu,
      dialTau,
      dialExhaustive ? 19 : dialK,
      dialSeed,
      profile === 'auto' ? undefined : profile,
    ))
  }

  // карта чувствительности: 19 фолдов на позицию в [mapFrom..mapTo]; результат
  // только с данными (без PDB мутантов), структура WT приходит из той же задачи
  // 敏感性图谱：[mapFrom..mapTo] 内每个位置 19 次折叠；结果仅含数据
  //（无突变体 PDB），WT 结构取自同一任务
  const runMap = () => {
    setResult(null); setScanResult(null); setMutPdb(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    setMapResult(null); setMapPaint(null)
    const positions = Array.from(
      { length: Math.max(0, mapTo - mapFrom + 1) },
      (_, i) => mapFrom + i,
    )
    job.run(() => api.submitScanMap(seq, positions, profile === 'auto' ? undefined : profile))
  }

  // опрос завершения: по готовности забираем артефакты, обновляем историю
  // 完成轮询：完成后取工件，刷新历史
  useEffect(() => {
    const st = job.status?.status
    if (st === 'done') {
      void afterDone(job.status!.job_id, job.status!.kind)
    }
    if (st === 'done' || st === 'error') loadHistory()
  }, [job.status?.status, job.status?.job_id, job.status?.kind]) // eslint-disable-line react-hooks/exhaustive-deps

  // показываем оверлей мутанта скана во вьюере (scan_<AA>.pdb выровнен по Kabsch)
  // 在查看器中显示扫描突变体的叠加（scan_<AA>.pdb 已按 Kabsch 对齐）
  const pickScanRow = useCallback(async (mutAA: string) => {
    const jobId = job.status?.job_id
    if (!jobId) return
    try {
      setMutPdb(await api.pdb(jobId, `scan_${mutAA}.pdb`))
      setPosition(scanResult?.position ?? position)
    } catch { /* артефакт мог исчезнуть */ }
  }, [job.status?.job_id, scanResult?.position, position])

  // показываем оверлей варианта ансамбля во вьюере (ens_XX.pdb, выровнен к WT)
  // 在查看器中显示 ensemble 变体的叠加（ens_XX.pdb，已对齐到 WT）
  const pickEnsembleRow = useCallback(async (i: number) => {
    // resultJob покрывает и восстановленные задачи (job.status знает только текущий прогон)
    // resultJob 也覆盖恢复的任务（job.status 只知道当前运行）
    const jobId = resultJob?.id ?? job.status?.job_id
    const res = ensembleResult
    const row = res?.variants[i]
    if (!jobId || !row) return
    try {
      setMutPdb(await api.pdb(jobId, row.pdb_file as `ens_${string}.pdb`))
      setPickedEnsIdx(i)
      setPosition(res!.position)
    } catch { /* artifact may be gone */ }
  }, [resultJob, job.status?.job_id, ensembleResult])

  // восстановление прошлой задачи: последовательность + мутация обратно в поля, артефакты во вьюер
  // 恢复历史任务：序列 + 突变回填到输入框，工件放回查看器
  const restore = useCallback(async (j: JobSummary) => {
    if (j.sequence) setInput(j.sequence)
    if (j.position) setPosition(j.position)
    if (j.mutant_aa) setMutantAA(j.mutant_aa)
    setResult(null)
    setMutPdb(null)
    setScanResult(null)
    setEnsembleResult(null)
    setPickedEnsIdx(null)
    setMapResult(null)
    setMapPaint(null)
    try {
      if (j.kind === 'mutate') {
        setResult(await api.result(j.job_id) as unknown as MutationResult)
        setMutPdb(await api.pdb(j.job_id, 'mut_aligned.pdb'))
        setResultJob({ id: j.job_id, kind: j.kind })
      } else if (j.kind === 'scan') {
        const res = await api.result(j.job_id) as unknown as ScanResult
        setScanResult(res)
        setMutPdb(await api.pdb(j.job_id, `scan_${res.best}.pdb`))
        setResultJob({ id: j.job_id, kind: j.kind })
      } else if (j.kind === 'ensemble') {
        const res = await api.result(j.job_id) as unknown as EnsembleResult
        setEnsembleResult(res)
        setPickedEnsIdx(0)
        if (res.variants[0]) {
          setMutPdb(await api.pdb(j.job_id, res.variants[0].pdb_file as `ens_${string}.pdb`))
        }
        // диск читает обратно конфигурацию, породившую этот ансамбль;
        // seed в поле не нужен — производный seed воспроизводится из конфига
        // (явный оверрайд сбрасываем: иначе он протёк бы в повторные прогоны)
        // 旋钮读回生成该 ensemble 的配置；seed 无需回填——派生 seed
        // 可由配置复现（显式覆盖会被清空，否则会泄漏到后续重跑中）
        if (j.mode) setDialExhaustive(j.mode === 'exhaustive')
        if (j.mu) setDialMu(j.mu)
        if (typeof j.tau === 'number') setDialTau(j.tau)
        if (j.k) setDialK(j.k)
        setDialSeed(null)
        setResultJob({ id: j.job_id, kind: j.kind })
      } else if (j.kind === 'scan_map') {
        const res = await api.result(j.job_id) as unknown as ScanMapResult
        setMapResult(res)
        setResultJob({ id: j.job_id, kind: j.kind })
      }
      setWtPdb(await api.pdb(j.job_id, 'wt.pdb'))
    } catch { /* артефакты могли исчезнуть */ }
  }, [])

  // смена языка → тексты бэкенда (сводка) приходят на новом языке
  // 切换语言 → 后端文本（摘要）以新语言重新获取
  useEffect(() => {
    if (!resultJob) return
    const kind = resultJob.kind
    if (kind !== 'mutate' && kind !== 'scan' && kind !== 'ensemble' && kind !== 'scan_map') return
    let live = true
    api.result(resultJob.id).then((res) => {
      if (!live) return
      if (kind === 'mutate') {
        setResult(res as unknown as MutationResult)
        setScanResult(null)
        setEnsembleResult(null)
      } else if (kind === 'scan') {
        setScanResult(res as unknown as ScanResult)
        setResult(null)
        setEnsembleResult(null)
      } else if (kind === 'ensemble') {
        setEnsembleResult(res as unknown as EnsembleResult)
        setResult(null)
        setScanResult(null)
      } else {
        setMapResult(res as unknown as ScanMapResult)
        setResult(null)
        setScanResult(null)
        setEnsembleResult(null)
      }
    }).catch(() => { /* артефакты задачи могли исчезнуть */ })
    return () => { live = false }
  }, [lang]) // eslint-disable-line react-hooks/exhaustive-deps -- resultJob читается, а не триггер

  return (
    <div className="grid gap-5 lg:grid-cols-[400px_1fr]">
      <div className="panel space-y-5 p-4">
        <SequenceInput value={input} onChange={setInput} presets={presets} minLen={LIMITS.min} maxLen={LIMITS.max} />
        <MutationPicker
          sequence={seq}
          position={position}
          mutantAA={mutantAA}
          onChange={(p, aa) => { setPosition(p); setMutantAA(aa) }}
          presets={presets}
          onApplyPreset={applyPreset}
        />
        <MutagenesisDial
          seqLen={seq.length}
          profile={profile}
          exhaustive={dialExhaustive}
          mu={dialMu}
          tau={dialTau}
          k={dialExhaustive ? 19 : dialK}
          seed={dialSeed}
          onExhaustive={setDialExhaustive}
          onMu={setDialMu}
          onTau={setDialTau}
          onK={setDialK}
          onSeed={setDialSeed}
        />
        <RunPanel
          canRun={canRun}
          running={!!job.running}
          status={job.status}
          error={job.error}
          gpu={gpu}
          profile={profile}
          onProfileChange={setProfile}
          onRunPredict={runPredict}
          onRunMutate={runMutate}
          onRunScan={runScan}
          onRunEnsemble={runEnsemble}
          onRunMap={runMap}
          mapFrom={mapFrom}
          mapTo={mapTo}
          seqLen={seq.length}
          onMapRangeChange={(a, b) => { setMapFrom(a); setMapTo(Math.max(a, b)) }}
          onReset={() => {
            setResult(null); setWtPdb(null); setMutPdb(null); setScanResult(null)
            setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
            setMapResult(null); setMapPaint(null)
          }}
        />
        <HistoryPanel
          jobs={history}
          currentJobId={job.status?.job_id ?? null}
          onRestore={(j) => void restore(j)}
          onRefresh={loadHistory}
        />
      </div>

      <div className="space-y-5">
        <MoleculeViewer
          wtPdb={wtPdb}
          mutPdb={mutPdb}
          aligned={true}
          mutationPosition={position}
          residueScores={mapPaint?.scores ?? null}
          scoreLabel={mapPaint ? t('viewer.legendSensitivity') : undefined}
        />
        <ProteinViewer
          sequence={seqOk ? seq : ''}
          position={position}
          onPositionChange={setPosition}
          plddtWt={result?.plddt_wt_list ?? null}
          result={result}
          scan={scanResult}
          ensemble={ensembleResult}
        />
        {mapResult ? (
          <div className="panel p-4">
            <h3 className="mb-3 text-sm font-medium text-neutral-900">
              {t('ws.mapTitle', { n: mapResult.n_positions })}
            </h3>
            <ScanMapPanel
              result={mapResult}
              jobId={resultJob?.id ?? job.status?.job_id ?? null}
              paintedMetric={mapPaint?.metric ?? null}
              onPaint={(scores, metric) => setMapPaint({ scores, metric })}
              onClearPaint={() => setMapPaint(null)}
            />
          </div>
        ) : scanResult ? (
          <div className="panel p-4">
            <h3 className="mb-3 text-sm font-medium text-neutral-900">
              {t('ws.scanTitle', { pos: scanResult.position })}
            </h3>
            <ScanPanel result={scanResult} onPickRow={(aa) => void pickScanRow(aa)} />
          </div>
        ) : ensembleResult ? (
          <div className="panel p-4">
            <h3 className="mb-3 text-sm font-medium text-neutral-900">
              {t('ws.ensembleTitle', { pos: ensembleResult.position })}
            </h3>
            <EnsemblePanel
              result={ensembleResult}
              onPickRow={(i) => void pickEnsembleRow(i)}
              pickedIndex={pickedEnsIdx}
            />
          </div>
        ) : result?.rmsd ? (
          <div className="panel p-4" data-demo="metrics">
            <h3 className="mb-3 text-sm font-medium text-neutral-900">{t('ws.overlayResult')}</h3>
            <ResultTabs result={result} />
          </div>
        ) : (
          <div className="panel p-4 text-xs text-neutral-500">
            {t('ws.hint')}
          </div>
        )}
        <MutationsCompare jobs={history} wtSequence={seqOk ? seq : ''} />
        <SensitivityCompare jobs={history} wtSequence={seqOk ? seq : ''} />
      </div>
    </div>
  )
}