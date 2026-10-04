// ComparisonPage: сводные таблицы по всем прогонам — мутации одного белка и
// чувствительность позиций. Раньше эти таблицы теснились внизу рабочей
// области, теперь у них отдельная страница.
// ComparisonPage：所有运行的汇总表——同一蛋白的突变与位点敏感性。
// 这些表格原先挤在工作台底部，现在有了独立页面。
import { useWorkspace } from '../state/workspace'
import PageFrame from '../components/PageFrame'
import MutationsCompare from '../components/MutationsCompare'
import SensitivityCompare from '../components/SensitivityCompare'

export default function ComparisonPage() {
  const ws = useWorkspace()
  const wtSequence = ws.seqOk ? ws.seq : ''

  return (
    <PageFrame titleKey="nav.comparison" leadKey="hint.comparison">
      <div className="panel p-4">
        <MutationsCompare jobs={ws.history} wtSequence={wtSequence} />
      </div>
      <div className="panel p-4">
        <SensitivityCompare jobs={ws.history} wtSequence={wtSequence} />
      </div>
    </PageFrame>
  )
}
