// BenchmarksPage: inference latency vs length (log-y, IQR bands) + kernel bench bars.
// Plotly is loaded lazily via React.lazy to keep the first paint fast.
import { Suspense, lazy, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { BenchmarkRow, KernelRow } from '../lib/types'

const Plot = lazy(() => import('../components/PlotlyChart'))

const PROFILES = ['fp32-gpu', 'fp16-gpu', 'cpu', 'dummy']

export default function BenchmarksPage() {
  const [seq] = useState('MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG')
  const [repeats, setRepeats] = useState(5)
  const [rows, setRows] = useState<BenchmarkRow[]>([])
  const [kernelRows, setKernelRows] = useState<KernelRow[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [kPairs, setKPairs] = useState(1024)
  const [kAtoms, setKAtoms] = useState(512)

  const runInference = async () => {
    setBusy(true); setErr(null)
    try {
      const { job_id } = await api.submitBenchmark(seq, PROFILES, repeats)
      // poll
      for (;;) {
        const s = await api.job(job_id)
        if (s.status === 'done') break
        if (s.status === 'error') throw new Error(s.error ?? 'benchmark failed')
        await new Promise((r) => setTimeout(r, 1000))
      }
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
      for (;;) {
        const s = await api.job(job_id)
        if (s.status === 'done') break
        if (s.status === 'error') throw new Error(s.error ?? 'kernel bench failed')
        await new Promise((r) => setTimeout(r, 1000))
      }
      const res = await api.result(job_id)
      setKernelRows((res as { rows: KernelRow[] }).rows ?? [])
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { /* rows render when set */ }, [rows, kernelRows])

  return (
    <div className="space-y-6">
      {err && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300">{err}</div>
      )}

      <div className="panel space-y-4 p-4">
        <h2 className="text-sm font-medium text-slate-200">Инференс: CPU vs GPU</h2>
        <div className="flex flex-wrap items-end gap-3 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-slate-500">repeats (2 warmup отбрасываются)</span>
            <input type="number" min={3} max={20} value={repeats}
              onChange={(e) => setRepeats(parseInt(e.target.value, 10) || 5)}
              className="mono w-24 rounded-lg border border-slate-800 bg-[#0b0f14] px-3 py-2 outline-none focus:border-cyan-700" />
          </label>
          <button onClick={runInference} disabled={busy || seq.length < 10}
            className="rounded-lg bg-cyan-700 px-4 py-2 font-medium text-white transition hover:bg-cyan-600 disabled:opacity-40">
            {busy ? 'Считаю…' : 'Запустить бенчмарк'}
          </button>
        </div>
        {rows.length > 0 && <InferenceChart rows={rows} />}
      </div>

      <div className="panel space-y-4 p-4">
        <h2 className="text-sm font-medium text-slate-200">Kabsch-ядро: numpy vs C++ vs CUDA</h2>
        <div className="flex flex-wrap items-end gap-3 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-slate-500">пар (B)</span>
            <input type="number" min={1} max={65536} value={kPairs}
              onChange={(e) => setKPairs(parseInt(e.target.value, 10) || 1024)}
              className="mono w-28 rounded-lg border border-slate-800 bg-[#0b0f14] px-3 py-2 outline-none focus:border-cyan-700" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-slate-500">атомов (N)</span>
            <input type="number" min={2} max={10000} value={kAtoms}
              onChange={(e) => setKAtoms(parseInt(e.target.value, 10) || 512)}
              className="mono w-28 rounded-lg border border-slate-800 bg-[#0b0f14] px-3 py-2 outline-none focus:border-cyan-700" />
          </label>
          <button onClick={runKernels} disabled={busy}
            className="rounded-lg border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 disabled:opacity-40">
            Прогнать ядро
          </button>
        </div>
        {kernelRows.length > 0 && <KernelChart rows={kernelRows} />}
      </div>
    </div>
  )
}

function InferenceChart({ rows }: { rows: BenchmarkRow[] }) {
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
    }
  })
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 60 },
    paper_bgcolor: '#0f151d', plot_bgcolor: '#0f151d',
    font: { color: '#9fb0c0', size: 11 },
    xaxis: { title: { text: 'длина (aa)' }, gridcolor: '#1c2733' },
    yaxis: { title: { text: 'latency, с (median±IQR/2)' }, type: 'log' as const, gridcolor: '#1c2733' },
    legend: { orientation: 'h' as const },
  }
  return (
    <Suspense fallback={<div className="text-xs text-slate-600">график загружается…</div>}>
      <Plot data={data} layout={layout} />
    </Suspense>
  )
}

function KernelChart({ rows }: { rows: KernelRow[] }) {
  const data = [{
    x: rows.map((r) => r.engine),
    y: rows.map((r) => r.wall_median_s * 1000),
    error_y: { type: 'data' as const, array: rows.map((r) => (r.wall_iqr_s / 2) * 1000), visible: true },
    type: 'bar' as const,
    marker: { color: rows.map((_, i) => COLORS[i % COLORS.length]) },
  }]
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 60 },
    paper_bgcolor: '#0f151d', plot_bgcolor: '#0f151d',
    font: { color: '#9fb0c0', size: 11 },
    yaxis: { title: { text: 'мс (median±IQR/2)' }, gridcolor: '#1c2733' },
  }
  const info = rows[0] ? `${rows[0].pairs} пар × ${rows[0].atoms} атомов` : ''
  return (
    <Suspense fallback={<div className="text-xs text-slate-600">график загружается…</div>}>
      <div className="text-xs text-slate-500">{info}</div>
      <Plot data={data} layout={layout} />
    </Suspense>
  )
}

const COLORS = ['#22d3ee', '#a78bfa', '#f59e0b', '#34d399', '#f472b6']