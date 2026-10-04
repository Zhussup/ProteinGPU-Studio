// Тема оформления (light / dark): класс .dark на <html> + палитры для не-DOM графики.
// DOM перекрашивается переворотом CSS-переменных шкалы Tailwind (см. index.css) —
// одинарная правка стилей вместо правок в каждом компоненте. Plotly, canvas и
// 3dmol принимают только конкретные hex/rgb-строки — им палитру даёт PALETTE[theme].
// 主题（light / dark）：在 <html> 上切换 .dark 类 + 非 DOM 图形的调色板。
// DOM 通过翻转 Tailwind 量表的 CSS 变量整体重着色（见 index.css）——
// 一处修改即可，无需逐组件改动。Plotly、canvas 与 3dmol 只接受具体的
// hex/rgb 字符串——调色板由 PALETTE[theme] 提供。
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'ui-theme'

function initialTheme(): Theme {
  // по умолчанию светлая — детерминированно для записи демо и защиты;
  // выбор сохраняется и переживает перезагрузку
  // 默认浅色——为演示录制与答辩保持确定性；选择持久化并在刷新后保留
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'dark' || v === 'light') return v
  } catch { /* приватный режим / заблокированное хранилище */ }
  return 'light'
}

interface ThemeCtx {
  theme: Theme
  toggle: () => void
}

const Ctx = createContext<ThemeCtx | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(initialTheme)

  const toggle = useCallback(() => {
    setThemeState((cur) => {
      const next: Theme = cur === 'dark' ? 'light' : 'dark'
      try { localStorage.setItem(STORAGE_KEY, next) } catch { /* игнорируем */ }
      return next
    })
  }, [])

  // класс .dark на <html>: переворачивает переменные шкалы (index.css) и даёт
  // color-scheme: dark для нативных контролов; index.html ставит его до первой
  // отрисовки, чтобы не мигало
  // <html> 上的 .dark 类：翻转量表变量（index.css）并为原生控件启用
  // color-scheme: dark；index.html 在首次绘制前就设置它，避免闪烁
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  const value = useMemo<ThemeCtx>(() => ({ theme, toggle }), [theme, toggle])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTheme(): ThemeCtx {
  const v = useContext(Ctx)
  if (!v) throw new Error('useTheme must be used inside <ThemeProvider>')
  return v
}

// --- палитры для Plotly / canvas / 3dmol / inline-SVG ---
// --- Plotly / canvas / 3dmol / 内联 SVG 的调色板 ---
// Имена полей — по роли, значения соответствуют перевёрнутой шкале Tailwind
// из index.css, чтобы график и его панель выглядели одной системой.
// 字段名对应角色；取值与 index.css 中翻转后的 Tailwind 量表一致，
// 保证图表面板与其中的图表属于同一体系。
export interface ChartColors {
  ink: string // данные, основные линии / 数据、主线
  ink2: string // вторая серия, буквы треков / 第二序列、轨道字母
  gray: string // нейтральная серия / 中性序列
  faint: string // тихие подписи, WT-линия / 弱化标注、WT 线
  muted: string // шрифт осей Plotly / Plotly 坐标轴字体
  dim: string // canvas-подписи / canvas 标注
  accent: string // фирменный красный（мутация, тревога）/ 品牌红（突变、警示）
  mut: string // cartoon мутанта / 突变体 cartoon 颜色
  wt: string // WT cartoon / WT cartoon 颜色
  grid: string // линии сетки / 网格线
  border: string // волосяные рамки осей / 坐标轴细边框
  paper: string // фон Plotly и canvas / Plotly、canvas 底色
  surface: string // лёгкая подложка / 浅底
  band: string // полоса local-window, hairline треков / local-window 条带、轨道细线
  scaleFrom: string // ноль тепловой шкалы / 热度色带零点
}

const LIGHT: ChartColors = {
  ink: '#111111', ink2: '#374151', gray: '#6b7280', faint: '#9ca3af',
  muted: '#525252', dim: '#737373',
  accent: '#b91c1c', mut: '#1f2937', wt: '#9ca3af',
  grid: '#e5e5e5', border: '#d4d4d4',
  paper: '#ffffff', surface: '#f5f5f5', band: '#f0f0f0',
  scaleFrom: '#ffffff',
}

const DARK: ChartColors = {
  ink: '#f0f0f0', ink2: '#b5b5b5', gray: '#9aa0a6', faint: '#9ca3af',
  muted: '#a3a3a3', dim: '#8f8f8f',
  accent: '#ef4444', mut: '#e2e2e2', wt: '#9ca3af',
  grid: '#2a2a2a', border: '#3a3a3a',
  paper: '#171717', surface: '#1f1f1f', band: '#262626',
  scaleFrom: '#1f1f1f',
}

// стабильно по ссылке для каждого theme — можно смело ставить в deps эффектов
// 每个 theme 对应稳定的对象引用——可安全用于 effect 依赖
export const PALETTE: Record<Theme, ChartColors> = { light: LIGHT, dark: DARK }