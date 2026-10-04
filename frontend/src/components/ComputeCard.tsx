// ComputeCard: профиль инференса и статус GPU — параметры, общие для ВСЕХ
// запусков, поэтому живут в сайдбаре (видны с любой страницы), а не дублируются
// в панели каждого анализа.
// ComputeCard：推理配置与 GPU 状态——所有运行共用的参数，因此放在侧栏
//（任意页面可见），而不是在每个分析面板中重复。
import { useI18n, type Key } from '../i18n'
import { useWorkspace } from '../state/workspace'
import type { InferenceProfile } from '../lib/types'

// Подписи селектора профиля исполнения (семантика _prepare_model бэкенда).
// 运行配置选择器的标签（后端 _prepare_model 的语义）。
const PROFILE_OPTIONS: { id: InferenceProfile; label: Key }[] = [
  { id: 'auto', label: 'run.auto' },
  { id: 'fp32-gpu', label: 'run.profile.fp32' },
  { id: 'fp16-gpu', label: 'run.profile.fp16' },
  { id: 'cpu', label: 'run.profile.cpu' },
  { id: 'dummy', label: 'run.dummy' },
]

export default function ComputeCard() {
  const { t } = useI18n()
  const { profile, setProfile, gpu, jobRunning } = useWorkspace()

  return (
    <div className="panel space-y-2 p-3">
      <div className="text-sm font-medium text-neutral-900">{t('shell.compute')}</div>

      <div className="flex items-center gap-2 text-xs text-neutral-600">
        <label htmlFor="profile-select">{t('run.profile')}</label>
        <select
          id="profile-select"
          value={profile}
          onChange={(e) => setProfile(e.target.value as InferenceProfile)}
          disabled={jobRunning}
          className="mono min-w-0 flex-1 border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-900 focus:border-neutral-900"
        >
          {PROFILE_OPTIONS.map((o) => (
            <option key={o.id} value={o.id}>{t(o.label)}</option>
          ))}
        </select>
      </div>
      <div className="text-[10px] text-neutral-400">{t('run.profileHint')}</div>

      {gpu && (
        <div className={`mono border px-2 py-0.5 text-[11px] ${
          gpu.available ? 'border-neutral-900 text-neutral-900' : 'border-neutral-300 text-neutral-500'
        }`}>
          {gpu.available
            ? t('run.gpu', { name: gpu.name ?? '' })
            : t('run.cpuOnly', { reason: gpu.reason ?? t('run.noCuda') })}
        </div>
      )}
    </div>
  )
}
