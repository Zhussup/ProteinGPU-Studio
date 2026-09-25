// MoleculeViewer: обёртка 3Dmol.js на белом холсте.
// WT — полупрозрачный серый cartoon; мутант — тёмно-серый/спектр; мутированный
// остаток — красные стики. Бэкенд отдаёт уже выровненный PDB мутанта
// (выравнивание делает ядро C++/CUDA) — никакой математики на клиенте.
// MoleculeViewer：白底画布上的 3Dmol.js 封装。
// WT 为半透明灰色 cartoon；突变体为深灰/渐变谱；突变残基为红色棍棒。
// 后端返回已对齐的突变体 PDB（对齐由 C++/CUDA 核心完成）——客户端不做任何计算。
import { useEffect, useRef } from 'react'
// UMD-бандл: импорт определяет window.$3Dmol
// UMD 包：导入后即定义 window.$3Dmol
import '3dmol'
import { useI18n } from '../i18n'
import { bucketColor, bucketOf, HEAT_BUCKETS } from './RoseGlyph'

// 3dmol поставляет UMD-бандл; объявляем минимальную поверхность, которую используем.
// 3dmol 提供 UMD 包；这里仅声明我们用到的最小接口。
declare global {
  interface Window {
    $3Dmol?: {
      createViewer: (
        el: HTMLElement,
        cfg: Record<string, unknown>,
      ) => $3DmolViewer
      syncSurface: () => void
    }
  }
  interface $3DmolViewer {
    addModel(data: string, format: string): void
    addStyle(sel: Record<string, unknown>, style: Record<string, unknown>): void
    addSurface(
      type: number,
      style: Record<string, unknown>,
      sel?: Record<string, unknown>,
    ): void
    removeAllSurfaces(): void
    removeAllModels(): void
    zoomTo(): void
    zoom(factor?: number): void
    render(): void
    setBackgroundColor(color: string): void
    clear(): void
  }
}

const WT_COLOR = '#9ca3af' // светло-серый, полупрозрачный | 浅灰、半透明
const MUT_COLOR = '#1f2937' // почти чёрный | 近黑
const MUT_COLOR_ALT = '#374151' // фолбэк, когда выравнивания нет | 未对齐时的回退色
const MUTATION_COLOR = '#b91c1c' // строгий красный | 严格红

export interface ViewerProps {
  wtPdb: string | null
  mutPdb: string | null
  aligned: boolean // true → mutPdb — выровненный вариант | true → mutPdb 为已对齐版本
  mutationPosition?: number // с 1 | 从 1 起
  height?: number
  // раскраска чувствительности (scan map): скаляр 0..1 на остаток (null = не измерено),
  // индекс 0 = остаток 1; раскрашивает WT-cartoon квантованными "тепловыми" корзинами
  // 敏感性着色（scan map）：逐残基标量 0..1（null = 未测），
  // 索引 0 = 残基 1；按分档热度给 WT cartoon 着色
  residueScores?: (number | null)[] | null
  scoreLabel?: string
}

// группируем измеренные остатки в непрерывные пробеги одной корзины → диапазоны resi
// 将已测残基分组为连续的同档区间 → resi 范围
export function scoreRuns(scores: (number | null)[]): { start: number; end: number; bucket: number }[] {
  const runs: { start: number; end: number; bucket: number }[] = []
  let cur: { start: number; end: number; bucket: number } | null = null
  scores.forEach((v, i) => {
    if (v === null || v === undefined) { cur = null; return }
    const bucket = bucketOf(v)
    if (cur && cur.bucket === bucket) {
      cur.end = i + 1
    } else {
      cur = { start: i + 1, end: i + 1, bucket }
      runs.push(cur)
    }
  })
  return runs
}

export default function MoleculeViewer({
  wtPdb, mutPdb, aligned, mutationPosition, height = 420, residueScores, scoreLabel,
}: ViewerProps) {
  const { t } = useI18n()
  const hostRef = useRef<HTMLDivElement>(null)
  const glRef = useRef<$3DmolViewer | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host || !window.$3Dmol) return
    const gl = window.$3Dmol.createViewer(host, { backgroundColor: '#ffffff' })
    glRef.current = gl
    // e2e-хук (?e2e в URL): демо-записи гоняют rotate/zoom через API вьюера —
    // синтетические события wheel не зумят в headless-захвате
    // e2e 钩子（URL 带 ?e2e）：演示录制通过查看器 API 驱动 rotate/zoom——
    // 无头截屏中合成 wheel 事件无法缩放
    if (new URLSearchParams(window.location.search).has('e2e')) {
      ;(window as unknown as { __mol?: $3DmolViewer }).__mol = gl
    }
    return () => {
      gl.clear()
      glRef.current = null
    }
  }, [])

  useEffect(() => {
    const gl = glRef.current
    if (!gl || !wtPdb) return
    gl.clear()

    // WT: полупрозрачный серый cartoon-бэкбон — или раскраска чувствительности,
    // когда scan map прислал оценки по остаткам (model: 0 не трогает модель
    // мутанта; null остаются базовым серым)
    // WT：半透明灰色 cartoon 骨架——或敏感性着色（当 scan map 传入逐残基
    // 分数时）（model: 0 不触碰突变体模型；null 保持基础灰色）
    gl.addModel(wtPdb, 'pdb')
    gl.addStyle({}, { cartoon: { color: WT_COLOR, opacity: 0.55 } })
    if (residueScores) {
      for (const run of scoreRuns(residueScores)) {
        gl.addStyle(
          { model: 0, resi: [`${run.start}-${run.end}`] },
          { cartoon: { color: bucketColor(run.bucket), opacity: 0.9 } },
        )
      }
    }

    // Мутант: выровненная (или сырая) модель, тёмный cartoon — контраст на белом
    // 突变体：对齐（或原始）模型，深色 cartoon——在白底上有对比度
    const mut = mutPdb
    if (mut) {
      gl.addModel(mut, 'pdb')
      const sel: Record<string, unknown> = {}
      if (aligned) {
        gl.addStyle(sel, { cartoon: { colorscheme: 'spectrum', opacity: 0.95 } })
      } else {
        gl.addStyle(sel, { cartoon: { color: MUT_COLOR_ALT, opacity: 0.95 } })
      }
      // мутированный остаток — красные стики
      // 突变残基以红色棍棒显示
      if (mutationPosition && mutationPosition >= 1) {
        gl.addStyle({ resi: mutationPosition }, {
          stick: { color: MUTATION_COLOR, radius: 0.25 },
          sphere: { color: MUTATION_COLOR, radius: 0.45 },
        })
      }
    }

    gl.zoomTo()
    gl.render()
  }, [wtPdb, mutPdb, aligned, mutationPosition, residueScores])

  const painted = !!residueScores && residueScores.some((v) => v !== null && v !== undefined)

  return (
    <div className="relative overflow-hidden border border-neutral-300 bg-white" data-demo="viewer">
      <div ref={hostRef} style={{ width: '100%', height }} className="cursor-grab" />
      <div className="pointer-events-none absolute right-2 bottom-2 border border-neutral-200 bg-white/85 px-2 py-1 text-[11px] text-neutral-500">
        {t('viewer.hint')}
      </div>
      {!wtPdb && (
        <div className="absolute inset-0 flex items-center justify-center text-neutral-400">
          {t('viewer.empty')}
        </div>
      )}
      {wtPdb && (mutPdb || painted) && (
        <div className="pointer-events-none absolute top-2 left-2 flex flex-col gap-1 text-[11px]">
          {painted ? (
            <LegendRamp label={scoreLabel ?? t('viewer.legendSensitivity')} />
          ) : (
            <Legend color={WT_COLOR} label={t('viewer.legendWt')} />
          )}
          {mutPdb && <Legend color={MUT_COLOR} label={t('viewer.legendMut')} />}
          {mutationPosition && mutPdb && <Legend color={MUTATION_COLOR} label={t('viewer.legendMutation', { pos: mutationPosition })} />}
        </div>
      )}
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5 border border-neutral-200 bg-white/85 px-2 py-0.5 text-neutral-700">
      <span className="inline-block h-2.5 w-2.5" style={{ background: color }} />
      {label}
    </div>
  )
}

// легенда-градиент для раскраски чувствительности: квантованные "тепловые" корзины
// 敏感性着色的渐变图例：分档热度色块
function LegendRamp({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1.5 border border-neutral-200 bg-white/85 px-2 py-0.5 text-neutral-700">
      <span className="flex">
        {Array.from({ length: HEAT_BUCKETS }, (_, i) => (
          <span key={i} className="inline-block h-2.5 w-2" style={{ background: bucketColor(i) }} />
        ))}
      </span>
      {label}
    </div>
  )
}