import { useEffect, useState } from 'react'
import WorkspacePage from './pages/WorkspacePage'
import BenchmarksPage from './pages/BenchmarksPage'
import { api } from './lib/api'

type Tab = 'workspace' | 'benchmarks'

export default function App() {
  const [tab, setTab] = useState<Tab>('workspace')
  const [health, setHealth] = useState<'ok' | 'down' | 'checking'>('checking')

  useEffect(() => {
    api.health()
      .then(() => setHealth('ok'))
      .catch(() => setHealth('down'))
  }, [tab])

  return (
    <div className="mx-auto max-w-7xl px-4 py-5">
      <header className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">
            ProteinGPU<span className="text-cyan-400">-Studio</span>
          </h1>
          <p className="text-xs text-slate-500">
            предсказание структуры · мутагенез in silico · Kabsch/RMSD на CPU и CUDA
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <nav className="flex gap-1">
            {(['workspace', 'benchmarks'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-lg px-3 py-1.5 transition ${
                  tab === t ? 'bg-cyan-700 text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {t === 'workspace' ? 'Рабочая область' : 'Бенчмарки'}
              </button>
            ))}
          </nav>
          <span
            className={`h-2 w-2 rounded-full ${
              health === 'ok' ? 'bg-emerald-400' : health === 'down' ? 'bg-red-500' : 'bg-slate-600'
            }`}
            title={health === 'ok' ? 'бэкенд доступен' : 'бэкенд недоступен — запустите uvicorn'}
          />
        </div>
      </header>

      {tab === 'workspace' ? <WorkspacePage /> : <BenchmarksPage />}
    </div>
  )
}