// WorkspacePage: sequence → mutation → run → 3D overlay + RMSD cards + history.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useJob } from '../lib/useJob'
import type { GpuInfo, JobSummary, MutationResult, Preset } from '../lib/types'
import SequenceInput, { stripFasta } from '../components/SequenceInput'
import MutationPicker from '../components/MutationPicker'
import RunPanel from '../components/RunPanel'
import ResultTabs from '../components/ResultTabs'
import MoleculeViewer from '../components/MoleculeViewer'
import HistoryPanel from '../components/HistoryPanel'

const LIMITS = { min: 10, max: 600 }

export default function WorkspacePage() {
  const [input, setInput] = useState('')
  const [position, setPosition] = useState(44)
  const [mutantAA, setMutantAA] = useState('A')
  const [presets, setPresets] = useState<Preset[]>([])
  const [gpu, setGpu] = useState<GpuInfo | null>(null)
  const [result, setResult] = useState<MutationResult | null>(null)
  const [wtPdb, setWtPdb] = useState<string | null>(null)
  const [mutPdb, setMutPdb] = useState<string | null>(null)
  const [history, setHistory] = useState<JobSummary[]>([])
  const job = useJob()

  const loadHistory = useCallback(() => {
    api.jobs(20).then(setHistory).catch(() => {})
  }, [])

  useEffect(() => {
    api.presets().then((r) => setPresets(r.presets)).catch(() => {})
    api.gpu().then(setGpu).catch(() => {})
    loadHistory()
  }, [loadHistory])

  const seq = stripFasta(input)
  const seqOk = seq.length >= LIMITS.min && seq.length <= LIMITS.max && /^[ACDEFGHIKLMNPQRSTVWY]+$/.test(seq)
  const posOk = position >= 1 && position <= seq.length
  const canRun = seqOk && posOk

  const applyPreset = useCallback((p: Preset) => {
    setInput(`>${p.name}\n${p.sequence}`)
    if (p.position) setPosition(p.position)
    if (p.mutant_aa) setMutantAA(p.mutant_aa)
  }, [])

  const afterDone = useCallback(async (jobId: string, withMut: boolean) => {
    try {
      if (withMut) {
        setResult(await api.result(jobId) as unknown as MutationResult)
        setMutPdb(await api.pdb(jobId, 'mut_aligned.pdb'))
      }
      setWtPdb(await api.pdb(jobId, 'wt.pdb'))
    } catch { /* files may be missing for predict-only runs */ }
  }, [])

  const runPredict = () => {
    setResult(null); setMutPdb(null)
    job.run(() => api.submitPredict(seq))
  }

  const runMutate = () => {
    setResult(null)
    job.run(() => api.submitMutate(seq, position, mutantAA))
  }

  // poll completion: fetch artifacts once done, refresh history
  useEffect(() => {
    const st = job.status?.status
    if (st === 'done') {
      const kind = job.status!.kind
      void afterDone(job.status!.job_id, kind === 'mutate')
    }
    if (st === 'done' || st === 'error') loadHistory()
  }, [job.status?.status, job.status?.job_id, job.status?.kind]) // eslint-disable-line react-hooks/exhaustive-deps

  // restore a past job: sequence + mutation back into inputs, artifacts into viewer
  const restore = useCallback(async (j: JobSummary) => {
    if (j.sequence) setInput(j.sequence)
    if (j.position) setPosition(j.position)
    if (j.mutant_aa) setMutantAA(j.mutant_aa)
    setResult(null)
    setMutPdb(null)
    try {
      if (j.kind === 'mutate') {
        setResult(await api.result(j.job_id) as unknown as MutationResult)
        setMutPdb(await api.pdb(j.job_id, 'mut_aligned.pdb'))
      } else {
        setResult(null)
      }
      setWtPdb(await api.pdb(j.job_id, 'wt.pdb'))
    } catch { /* artifacts may be gone */ }
  }, [])

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
        <RunPanel
          canRun={canRun}
          running={!!job.running}
          status={job.status}
          error={job.error}
          gpu={gpu}
          onRunPredict={runPredict}
          onRunMutate={runMutate}
          onReset={() => { setResult(null); setWtPdb(null); setMutPdb(null) }}
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
        />
        {result?.rmsd ? (
          <div className="panel p-4">
            <h3 className="mb-3 text-sm font-medium text-neutral-900">Результат наложения</h3>
            <ResultTabs result={result} />
          </div>
        ) : (
          <div className="panel p-4 text-xs text-neutral-500">
            Global + local RMSD (±10 остатков), TM-score и pLDDT появятся после запуска «WT + мутант».
            Модель почти детерминирована: на стабильном фолде точечные мутации дают суб-Å сдвиги
            (на убиквитине: I44A 0.21 Å, I3L 0.28 Å, P19G 0.72 Å — наибольший отклик).
            Ориентируйтесь на сравнение локального RMSD между мутациями, а не на абсолютные пороги.
          </div>
        )}
      </div>
    </div>
  )
}