// JobMiniStatus: активная (или только что завершённая) задача в сайдбаре.
// Прогресс и отмена видны с любой страницы — переход между страницами больше
// не «прячет» запущенный расчёт.
// JobMiniStatus：侧栏中的活动（或刚完成的）任务。
// 进度与取消在任意页面可见——页面切换不再“藏起”正在运行的计算。
import { Link } from 'react-router-dom'
import { useI18n, type Key } from '../i18n'
import { KIND_KEYS, KIND_ROUTE, useWorkspace } from '../state/workspace'
import JobProgress from './JobProgress'

export default function JobMiniStatus() {
  const { t } = useI18n()
  const { jobStatus, jobRunning, jobError, cancelJob } = useWorkspace()
  if (!jobStatus) return null

  const kindLabel = t((KIND_KEYS[jobStatus.kind] ?? 'shell.job') as Key)
  const to = KIND_ROUTE[jobStatus.kind] ?? '/history'

  return (
    <div className="panel space-y-2 p-3">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-neutral-500">{t('shell.job')}</span>
        <Link to={to} className="underline hover:text-neutral-900">{kindLabel}</Link>
      </div>

      {jobRunning && (
        <JobProgress variant="mini" status={jobStatus} error={jobError} running onCancel={cancelJob} />
      )}

      {jobStatus.status === 'done' && (
        <div className="flex items-center gap-1.5 text-[11px] text-neutral-600">
          <span className="inline-block h-2 w-2 shrink-0 bg-neutral-900" />
          <Link to={to} className="underline hover:text-neutral-900">{kindLabel}</Link>
        </div>
      )}

      {jobStatus.status === 'cancelled' && (
        <div className="text-[11px] text-neutral-500">{t('run.cancelled')}</div>
      )}

      {jobStatus.status === 'error' && (
        <div className="border border-red-300 bg-red-50 px-2 py-1 text-[11px] text-red-800">
          {jobError ?? t('run.jobFailed')}
        </div>
      )}
    </div>
  )
}
