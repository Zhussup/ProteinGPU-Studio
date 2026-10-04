// RunRow: главная кнопка запуска страницы + сброс результатов.
// На каждой странице ровно одно основное действие — взаимоисключающие виды
// анализа разведены по страницам, а не свалены в один ряд кнопок.
// RunRow：页面的主运行按钮 + 结果重置。
// 每页只有一个主操作——互斥的分析类型分属不同页面，而非挤在一排按钮里。
import { useI18n } from '../i18n'
import { useWorkspace } from '../state/workspace'

export type RunTone = 'primary' | 'outline' | 'danger' | 'dangerFill'

const TONES: Record<RunTone, string> = {
  primary: 'bg-neutral-900 font-medium text-white hover:bg-neutral-700',
  outline: 'border border-neutral-900 text-neutral-900 hover:bg-neutral-100',
  danger: 'border border-red-700 text-red-800 hover:bg-red-50',
  dangerFill: 'bg-red-700 font-medium text-white hover:bg-red-600',
}

export interface RunRowProps {
  label: string
  onClick: () => void
  tone?: RunTone
}

export default function RunRow({ label, onClick, tone = 'primary' }: RunRowProps) {
  const { t } = useI18n()
  const { canRun, jobRunning, resultJob, resetResults } = useWorkspace()

  return (
    <div className="flex flex-wrap items-center gap-2" data-demo="runrow">
      <button
        type="button"
        onClick={onClick}
        disabled={!canRun || jobRunning}
        className={`px-4 py-2 text-sm transition disabled:opacity-40 ${TONES[tone]}`}
      >
        {label}
      </button>
      {resultJob && !jobRunning && (
        <button
          type="button"
          onClick={resetResults}
          className="text-xs text-neutral-500 underline hover:text-neutral-900"
        >
          {t('run.reset')}
        </button>
      )}
    </div>
  )
}
