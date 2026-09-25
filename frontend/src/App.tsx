import { useEffect, useState } from 'react'
import WorkspacePage from './pages/WorkspacePage'
import BenchmarksPage from './pages/BenchmarksPage'
import { api } from './lib/api'
import { LOCALES, useI18n, type Key, type Lang } from './i18n'

type Tab = 'workspace' | 'benchmarks'

const TAB_KEYS: Record<Tab, Key> = {
  workspace: 'nav.workspace',
  benchmarks: 'nav.benchmarks',
}

// Переключатель RU / EN / 中文; активная локаль — сплошной чёрный, как вкладки.
// RU / EN / 中文 切换器；当前语言为实心黑，与标签页一致。
function LanguageSwitch() {
  const { lang, setLang, t } = useI18n()
  return (
    <span className="flex" title={t('common.language')}>
      {(Object.keys(LOCALES) as Lang[]).map((l) => (
        <button
          key={l}
          onClick={() => setLang(l)}
          className={`border px-2 py-1.5 transition first:border-r-0 ${
            lang === l
              ? 'border-neutral-900 bg-neutral-900 font-medium text-white'
              : 'border-neutral-200 text-neutral-500 hover:border-neutral-900 hover:text-neutral-900'
          }`}
        >
          {LOCALES[l].label}
        </button>
      ))}
    </span>
  )
}

export default function App() {
  const { t } = useI18n()
  const [tab, setTab] = useState<Tab>('workspace')
  const [health, setHealth] = useState<'ok' | 'down' | 'checking'>('checking')

  useEffect(() => {
    setHealth('checking')
    api.health()
      .then(() => setHealth('ok'))
      .catch(() => setHealth('down'))
  }, [tab])

  const healthTitle =
    health === 'ok' ? t('health.ok') : health === 'down' ? t('health.down') : t('health.checking')

  return (
    <div className="mx-auto max-w-7xl px-4 py-5">
      <header className="mb-5 flex items-end justify-between border-b border-neutral-200 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-neutral-900">
            ProteinGPU-Studio
          </h1>
          <p className="text-xs text-neutral-500">{t('app.subtitle')}</p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <LanguageSwitch />
          <nav className="flex">
            {(['workspace', 'benchmarks'] as Tab[]).map((tb) => (
              <button
                key={tb}
                onClick={() => setTab(tb)}
                className={`border border-b-0 px-3 py-1.5 transition ${
                  tab === tb
                    ? 'border-neutral-900 bg-neutral-900 font-medium text-white'
                    : 'border-neutral-200 text-neutral-500 hover:border-neutral-900 hover:text-neutral-900'
                }`}
              >
                {t(TAB_KEYS[tb])}
              </button>
            ))}
          </nav>
          <span
            className={`inline-block h-2.5 w-2.5 border ${
              health === 'ok'
                ? 'border-neutral-900 bg-neutral-900'
                : health === 'down'
                  ? 'border-red-700 bg-red-700'
                  : 'border-neutral-300 bg-neutral-200'
            }`}
            title={healthTitle}
          />
        </div>
      </header>

      {tab === 'workspace' ? <WorkspacePage /> : <BenchmarksPage />}
    </div>
  )
}