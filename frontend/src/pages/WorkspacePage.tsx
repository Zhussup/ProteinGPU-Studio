// WorkspacePage: sequence → mutation → run → 3D overlay + RMSD cards + history.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useJob } from '../lib/useJob'
import { useI18n } from '../i18n'
import type {
  EnsembleResult, GpuInfo, InferenceProfile, JobSummary, MutationResult,
  Preset, ScanResult,
} from '../lib/types'
import SequenceInput, { stripFasta } from '../components/SequenceInput'
import MutationPicker from '../components/MutationPicker'
import MutagenesisDial from '../components/MutagenesisDial'
import RunPanel from '../components/RunPanel'
import ResultTabs from '../components/ResultTabs'
import ScanPanel from '../components/ScanPanel'
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
  // the mutagenesis dial (dum.md §2): μ = simultaneous substitutions, τ = the
  // Grantham spectrum temperature, K = ensemble size; exhaustive = all 19 subs
  const [dialExhaustive, setDialExhaustive] = useState(false)
  const [dialMu, setDialMu] = useState(1)
  const [dialTau, setDialTau] = useState(0.5)
  const [dialK, setDialK] = useState(20)
  const [dialSeed, setDialSeed] = useState<number | null>(null)
  const [wtPdb, setWtPdb] = useState<string | null>(null)
  const [mutPdb, setMutPdb] = useState<string | null>(null)
  const [history, setHistory] = useState<JobSummary[]>([])
  // the done job whose result/scan panel is shown — retranslated on lang switch
  const [resultJob, setResultJob] = useState<{ id: string; kind: string } | null>(null)
  const job = useJob()

  const loadHistory = useCallback(() => {
    api.jobs(20).then(setHistory).catch(() => {})
  }, [])

  useEffect(() => {
    api.presets().then((r) => setPresets(r.presets)).catch(() => {})
    api.gpu().then(setGpu).catch(() => {})
  }, [loadHistory, lang]) // refetch on language switch: preset texts are backend-side

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const seq = stripFasta(input)
  const seqOk = seq.length >= LIMITS.min && seq.length <= LIMITS.max && /^[ACDEFGHIKLMNPQRSTVWY]+$/.test(seq)
  const posOk = position >= 1 && position <= seq.length
  const canRun = seqOk && posOk

  // keep the mutation position valid when a shorter/longer sequence arrives
  useEffect(() => {
    if (seq.length >= 1 && position > seq.length) setPosition(seq.length)
    if (position < 1 && seq.length >= 1) setPosition(1)
  }, [seq.length, position])

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
      }
      setWtPdb(await api.pdb(jobId, 'wt.pdb'))
    } catch { /* files may be missing for predict-only runs */ }
  }, [])

  const runPredict = () => {
    setResult(null); setMutPdb(null); setScanResult(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    job.run(() => api.submitPredict(seq, profile === 'auto' ? undefined : profile))
  }

  const runMutate = () => {
    setResult(null); setScanResult(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    job.run(() => api.submitMutate(seq, position, mutantAA, profile === 'auto' ? undefined : profile))
  }

  const runScan = () => {
    setResult(null); setScanResult(null); setMutPdb(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
    job.run(() => api.submitScan(seq, position, profile === 'auto' ? undefined : profile))
  }

  const runEnsemble = () => {
    setResult(null); setScanResult(null); setMutPdb(null)
    setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
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

  // poll completion: fetch artifacts once done, refresh history
  useEffect(() => {
    const st = job.status?.status
    if (st === 'done') {
      void afterDone(job.status!.job_id, job.status!.kind)
    }
    if (st === 'done' || st === 'error') loadHistory()
  }, [job.status?.status, job.status?.job_id, job.status?.kind]) // eslint-disable-line react-hooks/exhaustive-deps

  // show a scan mutant's overlay in the viewer (scan_<AA>.pdb is Kabsch-aligned)
  const pickScanRow = useCallback(async (mutAA: string) => {
    const jobId = job.status?.job_id
    if (!jobId) return
    try {
      setMutPdb(await api.pdb(jobId, `scan_${mutAA}.pdb`))
      setPosition(scanResult?.position ?? position)
    } catch { /* artifact may be gone */ }
  }, [job.status?.job_id, scanResult?.position, position])

  // show an ensemble variant's overlay in the viewer (ens_XX.pdb, aligned to WT)
  const pickEnsembleRow = useCallback(async (i: number) => {
    // resultJob covers restored jobs too (job.status only knows the current run)
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

  // restore a past job: sequence + mutation back into inputs, artifacts into viewer
  const restore = useCallback(async (j: JobSummary) => {
    if (j.sequence) setInput(j.sequence)
    if (j.position) setPosition(j.position)
    if (j.mutant_aa) setMutantAA(j.mutant_aa)
    setResult(null)
    setMutPdb(null)
    setScanResult(null)
    setEnsembleResult(null)
    setPickedEnsIdx(null)
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
        // the dial reads back the configuration that produced this ensemble;
        // the seed needs no field — the derived seed reproduces from the config
        // (an explicit override is cleared, it would otherwise leak into reruns)
        if (j.mode) setDialExhaustive(j.mode === 'exhaustive')
        if (j.mu) setDialMu(j.mu)
        if (typeof j.tau === 'number') setDialTau(j.tau)
        if (j.k) setDialK(j.k)
        setDialSeed(null)
        setResultJob({ id: j.job_id, kind: j.kind })
      }
      setWtPdb(await api.pdb(j.job_id, 'wt.pdb'))
    } catch { /* artifacts may be gone */ }
  }, [])

  // language switch → backend texts (summary) arrive in the new language
  useEffect(() => {
    if (!resultJob) return
    const kind = resultJob.kind
    if (kind !== 'mutate' && kind !== 'scan' && kind !== 'ensemble') return
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
      } else {
        setEnsembleResult(res as unknown as EnsembleResult)
        setResult(null)
        setScanResult(null)
      }
    }).catch(() => { /* job artifacts may be gone */ })
    return () => { live = false }
  }, [lang]) // eslint-disable-line react-hooks/exhaustive-deps -- resultJob read, not a trigger

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
          onReset={() => {
            setResult(null); setWtPdb(null); setMutPdb(null); setScanResult(null)
            setEnsembleResult(null); setPickedEnsIdx(null); setResultJob(null)
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
        {scanResult ? (
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