// ResultTabs: RMSD cards + summary + sequences + pLDDT after a mutation job.
// Each metric carries a "?" button opening a plain-language explanation modal.
import { Suspense, lazy, useState, type ReactNode } from 'react'
import type { MutationResult } from '../lib/types'
import Modal from './Modal'

const Plot = lazy(() => import('./PlotlyChart'))

const BADGE: Record<string, { cls: string; label: string }> = {
  stable: { cls: 'border border-neutral-900 text-neutral-900', label: 'стабильна' },
  moderate: { cls: 'bg-neutral-600 text-white', label: 'умеренно' },
  critical: { cls: 'bg-red-700 text-white', label: 'критично' },
}

// Plain-language explanations; shown via the "?" button on each metric.
// Wording mirrors docs/ml_model_decision.md and the README walkthrough.
const HELP: Record<string, { title: string; body: ReactNode }> = {
  global: {
    title: 'Global RMSD',
    body: (
      <>
        <p className="mb-2">Среднее «съезжание» атомов по <b>всему белку</b> после оптимального
        совмещения (алгоритм Кабш): расстояния между парными CA-атомами возводятся в квадрат,
        усредняются, из среднего извлекается корень. Измеряется в ангстремах
        (1 Å = 0.1 нанометра ≈ размер атома).</p>
        <p className="mb-2">Ориентиры: 0.2 Å — структуры практически одинаковы; 1–2 Å — заметные
        локальные изменения; более 5 Å — разные укладки.</p>
        <p><b>Почему это не главная метрика:</b> глобальный RMSD усредняет по всему белку, включая
        концы и петли, которые модель отрисовывает с небольшим шумом. Эффект точечной мутации в нём
        тонет — поэтому смотрят на Local RMSD.</p>
      </>
    ),
  },
  local: {
    title: 'Local RMSD (окно ±10 остатков)',
    body: (
      <>
        <p className="mb-2">То же измерение, но <b>только в окне ±10 остатков от места мутации</b>.
        Это главная метрика: она спрашивает не «изменился ли белок вообще», а «изменился ли белок
        в месте события».</p>
        <p className="mb-2">Пороги вердикта: менее 1 Å — «стабильна», 1–2 Å — «умеренно», 2 Å и более —
        «критично».</p>
        <p><b>Честная оговорка:</b> OmegaFold почти детерминирован — на стабильном фолде точечные
        мутации дают суб-Å сдвиги (убиквитин: I44A 0.21 Å, I3L 0.28 Å, P19G 0.72 Å). Поэтому
        сравнивайте мутации <b>между собой</b>, а не с абсолютным порогом.</p>
      </>
    ),
  },
  tm: {
    title: 'TM-score',
    body: (
      <>
        <p className="mb-2">Мера совпадения <b>глобальной укладки</b> (архитектуры: спирали и листы
        на своих местах), нормированная на длину белка. Шкала 0–1.</p>
        <p className="mb-2">Более 0.9 — та же укладка; 0.5–0.9 — узнаваема, но деформирована;
        менее 0.5 — структуры укладываются по-разному (для точечной мутации тревожный,
        почти невозможный результат).</p>
        <p>В отличие от RMSD, TM-score не растёт с длиной белка — им сравнивают структуры
        разных размеров.</p>
      </>
    ),
  },
  plddt: {
    title: 'pLDDT WT / mut',
    body: (
      <>
        <p className="mb-2"><b>pLDDT</b> — самооценка нейросети по каждому остатку, 0–100: «насколько
        я уверена, что этот участок свернулся именно так». Здесь показано среднее по всей структуре
        для WT и мутанта.</p>
        <p>Малое значение (менее 60) — сигнал «модель фантазирует, картинке не верьте».
        У хорошо изученного белка вроде убиквитина pLDDT обычно 90+.</p>
      </>
    ),
  },
  dplddt: {
    title: 'ΔpLDDT',
    body: (
      <>
        <p className="mb-2">Сдвиг уверенности модели: <b>pLDDT мутанта − pLDDT WT</b>.</p>
        <p className="mb-2">Отрицательный — модель стала <b>менее уверена</b> в структуре мутанта:
        мутация попала в структурно значимый регион. Положительный — мутация «упорядочила»
        регион. Для стабильного белка обычно в пределах ±1–2.</p>
        <p>У OmegaFold снижение pLDDT часто предшествует реальному изменению структуры —
        это полезный ранний сигнал.</p>
      </>
    ),
  },
}

function QuestionMark({ topic, onOpen }: { topic: string; onOpen: (t: string) => void }) {
  return (
    <button
      onClick={() => onOpen(topic)}
      title="что это значит?"
      className="ml-1 inline-flex h-4 w-4 items-center justify-center border border-neutral-300 text-[10px] leading-none text-neutral-500 hover:border-neutral-900 hover:text-neutral-900"
    >
      ?
    </button>
  )
}

export default function ResultTabs({ result }: { result: MutationResult | null }) {
  const [help, setHelp] = useState<string | null>(null)
  if (!result?.rmsd) return null
  const r = result.rmsd
  const badge = BADGE[r.interpretation] ?? BADGE.moderate

  return (
    <div className="space-y-4">
      {result.summary && (
        <div className="border-l-2 border-neutral-900 bg-neutral-50 p-3 text-sm text-neutral-800">
          {result.summary}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Global RMSD" value={`${r.global_rmsd.toFixed(2)} Å`} help="global" onHelp={setHelp} />
        <Metric
          label={`Local RMSD (${r.local_window[0]}–${r.local_window[1]})`}
          value={`${r.local_rmsd.toFixed(2)} Å`}
          help="local"
          onHelp={setHelp}
        />
        <Metric label="TM-score" value={r.tm_score.toFixed(3)} help="tm" onHelp={setHelp} />
        <div className="border border-neutral-200 bg-white p-3">
          <div className="text-[11px] text-neutral-500">
            Вердикт <QuestionMark topic="local" onOpen={setHelp} />
          </div>
          <span className={`mono mt-2 inline-block px-2 py-0.5 text-xs font-medium ${badge.cls}`}>
            {badge.label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs text-neutral-600 lg:grid-cols-4">
        <MetricSmall label="pLDDT WT" value={r.plddt_wt.toFixed(1)} help="plddt" onHelp={setHelp} />
        <MetricSmall label="pLDDT mut" value={r.plddt_mut.toFixed(1)} help="plddt" onHelp={setHelp} />
        <MetricSmall label="ΔpLDDT" value={(r.plddt_mut - r.plddt_wt).toFixed(1)} help="dplddt" onHelp={setHelp} />
        <MetricSmall label="Движок выравнивания" value={r.engine} />
      </div>

      {(result.plddt_wt_list && result.plddt_mut_list) && (
        <details open className="border border-neutral-200 bg-neutral-50 p-3">
          <summary className="cursor-pointer text-xs text-neutral-600">
            pLDDT-профиль по остаткам
            <QuestionMark topic="plddt" onOpen={setHelp} />
          </summary>
          <div className="mt-2">
            <Suspense fallback={<div className="py-10 text-center text-xs text-neutral-400">график загружается…</div>}>
              <PlddtChart
                wt={result.plddt_wt_list}
                mut={result.plddt_mut_list}
                position={result.position}
                wtAA={result.wt_aa}
                mutAA={result.mutant_aa}
              />
            </Suspense>
            <div className="mt-1 text-[10px] text-neutral-400">
              серая линия — WT, чёрная — мутант; красный маркер — позиция мутации.
              Провал уверенности в окне мутации часто предшествует реальному структурному сдвигу
            </div>
          </div>
        </details>
      )}

      <details className="border border-neutral-200 bg-neutral-50 p-3 text-xs">
        <summary className="cursor-pointer text-neutral-600">Последовательности</summary>
        <div className="mono mt-2 space-y-2 break-all">
          <div>
            <span className="text-neutral-500">WT </span>
            <span className="text-neutral-800">{result.wt_sequence}</span>
          </div>
          <div>
            <span className="text-neutral-500">MUT </span>
            <span className="text-neutral-800">
              {result.mutant_sequence.slice(0, result.position - 1)}
              <b className="bg-red-700 px-0.5 text-white">{result.mutant_sequence[result.position - 1]}</b>
              {result.mutant_sequence.slice(result.position)}
            </span>
          </div>
        </div>
      </details>

      {help && (
        <Modal title={HELP[help]?.title ?? ''} onClose={() => setHelp(null)}>
          <div className="space-y-2 text-sm text-neutral-800">{HELP[help]?.body}</div>
        </Modal>
      )}
    </div>
  )
}

function Metric({ label, value, help, onHelp }: {
  label: string; value: string; help: string; onHelp: (t: string) => void
}) {
  return (
    <div className="border border-neutral-200 bg-white p-3">
      <div className="text-[11px] text-neutral-500">
        {label} <QuestionMark topic={help} onOpen={onHelp} />
      </div>
      <div className="mono mt-1 text-xl text-neutral-900">{value}</div>
    </div>
  )
}

// Per-residue pLDDT trace: WT (grey) vs mutant (black), mutation position marked.
function PlddtChart({ wt, mut, position, wtAA, mutAA }: {
  wt: number[]; mut: number[]; position: number; wtAA: string; mutAA: string
}) {
  const xs = wt.map((_, i) => i + 1)
  const data = [
    {
      x: xs, y: wt, type: 'scatter', mode: 'lines', name: 'WT',
      line: { color: '#9ca3af', width: 1.5 },
    },
    {
      x: xs, y: mut, type: 'scatter', mode: 'lines', name: `${wtAA}${position}${mutAA}`,
      line: { color: '#111111', width: 2 },
    },
    {
      x: [position, position], y: [
        Math.min(...wt, ...mut) - 2, Math.max(...wt, ...mut) + 2,
      ], type: 'scatter', mode: 'lines', name: 'мутация',
      line: { color: '#b91c1c', width: 1, dash: 'dot' }, showlegend: false,
    },
  ]
  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 45 },
    paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
    font: { color: '#525252', size: 11 },
    xaxis: { title: { text: 'номер остатка' }, linecolor: '#d4d4d4' },
    yaxis: { title: { text: 'pLDDT' }, range: [0, 100], gridcolor: '#e5e5e5', linecolor: '#d4d4d4' },
    legend: { orientation: 'h', y: 1.15 },
  }
  return <Plot data={data} layout={layout} />
}

function MetricSmall({ label, value, help, onHelp }: {
  label: string; value: string; help?: string; onHelp?: (t: string) => void
}) {
  return (
    <div className="border border-neutral-200 bg-white px-3 py-2">
      <span className="text-neutral-500">{label}:</span>{' '}
      {help && onHelp && <QuestionMark topic={help} onOpen={onHelp} />}{' '}
      <span className="mono text-neutral-800">{value}</span>
    </div>
  )
}