// ValidationPage: DMS-валидация против ProteinGym — assay → последовательность
// → один PLM forward + ограниченный фолд-план → pre-registered корреляции.
// ValidationPage：DMS 对 ProteinGym 的验证——数据集 → 序列 → 一次 PLM 前向
// + 受限折叠计划 → 预登记相关性。
import { Suspense, lazy, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useJob } from '../lib/useJob'
import { useI18n, renderBold, type Key, type TFn } from '../i18n'
import { PALETTE, useTheme, type ChartColors } from '../state/theme'
import type {
  AssayInfo, DmsCorrelation, DmsPoint, DmsValidationResult, InferenceProfile,
} from '../lib/types'
import SequenceInput, { stripFasta } from '../components/SequenceInput'
import Modal from '../components/Modal'

const Plot = lazy(() => import('../components/PlotlyChart'))

const LIMITS = { min: 10, max: 600 }

// серая шкала + один красный; чёрный закреплён за zero-shot заголовком.
// значения берутся из палитры темы (state/theme.tsx) — ниже они встречаются
// как C.ink / C.gray / C.accent
// 灰阶 + 一抹红；黑色留给 zero-shot 主结果。取值来自主题调色板
//（state/theme.tsx）——下方使用 C.ink / C.gray / C.accent。

const PROFILES: InferenceProfile[] = ['auto', 'fp32-gpu', 'fp16-gpu', 'cpu', 'dummy']
const PROFILE_LABEL: Record<InferenceProfile, Key> = {
  auto: 'run.auto',
  'fp32-gpu': 'run.profile.fp32',
  'fp16-gpu': 'run.profile.fp16',
  cpu: 'run.profile.cpu',
  dummy: 'run.dummy',
}

function fmtRho(rho: number | null | undefined): string {
  if (rho === null || rho === undefined || Number.isNaN(rho)) return '—'
  return `${rho >= 0 ? '+' : '−'}${Math.abs(rho).toFixed(2)}`
}

function fmtCi(ci: [number, number] | null): string {
  return ci ? `[${ci[0].toFixed(2)}, ${ci[1].toFixed(2)}]` : '—'
}

export default function ValidationPage() {
  const { t, tl, lang } = useI18n()
  const { theme } = useTheme()
  const C = PALETTE[theme]
  const [input, setInput] = useState('')
  const [assays, setAssays] = useState<AssayInfo[] | null>(null)
  const [assayId, setAssayId] = useState('')
  const [sampleN, setSampleN] = useState(48)
  const [foldPosMax, setFoldPosMax] = useState(40)
  const [seed, setSeed] = useState(0)
  const [profile, setProfile] = useState<InferenceProfile>('auto')
  const [jobId, setJobId] = useState<string | null>(null)
  const [valResult, setValResult] = useState<DmsValidationResult | null>(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const job = useJob()

  const seq = stripFasta(input)
  const seqOk = seq.length >= LIMITS.min && seq.length <= LIMITS.max &&
    /^[ACDEFGHIKLMNPQRSTVWY]+$/.test(seq)
  const assay = assays?.find((a) => a.dms_id === assayId) ?? null
  const canRun = seqOk && !!assay && assay.ok && !job.running

  // инвентарь кюрируемых наборов — чистый file I/O бэкенда
  // 已策展数据集清单——后端纯文件 I/O
  useEffect(() => {
    api.assays()
      .then((r) => {
        setAssays(r.assays)
        const ok = r.assays.find((a) => a.ok)
        if (ok) setAssayId((cur) => cur || ok.dms_id)
      })
      .catch(() => setAssays([]))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- инвентарь читается один раз

  const runVal = () => {
    setValResult(null)
    setJobId(null)
    job.run(() => api.validateDms(
      seq, assayId, sampleN, foldPosMax, seed,
      profile === 'auto' ? undefined : profile,
    ))
  }

  // done → результат той же задачи (summary — бэкенд-текст активного языка)
  // done → 取同任务结果（summary 为后端按当前语言生成的文本）
  useEffect(() => {
    const st = job.status?.status
    const id = job.status?.job_id
    if (st === 'done' && id) {
      setJobId(id)
      api.result(id)
        .then((res) => setValResult(res as unknown as DmsValidationResult))
        .catch(() => { /* артефакт мог исчезнуть */ })
    }
  }, [job.status?.status, job.status?.job_id]) // eslint-disable-line react-hooks/exhaustive-deps

  // смена языка → сводка приходит на новом языке; корреляции/имена статичны
  // 切换语言 → 重新获取摘要；相关名称为后端静态键
  useEffect(() => {
    if (!jobId) return
    let live = true
    api.result(jobId)
      .then((res) => { if (live) setValResult(res as unknown as DmsValidationResult) })
      .catch(() => { /* артефакт задачи мог исчезнуть */ })
    return () => { live = false }
  }, [lang, jobId]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="grid gap-5 lg:grid-cols-[400px_1fr]">
      <div className="panel space-y-5 p-4">
        <SequenceInput
          value={input}
          onChange={(s) => { setInput(s); setValResult(null) }}
          presets={[]}
          minLen={LIMITS.min}
          maxLen={LIMITS.max}
        />

        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label htmlFor="val-assay" className="text-sm font-medium text-neutral-900">
              {t('val.assay')}
            </label>
            <button
              onClick={() => setHelpOpen(true)}
              className="border border-neutral-300 px-2 py-0.5 text-xs text-neutral-500 transition hover:border-neutral-900 hover:text-neutral-900"
            >
              {t('res.help.q')}
            </button>
          </div>
          <select
            id="val-assay"
            data-demo="val-assay"
            value={assayId}
            onChange={(e) => setAssayId(e.target.value)}
            className="mono w-full border border-neutral-300 bg-white px-3 py-2 text-xs text-neutral-900 outline-none focus:border-neutral-900"
          >
            <option value="" disabled>—</option>
            {(assays ?? []).map((a) => (
              <option key={a.dms_id} value={a.dms_id} disabled={!a.ok}
                title={a.ok ? undefined : t('val.assayMissing')}>
                {a.dms_id}{a.ok ? '' : ` ⚠ ${t('val.assayMissing')}`}
              </option>
            ))}
          </select>
          {assay && (
            <div className="text-xs text-neutral-500">
              {t('val.assayMeta', {
                len: assay.seq_len, singles: assay.singles, positions: assay.positions,
              })}
            </div>
          )}
          {assays !== null && assays.length === 0 && (
            <div className="border border-neutral-300 bg-neutral-50 px-3 py-2 text-xs text-neutral-700">
              {t('val.assayEmpty')}
            </div>
          )}
          {assay && !assay.ok && (
            <div className="border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
              {t('val.assayMissing')}
            </div>
          )}
        </div>

        {/* фолд-план ограничен по construction: оба нуля = PLM-only (без wt.pdb) */}
        {/* 折叠计划由构造限制：两者都为 0 = 仅 PLM（无 wt.pdb） */}
        <div className="flex flex-wrap gap-3 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-neutral-500">{t('val.sampleN')}</span>
            <input type="number" min={0} max={256} value={sampleN}
              onChange={(e) => setSampleN(Math.min(256, Math.max(0, parseInt(e.target.value, 10) || 0)))}
              className="mono w-20 border border-neutral-300 bg-white px-2 py-1.5 text-neutral-900 outline-none focus:border-neutral-900" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-neutral-500">{t('val.foldPosMax')}</span>
            <input type="number" min={0} max={400} value={foldPosMax}
              onChange={(e) => setFoldPosMax(Math.min(400, Math.max(0, parseInt(e.target.value, 10) || 0)))}
              className="mono w-20 border border-neutral-300 bg-white px-2 py-1.5 text-neutral-900 outline-none focus:border-neutral-900" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-neutral-500">{t('val.seed')}</span>
            <input type="number" min={0} max={99999} value={seed}
              onChange={(e) => setSeed(Math.min(99999, Math.max(0, parseInt(e.target.value, 10) || 0)))}
              className="mono w-20 border border-neutral-300 bg-white px-2 py-1.5 text-neutral-900 outline-none focus:border-neutral-900" />
          </label>
        </div>

        <label className="space-y-1">
          <span className="text-xs text-neutral-500">{t('run.profile')}</span>
          <select
            value={profile}
            onChange={(e) => setProfile(e.target.value as InferenceProfile)}
            className="mono block w-full border border-neutral-300 bg-white px-3 py-2 text-xs text-neutral-900 outline-none focus:border-neutral-900"
          >
            {PROFILES.map((p) => (
              <option key={p} value={p}>{t(PROFILE_LABEL[p])}</option>
            ))}
          </select>
        </label>

        <button
          data-demo="val-run"
          onClick={runVal}
          disabled={!canRun}
          className="w-full bg-neutral-900 px-4 py-2 font-medium text-white transition hover:bg-neutral-700 disabled:opacity-40"
        >
          {job.running ? t('val.running') : t('val.run')}
        </button>

        {job.status && job.status.status !== 'done' && job.status.status !== 'error'
          && job.status.status !== 'cancelled' && (
          <div className="text-xs text-neutral-500">
            {job.status.message ?? '…'} {(job.status.progress * 100).toFixed(0)}%
          </div>
        )}
        {job.error && (
          <div className="border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
            {job.error}
          </div>
        )}
      </div>

      <div className="space-y-5">
        {assays !== null && assays.length > 0 && assays.every((a) => !a.ok) && !valResult && (
          <div className="border border-red-300 bg-red-50 p-4 text-xs text-red-800">
            {t('val.assayMissing')}
          </div>
        )}
        {valResult && (
          <>
            <div className="panel space-y-2 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-sm font-medium text-neutral-900">{t('val.title')}</h2>
                <span className="mono text-xs text-neutral-500">
                  {valResult.assay_id} · {valResult.mapping} · {valResult.plm_scorer}
                </span>
              </div>
              <p className="text-sm text-neutral-800">{valResult.summary}</p>
              <div className="text-xs text-neutral-500">
                {t('val.counts', {
                  mapped: valResult.n_rows, total: valResult.counts.rows_total ?? 0,
                  dups: valResult.counts.rows_dup_merged ?? 0,
                  multi: valResult.counts.rows_multi ?? 0,
                })}
              </div>
              {jobId && (
                <div className="mono text-xs text-neutral-500">
                  <a className="underline hover:text-neutral-900"
                    href={`/api/v1/files/${jobId}/dms_validation.csv`}>dms_validation.csv</a>
                  {' · '}
                  <a className="underline hover:text-neutral-900"
                    href={`/api/v1/files/${jobId}/dms_validation.json`}>dms_validation.json</a>
                </div>
              )}
            </div>

            <div className="panel space-y-3 p-4">
              <h3 className="text-sm font-medium text-neutral-900">{t('val.corr.title')}</h3>
              <CorrTable correlations={valResult.correlations} />
            </div>

            <div className="panel space-y-3 p-4" data-demo="val-scatter">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-xs font-medium text-neutral-900">{t('val.scatterPLM')}</h3>
                  <Suspense
                    fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}
                  >
                    <Plot
                      data={scatterData(valResult.scatter_plm, C.ink)}
                      layout={scatterLayout(t('val.xMargin'), t('val.yFitness'), C)}
                    />
                  </Suspense>
                </div>
                <div>
                  <h3 className="mb-2 text-xs font-medium text-neutral-900">{t('val.scatterStruct')}</h3>
                  <Suspense
                    fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}
                  >
                    {valResult.scatter_struct.length > 0
                      ? (
                        <Plot
                          data={scatterData(valResult.scatter_struct, C.accent)}
                          layout={scatterLayout(t('val.xRmsd'), t('val.yFitness'), C)}
                        />
                      )
                      : (
                        <div className="flex h-40 items-center justify-center border border-neutral-200 text-xs text-neutral-500">
                          {t('val.noFolds')}
                        </div>
                      )}
                  </Suspense>
                </div>
              </div>
            </div>

            <div className="panel space-y-3 p-4">
              <h3 className="text-xs font-medium text-neutral-900">{t('val.posStrip')}</h3>
              <Suspense
                fallback={<div className="text-xs text-neutral-400">{t('common.chartLoading')}</div>}
              >
                <Plot data={positionBars(valResult, C)} layout={positionBarsLayout(t, C)} />
              </Suspense>
            </div>

            <div className="panel space-y-2 p-4" data-demo="val-honesty">
              <h3 className="text-sm font-medium text-neutral-900">{t('val.honesty')}</h3>
              <ul className="list-disc space-y-1 pl-5 text-xs text-neutral-600">
                {valResult.caveats.map((c, i) => (
                  <li key={i}>{t(`val.caveat.${c.key}` as Key, c.params)}</li>
                ))}
              </ul>
            </div>
          </>
        )}
        {!valResult && (
          <div className="panel p-4 text-xs text-neutral-500">{t('val.aboutAssay')}</div>
        )}
      </div>

      {helpOpen && (
        <Modal title={t('val.helpTitle')} onClose={() => setHelpOpen(false)} wide>
          <div className="space-y-3 text-sm text-neutral-800">
            {tl('help.validation').map((p, i) => (
              <p key={i}>{renderBold(p)}</p>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}

function CorrTable({ correlations }: { correlations: DmsCorrelation[] }) {
  const { t } = useI18n()
  return (
    <table className="w-full text-xs" data-demo="val-table">
      <thead>
        <tr className="border-b border-neutral-200 text-left text-neutral-500">
          <th className="py-1.5 pr-3 font-normal"> </th>
          <th className="py-1.5 pr-3 text-right font-normal">{t('val.corr.rho')}</th>
          <th className="py-1.5 pr-3 text-right font-normal">{t('val.corr.n')}</th>
          <th className="py-1.5 pr-3 text-right font-normal">{t('val.corr.ci')}</th>
          <th className="py-1.5 text-right font-normal">{t('val.corr.expect')}</th>
        </tr>
      </thead>
      <tbody>
        {correlations.map((c) => {
          const flat = c.spearman === null || c.spearman === undefined
          const positive = c.expected_sign === '+'
          const match = flat
            ? null
            : positive ? (c.spearman as number) >= 0 : (c.spearman as number) <= 0
          return (
            <tr key={c.name} className="border-b border-neutral-100">
              <td className="py-1.5 pr-3 text-neutral-900">{t(`val.corr.${c.name}` as Key)}</td>
              <td className="mono py-1.5 pr-3 text-right text-neutral-900">{fmtRho(c.spearman)}</td>
              <td className="mono py-1.5 pr-3 text-right text-neutral-500">{c.n}</td>
              <td className="mono py-1.5 pr-3 text-right text-neutral-500">{fmtCi(c.ci)}</td>
              <td
                className={`py-1.5 text-right ${
                  flat ? 'text-neutral-400' : match ? 'text-neutral-900' : 'text-red-700'
                }`}
                title={
                  flat ? t('val.corr.flat')
                    : match ? t('val.corr.matchTrue') : t('val.corr.matchFalse')
                }
              >
                {flat ? '—' : match ? '✓' : '✗'}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function scatterData(pts: DmsPoint[], color: string) {
  return [{
    x: pts.map((p) => p.x),
    y: pts.map((p) => p.y),
    text: pts.map((p) => p.label),
    hoverinfo: 'x+y+text',
    type: 'scatter' as const,
    mode: 'markers' as const,
    marker: { size: 5, color },
  }]
}

function scatterLayout(xTitle: string, yTitle: string, C: ChartColors) {
  return {
    margin: { t: 10, r: 10, b: 40, l: 55 },
    paper_bgcolor: C.paper, plot_bgcolor: C.paper,
    font: { color: C.muted, size: 11 },
    xaxis: { title: { text: xTitle }, gridcolor: C.grid, linecolor: C.border },
    yaxis: { title: { text: yTitle }, gridcolor: C.grid, linecolor: C.border },
    showlegend: false,
  }
}

// два ряда на одной оси позиций: экспериментальный fitness (серый, левая ось)
// и PLM-перцентиль хрупкости (красный, правая 0..1) — шкалы несопоставимы
// 同一位置轴上两组柱：实验 fitness（灰，左轴）与 PLM 脆弱性百分位（红，右轴 0..1）——量纲不同
function positionBars(r: DmsValidationResult, C: ChartColors) {
  const pp = r.per_position
  return [
    {
      x: pp.map((p) => p.pos),
      y: pp.map((p) => p.mean_fitness_z),
      name: 'fitness',
      type: 'bar' as const,
      marker: { color: C.gray },
    },
    {
      x: pp.map((p) => p.pos),
      y: pp.map((p) => p.v_med_pctl),
      name: 'PLM',
      type: 'bar' as const,
      yaxis: 'y2' as const,
      marker: { color: C.accent },
    },
  ]
}

function positionBarsLayout(t: TFn, C: ChartColors) {
  return {
    margin: { t: 10, r: 55, b: 30, l: 55 },
    paper_bgcolor: C.paper, plot_bgcolor: C.paper,
    font: { color: C.muted, size: 11 },
    barmode: 'group' as const,
    xaxis: { title: { text: t('res.xaxis.residue') }, gridcolor: C.grid, linecolor: C.border },
    yaxis: { title: { text: t('val.fitness') }, gridcolor: C.grid, linecolor: C.border },
    yaxis2: {
      overlaying: 'y' as const, side: 'right' as const, range: [0, 1] as [number, number],
      title: { text: t('val.pctl') }, showgrid: false, zeroline: false,
    },
    legend: { orientation: 'h' as const },
  }
}