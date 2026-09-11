import { useEffect, useState } from 'react'
import WorkspacePage from './pages/WorkspacePage'
import BenchmarksPage from './pages/BenchmarksPage'
import { api } from './lib/api'

type Tab = 'workspace' | 'benchmarks'

export default function App() {
  const [tab, setTab] = useState<Tab>('workspace')
  const [health, setHealth] = useState<'ok' | 'down' | 'checking'>('checking')

  useEffect(() => {
    setHealth('checking')
    api.health()
      .then(() => setHealth('ok'))
      .catch(() => setHealth('down'))
  }, [tab])

  return (
    <div className="mx-auto max-w-7xl px-4 py-5">
      <header className="mb-5 flex items-end justify-between border-b border-neutral-200 pb-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-neutral-900">
            ProteinGPU-Studio
          </h1>
          <p className="text-xs text-neutral-500">
            предсказание структуры · мутагенез in silico · Kabsch/RMSD на CPU и CUDA
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <nav className="flex">
            {(['workspace', 'benchmarks'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`border border-b-0 px-3 py-1.5 transition ${
                  tab === t
                    ? 'border-neutral-900 bg-neutral-900 font-medium text-white'
                    : 'border-neutral-200 text-neutral-500 hover:border-neutral-900 hover:text-neutral-900'
                }`}
              >
                {t === 'workspace' ? 'Рабочая область' : 'Бенчмарки'}
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
            title={health === 'ok' ? 'бэкенд доступен' : health === 'down' ? 'бэкенд недоступен — запустите uvicorn' : 'проверка…'}
          />
        </div>
      </header>

      {tab === 'workspace' ? <WorkspacePage /> : <BenchmarksPage />}
    </div>
  )
}