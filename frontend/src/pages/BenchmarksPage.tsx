// BenchmarksPage: латентность инференса против длины (log-y, полосы IQR) + столбцы бенча ядер.
// Plotly загружается лениво через React.lazy, чтобы первый рендер оставался быстрым.
// BenchmarksPage：推理延迟 vs 长度（log-y，IQR 区间）+ 核心基准条形图。
// Plotly 经 React.lazy 懒加载，保持首屏渲染迅速。
import { Suspense, lazy, useState } from 'react'
import { api } from '../lib/api'
import type { BenchmarkRow, KernelRow } from '../lib/types'
import { useI18n } from '../i18n'

const Plot = lazy(() => import('../components/PlotlyChart'))

const PROFILES = ['fp32-gpu', 'fp16-gpu', 'cpu', 'dummy']

// строгие серые + один красный; чёрный закреплён за основной серией
// 严格灰阶 + 一抹红；黑色留给主系列
const COLORS = ['#111111', '#6b7280', '#b91c1c', '#9ca3af', '#374151']

export default function BenchmarksPage() {
  const { t } = useI18n()
  const [seq] = useState('MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG')
  const [repeats, setRepeats] = useState(5)
  const [rows, setRows] = useState<BenchmarkRow[]>([])
  const [kernelRows, setKernelRows] = useState<KernelRow[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [kPairs, setKPairs] = useState(1024)
  const [kAtoms, setKAtoms] = useState(512)

  const poll = async (jobId: string) => {
    for (;;) {
      const s = await api.job(jobId)
      if (s.status === 'done') return
      if (s.status === 'error') throw new Error(s.error ?? t('run.jobFailed'))
      await new Promise((r) => setTimeout(r, 1000))
    }
  }

  const runInference = async () => {
    setBusy(true); setErr(null)
    try {
      const { job_id } = await api.submitBenchmark(seq, PROFILES, repeats)
      await poll(job_id)
      const res = await api.result(job_id)
      setRows((res as { rows: BenchmarkRow[] }).rows ?? [])
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runKernels = async () => {
    setBusy(true); setErr(null)
    try {
      const { job_id } = await api.submitKernelBench(kPairs, kAtoms)
      await poll(job_id)
      const res = await api.result(job_id)
      setKernelRows((res as { rows: KernelRow[] }).rows ?? [])
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      {err && (
        <div className="border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">{err}</div>
      )}

      <div className="panel space-y-4 p-4">
        <h2 className="text-sm font-medium text-neutral-900">{t('bench.inference')}</h2>
        <div className="flex flex-wrap items-end gap-3 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-neutral-500">{t('bench.repeats')}</span>
            <input type="number" min={3} max={20} value={repeats}
              onChange={(e) => setRepeats(parseInt(e.target.value, 10) || 5)}
              className="mono w-24 border border-neutral-300 bg-white px-3 py-2 text-neutral-900 outline-none focus:border-neutral-900" />
          </label>
          <button onClick={runInference} disabled={busy || seq.length < 10}
            className="bg-neutral-900 px-4 py-2 font-medium text-white transition hover:bg-neutral-700 disabled:opacity-40">
            {busy ? t('bench.busy') : t('bench.runBenchmark')}
          </button>
        </div>
        {rows.length > 0 && <InferenceChart rows={rows} />}
      </div>

      <div className="panel space-y-4 p-4">
        <h2 className="text-sm font-medium text-neutral-900">{t('bench.kernels')}</h2>
        <div className="flex flex-wrap items-end gap-3 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-neutral-500">{t('bench.pairs')}</span>
            <input type="number" min={1} max={65536} value={kPairs}
              onChange={(e) => setKPairs(parseInt(e.target.value, 10) || 1024)}
              className="mono w-28 border border-neutral-300 bg-white px-3 py-2 text-neutral-900 outline-none focus:border-neutral-900" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-neutral-500">{t('bench.atoms')}</span>
            <input type="number" min={2} max={10000} value={kAtoms}
              onChange={(e) => setKAtoms(parseInt(e.target.value, 10) || 512)}
              className="mono w-28 border border-neutral-300 bg-white px-3 py-2 text-neutral-900 outline-none focus:border-neutral-900" />
          </label>
          <button onClick={runKernels} disabled={busy}
            className="border border-neutral-300 px-4 py-2 text-neutral-800 transition hover:border-neutral-900 disabled:opacity-40">
            {t('bench.runKernel')}
          </button>
        </div>
        {kernelRows.length > 0 && <KernelChart rows={kernelRows} />}
      </div>
    </div>
  )
}

function InferenceChart({ rows }: { rows: BenchmarkRow[] }) {
  const { t } = useI18n()
  const profiles = [...new Set(rows.map((r) => r.profile))]
  const data = profiles.map((p, i) => {
    const rr = rows.filter((r) => r.profile === p).sort((a, b) => a.length - b.length)
    return {
      x: rr.map((r) => r.length),
      y: rr.map((r) => r.wall_median_s),
      error_y: {
        type: 'data' as const,
        array: rr.map((r) => r.wall_iqr_s / 2),
        visible: true,
      },
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      name: p,
      line: { color: COLORS[i % COLORS.length] },
      marker: { color: COLORS[i % COLORS.length] },
    }
  })
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 60 },
    paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
    font: { color: '#525252', size: 11 },
    xaxis: { title: { text: t('bench.xaxis.length') }, gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
    yaxis: { title: { text: t('bench.yaxis.latency') }, type: 'log' as const, gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
    legend: { orientation: 'h' as const },
  }
  return (
    <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
      <Plot data={data} layout={layout} />
    </Suspense>
  )
}

function KernelChart({ rows }: { rows: KernelRow[] }) {
  const { t } = useI18n()
  const data = [{
    x: rows.map((r) => r.engine),
    y: rows.map((r) => r.wall_median_s * 1000),
    error_y: { type: 'data' as const, array: rows.map((r) => (r.wall_iqr_s / 2) * 1000), visible: true },
    type: 'bar' as const,
    marker: { color: rows.map((_, i) => COLORS[i % COLORS.length]) },
  }]
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 60 },
    paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
    font: { color: '#525252', size: 11 },
    yaxis: { title: { text: t('bench.yaxis.ms') }, gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
  }
  const info = rows[0] ? t('bench.kernelInfo', { pairs: rows[0].pairs, atoms: rows[0].atoms }) : ''
  return (
    <Suspense fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}>
      <div className="text-xs text-neutral-500">{info}</div>
      <Plot data={data} layout={layout} />
    </Suspense>
  )
}