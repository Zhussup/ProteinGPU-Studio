// App: оболочка приложения — постоянный сайдбар (белок, навигация, вычисления,
// активная задача) + область страницы под роутером. Каждый вид анализа живёт
// на своей странице: параметры перестают наслаиваться, а взаимоисключающие
// режимы выбираются явно внутри своей страницы.
// App：应用外壳——常驻侧栏（蛋白、导航、算力、活动任务）+ 路由下的页面区域。
// 每种分析各有其页：参数不再堆叠，互斥模式在各自页面内显式选择。
import { useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { api } from './lib/api'
import { LOCALES, useI18n, type Key, type Lang } from './i18n'
import { useTheme } from './state/theme'
import ProteinCard from './components/ProteinCard'
import ComputeCard from './components/ComputeCard'
import JobMiniStatus from './components/JobMiniStatus'
import StructurePage from './pages/StructurePage'
import ScanPage from './pages/ScanPage'
import EnsemblePage from './pages/EnsemblePage'
import SensitivityPage from './pages/SensitivityPage'
import PlmPage from './pages/PlmPage'
import ValidationPage from './pages/ValidationPage'
import ComparisonPage from './pages/ComparisonPage'
import HistoryPage from './pages/HistoryPage'
import BenchmarksPage from './pages/BenchmarksPage'

// группы навигации сайдбара: анализ → результат, данные, система
// 侧栏导航分组：分析 → 结果、数据、系统
const NAV_GROUPS: { key: Key; items: { to: string; key: Key }[] }[] = [
  {
    key: 'nav.group.analysis',
    items: [
      { to: '/structure', key: 'nav.structure' },
      { to: '/scan', key: 'nav.scan' },
      { to: '/ensemble', key: 'nav.ensemble' },
      { to: '/sensitivity', key: 'nav.sensitivity' },
      { to: '/plm', key: 'nav.plm' },
    ],
  },
  {
    key: 'nav.group.data',
    items: [
      { to: '/validation', key: 'nav.validation' },
      { to: '/comparison', key: 'nav.comparison' },
      { to: '/history', key: 'nav.history' },
    ],
  },
  {
    key: 'nav.group.system',
    items: [
      { to: '/benchmarks', key: 'nav.benchmarks' },
    ],
  },
]

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

// ThemeToggle: sun/moon в том же квадратном стиле, что и переключатель языка.
// ThemeToggle：与语言切换器同一方角风格的 sun/moon 按钮。
function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const { t } = useI18n()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      title={t(dark ? 'theme.toLight' : 'theme.toDark')}
      aria-label={t(dark ? 'theme.toLight' : 'theme.toDark')}
      className="border border-neutral-200 px-2 py-1.5 text-neutral-500 transition hover:border-neutral-900 hover:text-neutral-900"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
        {dark ? (
          // луна / 月亮
          <path d="M20 12.5A8 8 0 1 1 11.5 4 6.5 6.5 0 0 0 20 12.5Z" />
        ) : (
          // солнце / 太阳
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" />
          </>
        )}
      </svg>
    </button>
  )
}

// HealthDot: индикатор доступности бэкенда; перепроверяется при смене страницы.
// HealthDot：后端可用性指示；切换页面时重新检查。
function HealthDot() {
  const { t } = useI18n()
  const { pathname } = useLocation()
  const [health, setHealth] = useState<'ok' | 'down' | 'checking'>('checking')

  useEffect(() => {
    setHealth('checking')
    api.health()
      .then(() => setHealth('ok'))
      .catch(() => setHealth('down'))
  }, [pathname])

  const title = health === 'ok' ? t('health.ok') : health === 'down' ? t('health.down') : t('health.checking')
  return (
    <span
      className={`inline-block h-2.5 w-2.5 border ${
        health === 'ok'
          ? 'border-neutral-900 bg-neutral-900'
          : health === 'down'
            ? 'border-red-700 bg-red-700'
            : 'border-neutral-300 bg-neutral-200'
      }`}
      title={title}
    />
  )
}

export default function App() {
  const { t } = useI18n()

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <aside className="w-full shrink-0 border-b border-neutral-200 px-4 py-5 lg:sticky lg:top-0 lg:h-screen lg:w-72 lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <div className="mb-4">
          <h1 className="text-lg font-semibold tracking-tight text-neutral-900">
            ProteinGPU-Studio
          </h1>
          <p className="text-xs text-neutral-500">{t('app.subtitle')}</p>
        </div>

        <div className="space-y-3">
          <ProteinCard />

          <nav className="space-y-3">
            {NAV_GROUPS.map((g) => (
              <div key={g.key}>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-neutral-400">
                  {t(g.key)}
                </div>
                <div className="flex flex-row flex-wrap gap-1 lg:flex-col">
                  {g.items.map((it) => (
                    <NavLink
                      key={it.to}
                      to={it.to}
                      data-demo={`tab-${it.to.slice(1)}`}
                      className={({ isActive }) =>
                        `border px-2.5 py-1.5 text-xs transition ${
                          isActive
                            ? 'border-neutral-900 bg-neutral-900 font-medium text-white'
                            : 'border-neutral-200 text-neutral-600 hover:border-neutral-900 hover:text-neutral-900'
                        }`
                      }
                    >
                      {t(it.key)}
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </nav>

          <ComputeCard />
          <JobMiniStatus />
        </div>

        <div className="mt-5 flex items-center justify-between border-t border-neutral-200 pt-3">
          <LanguageSwitch />
          <span className="flex items-center gap-2">
            <ThemeToggle />
            <HealthDot />
          </span>
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-4 py-6 lg:px-6">
        <div className="mx-auto max-w-6xl">
          <Routes>
            <Route path="/" element={<Navigate to="/structure" replace />} />
            <Route path="/structure" element={<StructurePage />} />
            <Route path="/scan" element={<ScanPage />} />
            <Route path="/ensemble" element={<EnsemblePage />} />
            <Route path="/sensitivity" element={<SensitivityPage />} />
            <Route path="/plm" element={<PlmPage />} />
            <Route path="/validation" element={<ValidationPage />} />
            <Route path="/comparison" element={<ComparisonPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/benchmarks" element={<BenchmarksPage />} />
            <Route path="*" element={<Navigate to="/structure" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
