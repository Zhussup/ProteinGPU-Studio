// WorkspacePage: sequence → mutation → run → 3D overlay + RMSD cards.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useJob } from '../lib/useJob'
import type { GpuInfo, MutationResult, Preset } from '../lib/types'
import SequenceInput, { stripFasta } from '../components/SequenceInput'
import MutationPicker from '../components/MutationPicker'
import RunPanel from '../components/RunPanel'
import ResultTabs from '../components/ResultTabs'
import MoleculeViewer from '../components/MoleculeViewer'

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
  const job = useJob()

  useEffect(() => {
    api.presets().then((r) => setPresets(r.presets)).catch(() => {})
    api.gpu().then(setGpu).catch(() => {})
  }, [])

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
        setResult(await api.result(jobId) as MutationResult)
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

  // poll completion: fetch artifacts once done
  useEffect(() => {
    if (job.status?.status === 'done') {
      const kind = job.status.kind
      void afterDone(job.status.job_id, kind === 'mutate')
    }
  }, [job.status?.status, job.status?.job_id, job.status?.kind]) // eslint-disable-line react-hooks/exhaustive-deps

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
            <h3 className="mb-3 text-sm font-medium text-slate-300">Результат наложения</h3>
            <ResultTabs result={result} />
          </div>
        ) : (
          <div className="panel p-4 text-xs text-slate-600">
            Global + local RMSD (±10 остатков), TM-score и pLDDT появятся после запуска «WT + мутант».
            Глобальный RMSD двух независимых фолдингов может содержать шум модели — ориентируйтесь на
            локальный RMSD рядом с мутацией.
          </div>
        )}
      </div>
    </div>
  )
}