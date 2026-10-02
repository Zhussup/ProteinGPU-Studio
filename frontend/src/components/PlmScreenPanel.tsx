// PlmScreenPanel: скрин всего белка из одного PLM-прохода (zero-shot
// WT-margin). Тот же язык визуализации, что у карты чувствительности:
// тепловая карта (позиции × компас), роза выбранной позиции, ранжированная
// таблица, «раскрасить 3D». Отличие — канал pctl построен на plm_damage
// (−log margin), а структурные колонки есть только у сфолднутых top-K
// замен: для них показан блок согласия PLM ↔ структура.
// PlmScreenPanel：一次 PLM 前向的全蛋白筛查（zero-shot WT-margin）。
// 视觉语言与敏感性图谱相同：热图、选中位置玫瑰、排序表、3D 着色。
// 差别：pctl 通道基于 plm_damage（−log margin），只有折叠的 top-K 替换
// 才有结构列，并附 PLM ↔ 结构一致性块。
import { useMemo, useState } from 'react'
import type { PlmPosition, PlmScreenResult } from '../lib/types'
import { renderBold, useI18n, type Key } from '../i18n'
import RoseGlyph, { PETAL_DIRS, rank } from './RoseGlyph'
import PetalHeatmap, { type PetalRow } from './PetalHeatmap'
import Modal from './Modal'

// метрики окраски PLM-канала (в mapPaint их отделяем от scan_map-метрик)
// PLM 通道的着色指标（与 scan_map 指标在 mapPaint 中区分）
export type PlmPaintMetric = 'plm_v_max' | 'plm_v_med'

export interface PlmScreenPanelProps {
  result: PlmScreenResult
  jobId?: string | null
  paintedMetric: PlmPaintMetric | null
  onPaint: (scores: (number | null)[], metric: PlmPaintMetric) => void
  onClearPaint: () => void
}

function PctlBar({ v }: { v: number }) {
  return (
    <span className="inline-block h-1.5 w-14 align-middle bg-neutral-100">
      <span
        className="block h-full bg-neutral-900"
        style={{ width: `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%` }}
      />
    </span>
  )
}

export default function PlmScreenPanel({ result, jobId, paintedMetric, onPaint, onClearPaint }: PlmScreenPanelProps) {
  const { t, tl } = useI18n()
  const [metric, setMetric] = useState<'v_max' | 'v_med'>('v_max')
  const [helpOpen, setHelpOpen] = useState(false)
  const positions = result.positions
  const L = result.wt_sequence.length
  const dummy = result.plm_scorer === 'dummy-plm'

  const sorted = useMemo(() => {
    const key = metric === 'v_max' ? 'pctl_v_max' : 'pctl_v_med'
    return [...positions].sort((a, b) => b.stats[key] - a.stats[key])
  }, [positions, metric])

  const [selectedPos, setSelectedPos] = useState<number | null>(null)
  const selected: PlmPosition | undefined =
    positions.find((p) => p.pos === selectedPos) ?? sorted[0]

  const paint = () => {
    const key = metric === 'v_max' ? 'plm_v_max' : 'plm_v_med'
    const scores: (number | null)[] = new Array(L).fill(null)
    for (const p of positions) scores[p.pos - 1] = p.stats[key]
    onPaint(scores, key)
  }

  return (
    <div className="space-y-4">
      <div className="border-l-2 border-neutral-900 bg-neutral-50 p-3 text-sm text-neutral-800">
        {result.summary}
      </div>

      {/* метрика + раскраска 3D + артефакты датасета + честный бейдж скорера */}
      {/* 指标 + 3D 着色 + 数据集工件 + 诚实的评分器徽章 */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-neutral-500">{t('plm.metricLabel')}</span>
        <button
          onClick={() => setMetric('v_max')}
          className={`border px-2 py-1 ${
            metric === 'v_max' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-300 text-neutral-700 hover:border-neutral-900'
          }`}
        >
          {t('plm.metric.vmax')}
        </button>
        <button
          onClick={() => setMetric('v_med')}
          className={`border px-2 py-1 ${
            metric === 'v_med' ? 'border-neutral-900 bg-neutral-900 text-white' : 'border-neutral-300 text-neutral-700 hover:border-neutral-900'
          }`}
        >
          {t('plm.metric.vmed')}
        </button>
        <button
          onClick={paint}
          title={t('plm.paintTitle')}
          className="border border-red-700 px-2 py-1 text-red-800 hover:bg-red-50"
        >
          {t('plm.paint')}
        </button>
        {paintedMetric && (
          <button onClick={onClearPaint} className="text-neutral-500 underline hover:text-neutral-900">
            {t('plm.clearPaint')}
          </button>
        )}
        <button
          onClick={() => setHelpOpen(true)}
          title={t('plm.helpTitle')}
          className="ml-1 inline-flex h-4 w-4 items-center justify-center border border-neutral-300 text-[10px] leading-none text-neutral-500 hover:border-neutral-900 hover:text-neutral-900"
          data-demo="plm-help"
        >
          ?
        </button>
        <span
          className={`mono ml-auto border px-2 py-0.5 text-[10px] ${dummy
            ? 'border-red-700 bg-red-50 text-red-800'
            : 'border-neutral-900 text-neutral-900'}`}
          data-demo="plm-scorer"
        >
          {result.plm_scorer}
        </span>
        {jobId && (
          <span className="flex gap-3">
            <a
              href={`/api/v1/files/${jobId}/plm_screen.csv`}
              download
              className="text-neutral-500 underline hover:text-neutral-900"
            >
              {t('plm.csv')}
            </a>
            <a
              href={`/api/v1/files/${jobId}/plm_screen.json`}
              download
              className="text-neutral-500 underline hover:text-neutral-900"
            >
              {t('plm.json')}
            </a>
          </span>
        )}
      </div>
      {paintedMetric && (
        <div className="text-[10px] text-neutral-400">
          {t('plm.painted', {
            metric: paintedMetric === 'plm_v_max' ? t('plm.metric.vmax') : t('plm.metric.vmed'),
          })}
        </div>
      )}

      <PetalHeatmap
        positions={positions.map((p) => ({
          pos: p.pos,
          rows: p.rows.map((r): PetalRow => ({
            mut_aa: r.mut_aa,
            pctl: r.pctl,
            tip: t('plm.heatTip', {
              m: `${p.wt_aa}${p.pos}${r.mut_aa}`,
              pctl: r.pctl.toFixed(2),
              margin: r.plm_margin.toFixed(2),
            }),
          })),
        }))}
        title={t('plm.heatmap')}
        xTitle={t('res.xaxis.residue')}
        legendText={t('plm.heatLegend')}
      />

      {selected && <RoseDetail pos={selected} />}

      {/* ранжированная таблица: перцентили plm-канала; folded — чип RMSD */}
      {/* 排序表：plm 通道百分位；已折叠行显示 RMSD 徽标 */}
      <div className="max-h-96 overflow-y-auto border border-neutral-200">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-neutral-100 text-neutral-600">
            <tr>
              <th className="px-2 py-1.5 text-left">{t('plm.h.pos')}</th>
              <th className="px-2 py-1.5 text-left">{t('plm.h.rose')}</th>
              <th className="px-2 py-1.5 text-right">{t('plm.h.vmax')}</th>
              <th className="px-2 py-1.5 text-right">{t('plm.h.vmed')}</th>
              <th className="px-2 py-1.5 text-right">{t('plm.h.logprob')}</th>
              <th className="px-2 py-1.5 text-left">{t('plm.h.fold')}</th>
              <th className="px-2 py-1.5 text-right">{t('plm.h.pctl')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const key = metric === 'v_max' ? 'pctl_v_max' : 'pctl_v_med'
              const worst = p.rows.reduce((m, r) => (r.plm_margin < m.plm_margin ? r : m), p.rows[0])
              return (
                <tr
                  key={p.pos}
                  onClick={() => setSelectedPos(p.pos)}
                  className={`cursor-pointer border-t border-neutral-100 hover:bg-neutral-100 ${
                    selected?.pos === p.pos ? 'bg-neutral-100' : 'bg-white'
                  }`}
                >
                  <td className="mono px-2 py-1.5 font-medium text-neutral-900">
                    {p.wt_aa}{p.pos}
                  </td>
                  <td className="px-2 py-1"><TableRose p={p} /></td>
                  <td className="mono px-2 py-1.5 text-right">{p.stats.plm_v_max.toFixed(2)}</td>
                  <td className="mono px-2 py-1.5 text-right text-neutral-500">{p.stats.plm_v_med.toFixed(2)}</td>
                  <td className="mono px-2 py-1.5 text-right text-neutral-500">{p.stats.logprob_wt.toFixed(2)}</td>
                  <td className="px-2 py-1.5">
                    {worst.local_rmsd != null ? (
                      <span className="mono px-1.5 py-0.5 text-[10px] text-neutral-800" title={t('plm.foldChip')}>
                        {p.wt_aa}{p.pos}{worst.mut_aa} · {worst.local_rmsd.toFixed(2)} Å
                      </span>
                    ) : (
                      <span className="text-neutral-300">—</span>
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <PctlBar v={p.stats[key]} />
                    <span className="mono ml-1 text-[10px] text-neutral-500">{p.stats[key].toFixed(2)}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* блок фолдинга: бюджет и согласие PLM ↔ структура */}
      {/* 折叠块：预算与 PLM ↔ 结构一致性 */}
      {(result.folds.done > 0 || result.folds.planned > 0) && (
        <div className="flex flex-wrap items-center gap-3 border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-700">
          <span>{t('plm.folds', { done: result.folds.done, planned: result.folds.planned })}</span>
          {result.folds.consistency_spearman != null && (
            <span>{t('plm.consistency', { rho: result.folds.consistency_spearman.toFixed(3) })}</span>
          )}
        </div>
      )}

      {dummy && (
        <div className="border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
          {t('plm.dummyNote')}
        </div>
      )}

      <div className="text-[10px] text-neutral-400">
        {t('plm.note')}
      </div>

      {helpOpen && (
        <Modal title={t('plm.helpTitle')} onClose={() => setHelpOpen(false)}>
          {tl('help.plmScreen').map((p, i) => (
            <p key={i} className={i < tl('help.plmScreen').length - 1 ? 'mb-2 text-sm text-neutral-800' : 'text-sm text-neutral-800'}>
              {renderBold(p)}
            </p>
          ))}
        </Modal>
      )}
    </div>
  )
}

// лепестки PLM-розы: длина = перцентиль plm_damage (канал бэкенда), цвет =
// ранг plm_damage внутри позиции; WT-замена с margin 0 в слот WT не попадает.
// PLM 玫瑰花瓣：长度 = plm_damage 百分位，颜色 = 位点内 plm_damage 排名。
function plmPetals(p: PlmPosition, fmt: (m: string, pctl: string, margin: string) => string) {
  const damages = p.rows.map((r) => r.plm_damage)
  return p.rows.map((r) => ({
    aa: r.mut_aa,
    len: r.pctl,
    intensity: rank(r.plm_damage, damages),
    tip: fmt(`${p.wt_aa}${p.pos}${r.mut_aa}`, r.pctl.toFixed(2), r.plm_margin.toFixed(2)),
  }))
}

function plmPetalTip(t: (k: Key, params?: Record<string, string | number>) => string) {
  return (m: string, pctl: string, margin: string) => t('plm.petalTip', { m, pctl, margin })
}

function TableRose({ p }: { p: PlmPosition }) {
  const { t } = useI18n()
  return (
    <RoseGlyph
      petals={plmPetals(p, plmPetalTip(t))}
      wtSlot={PETAL_DIRS.indexOf(p.wt_aa)}
      size={44}
      title={t('map.roseTitle', { m: `${p.wt_aa}${p.pos}` })}
    />
  )
}

function RoseDetail({ pos }: { pos: PlmPosition }) {
  const { t } = useI18n()
  const worst = pos.rows.reduce((m, r) => (r.plm_margin < m.plm_margin ? r : m), pos.rows[0])
  const st = pos.stats
  return (
    <div className="flex items-start gap-4 border border-neutral-200 bg-neutral-50 p-3">
      <RoseGlyph petals={plmPetals(pos, plmPetalTip(t))} wtSlot={PETAL_DIRS.indexOf(pos.wt_aa)} size={150} />
      <div className="min-w-0 flex-1 space-y-1.5 text-xs text-neutral-700">
        <div className="text-sm font-medium text-neutral-900">
          {t('map.detailTitle', { m: `${pos.wt_aa}${pos.pos}` })}
        </div>
        <div>
          {t('plm.detailVmax', { v: st.plm_v_max.toFixed(2) })} ·{' '}
          {t('plm.detailVmed', { v: st.plm_v_med.toFixed(2) })} ·{' '}
          {t('plm.detailLogprob', { v: st.logprob_wt.toFixed(2) })}
        </div>
        <div>
          {t('plm.detailWorst', {
            m: `${pos.wt_aa}${pos.pos}${worst.mut_aa}`,
            margin: worst.plm_margin.toFixed(2),
          })}
        </div>
        <div className="text-[10px] text-neutral-500">
          {t('plm.lenChannel')} · {t('plm.colorChannel')}
        </div>
      </div>
    </div>
  )
}