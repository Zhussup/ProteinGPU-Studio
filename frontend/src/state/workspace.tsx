// workspace: общий контекст рабочей области — белок, вычислительный профиль,
// результаты всех видов анализа, ручка ансамбля, история задач и единственный
// поллер активной задачи. Живёт над роутером страниц, поэтому задача переживает
// переход между страницами (useJob снимает поллинг только при unmount, а
// провайдер не размонтируется).
// workspace：工作台共享上下文——蛋白、算力配置、各类分析结果、ensemble 旋钮、
// 任务历史，以及唯一的活动任务轮询器。它位于页面路由之上，因此任务在页面
// 切换时不会中断（useJob 仅在卸载时停止轮询，而 Provider 从不卸载）。
import {
  createContext, useCallback, useContext, useEffect, useState,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useJob } from '../lib/useJob'
import { useI18n, type Key } from '../i18n'
import type {
  EnsembleResult, GpuInfo, InferenceProfile, JobSummary, JobStatus, MutationResult,
  PlmScreenResult, Preset, ScanMapResult, ScanResult,
} from '../lib/types'
import { stripFasta } from '../components/SequenceInput'
import type { PaintMetric } from '../components/ScanMapPanel'
import type { PlmPaintMetric } from '../components/PlmScreenPanel'

export const LIMITS = { min: 10, max: 600 }

// тип задачи → страница, где живёт её результат: цель для мини-статуса
// в сайдбаре и для восстановления задачи из истории
// 任务类型 → 存放其结果页面：侧栏迷你状态与历史恢复的目标
export const KIND_ROUTE: Record<string, string> = {
  predict: '/structure',
  mutate: '/structure',
  scan: '/scan',
  ensemble: '/ensemble',
  scan_map: '/sensitivity',
  plm_screen: '/plm',
  dms_validation: '/validation',
  benchmark: '/benchmarks',
  benchmark_kernels: '/benchmarks',
}

// подписи видов задач (история + мини-статус) — один источник для обоих мест
// 任务类型标签（历史 + 迷你状态）——两处的单一来源
export const KIND_KEYS: Record<string, Key> = {
  predict: 'hist.kind.predict',
  mutate: 'hist.kind.mutate',
  scan: 'hist.kind.scan',
  ensemble: 'hist.kind.ensemble',
  scan_map: 'hist.kind.map',
  plm_screen: 'hist.kind.plm',
  dms_validation: 'hist.kind.dms',
  benchmark: 'hist.kind.benchmark',
  benchmark_kernels: 'hist.kind.benchmark',
}

// чем раскрашен 3D-вьюер: скалярный канал scan-map или PLM
// 3D 查看器着色所用的标量通道：scan-map 或 PLM
export interface MapPaint {
  scores: (number | null)[]
  metric: PaintMetric | PlmPaintMetric
}

export interface WorkspaceCtx {
  // белок | 蛋白
  input: string
  setInput: (s: string) => void
  seq: string
  seqOk: boolean
  canRun: boolean
  position: number
  setPosition: (p: number) => void
  mutantAA: string
  setMutantAA: (aa: string) => void
  presets: Preset[]
  applyPreset: (p: Preset) => void

  // вычисления | 算力
  profile: InferenceProfile
  setProfile: (p: InferenceProfile) => void
  gpu: GpuInfo | null

  // результаты | 结果
  result: MutationResult | null
  scanResult: ScanResult | null
  ensembleResult: EnsembleResult | null
  pickedEnsIdx: number | null
  mapResult: ScanMapResult | null
  plmResult: PlmScreenResult | null
  plmTopK: number
  setPlmTopK: (v: number) => void
  mapFrom: number
  mapTo: number
  setMapRange: (from: number, to: number) => void
  mapPaint: MapPaint | null
  setMapPaint: (p: MapPaint | null) => void
  wtPdb: string | null
  mutPdb: string | null
  resultJob: { id: string; kind: string } | null
  activeJobId: string | null

  // ручка ансамбля | ensemble 旋钮
  dialExhaustive: boolean
  setDialExhaustive: (v: boolean) => void
  dialMu: number
  setDialMu: (v: number) => void
  dialTau: number
  setDialTau: (v: number) => void
  dialK: number
  setDialK: (v: number) => void
  dialSeed: number | null
  setDialSeed: (v: number | null) => void

  // задачи | 任务
  jobStatus: JobStatus | null
  jobRunning: boolean
  jobError: string | null
  cancelJob: () => void
  runPredict: () => void
  runMutate: () => void
  runScan: () => void
  runEnsemble: () => void
  runMap: () => void
  runPlm: () => void
  resetResults: () => void

  // история | 历史
  history: JobSummary[]
  refreshHistory: () => void
  restore: (j: JobSummary) => void
  pickScanRow: (aa: string) => void
  pickEnsembleRow: (i: number) => void
}

const Ctx = createContext<WorkspaceCtx | null>(null)

export function useWorkspace(): WorkspaceCtx {
  const v = useContext(Ctx)
  if (!v) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return v
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { lang } = useI18n()
  const navigate = useNavigate()

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
  const [mapPaint, setMapPaint] = useState<MapPaint | null>(null)
  // PLM-скрин всего белка: один forward-проход + опциональный top-K фолдинг
  // 全蛋白 PLM 筛查：一次前向 + 可选的 top-K 折叠
  const [plmResult, setPlmResult] = useState<PlmScreenResult | null>(null)
  const [plmTopK, setPlmTopK] = useState(1)
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
  const { status: jobStatus, running: jobRunning, error: jobError } = job

  const loadHistory = useCallback(() => {
    api.jobs(20).then(setHistory).catch(() => {})
  }, [])

  useEffect(() => {
    api.presets().then((r) => setPresets(r.presets)).catch(() => {})
    api.gpu().then(setGpu).catch(() => {})
  }, [lang]) // повторный запрос при смене языка: тексты пресетов приходят с бэкенда | 切换语言时重新请求：预设文本由后端返回

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

  const clearResults = useCallback(() => {
    setResult(null)
    setScanResult(null)
    setEnsembleResult(null)
    setPickedEnsIdx(null)
    setResultJob(null)
    setMapResult(null)
    setMapPaint(null)
    setPlmResult(null)
  }, [])

  const resetResults = useCallback(() => {
    clearResults()
    setWtPdb(null)
    setMutPdb(null)
  }, [clearResults])

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
        setMapResult(await api.result(jobId) as unknown as ScanMapResult)
        setMapPaint(null)
        setResultJob({ id: jobId, kind })
      } else if (kind === 'plm_screen') {
        setPlmResult(await api.result(jobId) as unknown as PlmScreenResult)
        setMapPaint(null)
        setResultJob({ id: jobId, kind })
      }
      setWtPdb(await api.pdb(jobId, 'wt.pdb'))
    } catch { /* файлы могут отсутствовать для прогонов только-WT */ }
  }, [])

  const runPredict = useCallback(() => {
    clearResults()
    job.run(() => api.submitPredict(seq, profile === 'auto' ? undefined : profile))
  }, [clearResults, job, seq, profile])

  const runMutate = useCallback(() => {
    clearResults()
    job.run(() => api.submitMutate(seq, position, mutantAA, profile === 'auto' ? undefined : profile))
  }, [clearResults, job, seq, position, mutantAA, profile])

  const runScan = useCallback(() => {
    clearResults()
    job.run(() => api.submitScan(seq, position, profile === 'auto' ? undefined : profile))
  }, [clearResults, job, seq, position, profile])

  const runEnsemble = useCallback(() => {
    clearResults()
    const mode = dialExhaustive ? 'exhaustive' as const : 'sampled' as const
    job.run(() => api.submitEnsemble(
      seq, position, mode,
      dialExhaustive ? 1 : dialMu,
      dialTau,
      dialExhaustive ? 19 : dialK,
      dialSeed,
      profile === 'auto' ? undefined : profile,
    ))
  }, [clearResults, job, seq, position, dialExhaustive, dialMu, dialTau, dialK, dialSeed, profile])

  // карта чувствительности: 19 фолдов на позицию в [mapFrom..mapTo]; результат
  // только с данными (без PDB мутантов), структура WT приходит из той же задачи
  // 敏感性图谱：[mapFrom..mapTo] 内每个位置 19 次折叠；结果仅含数据
  //（无突变体 PDB），WT 结构取自同一任务
  const runMap = useCallback(() => {
    clearResults()
    const positions = Array.from(
      { length: Math.max(0, mapTo - mapFrom + 1) },
      (_, i) => mapFrom + i,
    )
    job.run(() => api.submitScanMap(seq, positions, profile === 'auto' ? undefined : profile))
  }, [clearResults, job, seq, mapFrom, mapTo, profile])

  // PLM-скрин: все 19×L замен из одного форварда; fold_top_k=0 — PLM-only
  // PLM 筛查：一次前向得到全部 19×L 替换；fold_top_k=0 为仅 PLM
  const runPlm = useCallback(() => {
    clearResults()
    job.run(() => api.submitPlmScreen(seq, plmTopK, profile === 'auto' ? undefined : profile))
  }, [clearResults, job, seq, plmTopK, profile])

  // опрос завершения: по готовности забираем артефакты, обновляем историю
  // 完成轮询：完成后取工件，刷新历史
  useEffect(() => {
    const st = jobStatus?.status
    if (st === 'done') {
      void afterDone(jobStatus!.job_id, jobStatus!.kind)
    }
    if (st === 'done' || st === 'error' || st === 'cancelled') loadHistory()
  }, [jobStatus?.status, jobStatus?.job_id, jobStatus?.kind]) // eslint-disable-line react-hooks/exhaustive-deps

  // показываем оверлей мутанта скана во вьюере (scan_<AA>.pdb выровнен по Kabsch)
  // 在查看器中显示扫描突变体的叠加（scan_<AA>.pdb 已按 Kabsch 对齐）
  // resultJob покрывает и восстановленные задачи (job.status знает только текущий прогон)
  // resultJob 也覆盖恢复的任务（job.status 只知道当前运行）
  const pickScanRow = useCallback(async (mutAA: string) => {
    const jobId = resultJob?.id ?? jobStatus?.job_id
    if (!jobId) return
    try {
      setMutPdb(await api.pdb(jobId, `scan_${mutAA}.pdb`))
      setPosition(scanResult?.position ?? position)
    } catch { /* артефакт мог исчезнуть */ }
  }, [resultJob, jobStatus?.job_id, scanResult?.position, position])

  // показываем оверлей варианта ансамбля во вьюере (ens_XX.pdb, выровнен к WT)
  // 在查看器中显示 ensemble 变体的叠加（ens_XX.pdb，已对齐到 WT）
  const pickEnsembleRow = useCallback(async (i: number) => {
    const jobId = resultJob?.id ?? jobStatus?.job_id
    const res = ensembleResult
    const row = res?.variants[i]
    if (!jobId || !row) return
    try {
      setMutPdb(await api.pdb(jobId, row.pdb_file as `ens_${string}.pdb`))
      setPickedEnsIdx(i)
      setPosition(res!.position)
    } catch { /* artifact may be gone */ }
  }, [resultJob, jobStatus?.job_id, ensembleResult])

  // восстановление прошлой задачи: последовательность + мутация обратно в поля,
  // артефакты во вьюер; сразу уводим на страницу, где живёт этот результат
  // 恢复历史任务：序列 + 突变回填到输入框，工件放回查看器；
  // 并立即跳转到该结果所在的页面
  const restore = useCallback(async (j: JobSummary) => {
    navigate(KIND_ROUTE[j.kind] ?? '/history')
    if (j.sequence) setInput(j.sequence)
    if (j.position) setPosition(j.position)
    if (j.mutant_aa) setMutantAA(j.mutant_aa)
    clearResults()
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
        // ручка читает обратно конфигурацию, породившую этот ансамбль;
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
        setMapResult(await api.result(j.job_id) as unknown as ScanMapResult)
        setResultJob({ id: j.job_id, kind: j.kind })
      } else if (j.kind === 'plm_screen') {
        setPlmResult(await api.result(j.job_id) as unknown as PlmScreenResult)
        if (j.fold_top_k != null) setPlmTopK(j.fold_top_k)
        setResultJob({ id: j.job_id, kind: j.kind })
      }
      setWtPdb(await api.pdb(j.job_id, 'wt.pdb'))
    } catch { /* артефакты могли исчезнуть */ }
  }, [navigate, clearResults])

  // смена языка → тексты бэкенда (сводка) приходят на новом языке
  // 切换语言 → 后端文本（摘要）以新语言重新获取
  useEffect(() => {
    if (!resultJob) return
    const kind = resultJob.kind
    if (kind !== 'mutate' && kind !== 'scan' && kind !== 'ensemble' && kind !== 'scan_map' && kind !== 'plm_screen') return
    let live = true
    api.result(resultJob.id).then((res) => {
      if (!live) return
      if (kind === 'mutate') {
        setResult(res as unknown as MutationResult)
      } else if (kind === 'scan') {
        setScanResult(res as unknown as ScanResult)
      } else if (kind === 'ensemble') {
        setEnsembleResult(res as unknown as EnsembleResult)
      } else if (kind === 'plm_screen') {
        setPlmResult(res as unknown as PlmScreenResult)
      } else {
        setMapResult(res as unknown as ScanMapResult)
      }
    }).catch(() => { /* артефакты задачи могли исчезнуть */ })
    return () => { live = false }
  }, [lang]) // eslint-disable-line react-hooks/exhaustive-deps -- resultJob читается, а не триггер

  // значение пересобирается на каждый рендер намеренно: состояние провайдера
  // меняется часто (поллинг 700 мс), мемоизация не дала бы выигрыша
  // 有意在每次渲染时重建 value：Provider 状态变化频繁（700ms 轮询），
  // 记忆化没有收益
  const value: WorkspaceCtx = {
    input, setInput, seq, seqOk, canRun, position, setPosition, mutantAA, setMutantAA,
    presets, applyPreset,
    profile, setProfile, gpu,
    result, scanResult, ensembleResult, pickedEnsIdx, mapResult, plmResult,
    plmTopK, setPlmTopK,
    mapFrom, mapTo,
    setMapRange: (from, to) => { setMapFrom(from); setMapTo(Math.max(from, to)) },
    mapPaint, setMapPaint, wtPdb, mutPdb, resultJob,
    activeJobId: resultJob?.id ?? jobStatus?.job_id ?? null,
    dialExhaustive, setDialExhaustive, dialMu, setDialMu, dialTau, setDialTau,
    dialK, setDialK, dialSeed, setDialSeed,
    jobStatus, jobRunning, jobError, cancelJob: job.cancel,
    runPredict, runMutate, runScan, runEnsemble, runMap, runPlm, resetResults,
    history, refreshHistory: loadHistory, restore,
    pickScanRow: (aa) => void pickScanRow(aa),
    pickEnsembleRow: (i) => void pickEnsembleRow(i),
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
