// SensitivityCompare: межпозиционная таблица по УЖЕ ВЫЧИСЛЕННЫМ ансамблям
// из истории (dum.md §5). Без автосканирования — только позиции, которые
// пользователь реально запускал. Композитная «чувствительность» нормируется
// перцентилями ВНУТРИ сравниваемого набора (у каждого окна свой шумовой пол
// модели, dum.md §6): сырые медианы лежат рядом, чтобы честные числа
// оставались видимыми.
// SensitivityCompare：跨位点表格，基于历史中已算好的 ensemble（dum.md §5）。
// 不做自动扫描——只覆盖用户实际运行过的位点。复合“敏感性”在比较集合内
// 按百分位归一化（每个窗口有自己的模型噪声底，dum.md §6）：
// 原始中位数并列显示，让诚实的数字保持可见。
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { EnsembleResult, JobSummary } from '../lib/types'
import { useI18n, type Key } from '../i18n'

interface Row {
  jobId: string
  position: number
  mu: number
  tau: number
  k: number
  mode: string
  medLocal: number
  medAbsDplddt: number
  width: string
  sensitivity: number // 0..1, перцентиль внутри сравниваемого набора | 0..1，比较集合内的百分位
}

const WIDTH_CLS: Record<string, string> = {
  narrow: 'border border-neutral-300 text-neutral-500',
  moderate: 'bg-neutral-600 text-white',
  wide: 'bg-red-700 text-white',
}
const WIDTH_KEYS: Record<string, Key> = {
  narrow: 'ens.width.narrow',
  moderate: 'ens.width.moderate',
  wide: 'ens.width.wide',
}

// ранг x внутри arr, 0..1 (доля значений строго меньших)
// x 在 arr 中的排名，0..1（严格小于的比例）
const rank = (x: number, arr: number[]): number => {
  const below = arr.filter((v) => v < x).length
  return arr.length > 1 ? below / (arr.length - 1) : 0.5
}

export default function SensitivityCompare({ jobs, wtSequence }: {
  jobs: JobSummary[]
  wtSequence: string
}) {
  const { t } = useI18n()
  const [rows, setRows] = useState<Row[] | null>(null)

  useEffect(() => {
    if (!wtSequence) { setRows(null); return }
    let cancelled = false
    const done = jobs.filter(
      (j) => j.kind === 'ensemble' && j.status === 'done' && j.sequence === wtSequence,
    )
    if (done.length < 2) { setRows(null); return }
    Promise.all(
      done.map(async (j): Promise<Row | null> => {
        try {
          const res = await api.result(j.job_id) as unknown as EnsembleResult
          if (!res.stats || !res.headline) return null
          return {
            jobId: j.job_id,
            position: res.position,
            mu: res.params.mu,
            tau: res.params.tau,
            k: res.params.k,
            mode: res.mode,
            medLocal: res.stats.local_rmsd.median,
            medAbsDplddt: res.headline.median_abs_dplddt_local,
            width: res.headline.width,
            sensitivity: 0, // присвоим, когда ранги известны | 等排名算出后再赋值
          }
        } catch { return null }
      }),
    ).then((rs) => {
      if (cancelled) return
      const good = rs.filter((r): r is Row => r !== null)
      if (good.length < 2) { setRows(null); return }
      const L = good.map((r) => r.medLocal)
      const D = good.map((r) => r.medAbsDplddt)
      for (const r of good) {
        r.sensitivity = (rank(r.medLocal, L) + rank(r.medAbsDplddt, D)) / 2
      }
      setRows(good.sort((a, b) => b.sensitivity - a.sensitivity))
    })
    return () => { cancelled = true }
  }, [jobs, wtSequence])

  if (!rows) return null

  return (
    <div className="panel p-4">
      <h3 className="mb-3 text-sm font-medium text-neutral-900">{t('sens.title')}</h3>
      <div className="border border-neutral-200 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-neutral-100 text-neutral-600">
            <tr>
              <th className="px-2 py-1.5 text-left">{t('sens.h.position')}</th>
              <th className="px-2 py-1.5 text-right">μ</th>
              <th className="px-2 py-1.5 text-right">τ</th>
              <th className="px-2 py-1.5 text-right">K</th>
              <th className="px-2 py-1.5 text-right">{t('sens.h.medLocal')}</th>
              <th className="px-2 py-1.5 text-right">{t('sens.h.medDplddt')}</th>
              <th className="px-2 py-1.5 text-right">{t('sens.h.sensitivity')}</th>
              <th className="px-2 py-1.5 text-center">{t('ens.width.label')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.jobId} className="border-t border-neutral-100">
                <td className="mono px-2 py-1.5 font-medium text-neutral-900">
                  {r.mode === 'exhaustive' ? `${r.position} ×19` : r.position}
                </td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.mu}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.tau.toFixed(2)}</td>
                <td className="mono px-2 py-1.5 text-right text-neutral-500">{r.k}</td>
                <td className="mono px-2 py-1.5 text-right">{r.medLocal.toFixed(2)} Å</td>
                <td className="mono px-2 py-1.5 text-right">{r.medAbsDplddt.toFixed(2)}</td>
                <td className="mono px-2 py-1.5 text-right font-medium text-neutral-900">
                  {(r.sensitivity * 100).toFixed(0)}%
                </td>
                <td className="px-2 py-1.5 text-center">
                  <span className={`mono px-1.5 py-0.5 text-[10px] ${WIDTH_CLS[r.width] ?? ''}`}>
                    {t(WIDTH_KEYS[r.width] ?? 'ens.width.moderate')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-1 text-[10px] text-neutral-400">{t('sens.note')}</div>
    </div>
  )
}