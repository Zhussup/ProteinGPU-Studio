import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { LanguageProvider } from './i18n'
import { ThemeProvider } from './state/theme'
import { WorkspaceProvider } from './state/workspace'

// Порядок провайдеров важен: WorkspaceProvider использует useNavigate(),
// поэтому обязан быть внутри BrowserRouter. LanguageProvider роутерных
// хуков не трогает и стоит снаружи. ThemeProvider — самый внешний: тему
// читают и провайдеры, и листьевые компоненты (Plotly/canvas/3dmol).
// 提供者的顺序很重要：WorkspaceProvider 使用 useNavigate()，
// 因此必须位于 BrowserRouter 内部。LanguageProvider 不涉及路由钩子，放在外层。
// ThemeProvider 最外层：主题既被提供者读取，也被叶子组件读取
// （Plotly/canvas/3dmol）。
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <LanguageProvider>
        <BrowserRouter>
          <WorkspaceProvider>
            <App />
          </WorkspaceProvider>
        </BrowserRouter>
      </LanguageProvider>
    </ThemeProvider>
  </StrictMode>,
)
