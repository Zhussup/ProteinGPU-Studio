// HistoryPage: журнал задач целиком. Клик по завершённой задаче
// восстанавливает её результат и уводит на страницу этого вида анализа.
// HistoryPage：完整任务日志。点击已完成任务可恢复结果，
// 并跳转到该分析类型所在的页面。
import { useI18n } from '../i18n'
import { useWorkspace } from '../state/workspace'
import PageFrame from '../components/PageFrame'
import HistoryPanel from '../components/HistoryPanel'

export default function HistoryPage() {
  const { t } = useI18n()
  const ws = useWorkspace()

  return (
    <PageFrame titleKey="nav.history" leadKey="hint.history">
      <div className="panel p-4">
        <HistoryPanel
          jobs={ws.history}
          currentJobId={ws.jobStatus?.job_id ?? null}
          onRestore={ws.restore}
          onRefresh={ws.refreshHistory}
          tall
        />
      </div>
      {ws.history.length === 0 && (
        <div className="text-xs text-neutral-400">{t('hist.empty')}</div>
      )}
    </PageFrame>
  )
}
