// i18n: крошечные переводы на контексте (ru / en / zh), без рантайм-зависимостей.
// Словари типизированы от ru (источник истины), поэтому отсутствующий ключ
// в en/zh — ошибка компиляции; t() в рантайме откатывается на ru. Выбор
// сохраняется в localStorage ('ui-lang') и управляет <html lang>.
// i18n：基于 context 的轻量翻译（ru / en / zh），无运行时依赖。
// 字典以 ru（事实标准）做类型约束，en/zh 缺键即编译错误；
// t() 在运行时回退到 ru。选择持久化在 localStorage（'ui-lang'），
// 并同步到 <html lang>。
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react'
import { ru, type Dict, type Key } from './ru'
import { en } from './en'
import { zh } from './zh'

export type Lang = 'ru' | 'en' | 'zh'

export const LOCALES: Record<Lang, { label: string; htmlLang: string }> = {
  ru: { label: 'RU', htmlLang: 'ru' },
  en: { label: 'EN', htmlLang: 'en' },
  zh: { label: '中文', htmlLang: 'zh' },
}

const DICTS: Record<Lang, Dict> = { ru, en, zh }

const STORAGE_KEY = 'ui-lang'

// api.ts читает это на каждый запрос, чтобы сгенерированные бэкендом тексты
// (сводки, сообщения этапов, описания пресетов) приходили на активном языке UI.
// api.ts 每次请求都读取它，使后端生成的文本（摘要、阶段消息、预设描述）
// 以当前 UI 语言返回。
export function currentLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'ru' || v === 'en' || v === 'zh') return v
  } catch { /* приватный режим / заблокированное хранилище */ }
  return 'ru'
}

function initialLang(): Lang {
  return currentLang()
}

export type Interp = Record<string, string | number>

// тип функции перевода, пробрасывается вниз в хелперы отрисовки canvas
// 翻译函数类型，向下传递给 canvas 绘制辅助函数
export type TFn = (key: Key, params?: Interp) => string

function interpolate(tpl: string, params?: Interp): string {
  if (!params) return tpl
  return tpl.replace(/\{(\w+)\}/g, (m, key) => (key in params ? String(params[key]) : m))
}

interface I18n {
  lang: Lang
  setLang: (l: Lang) => void
  t: TFn
  tl: (key: Key) => string[] // списки абзацев (справка) | 段落列表（帮助文本）
}

const Ctx = createContext<I18n | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try { localStorage.setItem(STORAGE_KEY, l) } catch { /* игнорируем */ }
  }, [])

  // держим <html lang> синхронным с активной локалью
  // 让 <html lang> 与当前语言保持同步
  useEffect(() => {
    document.documentElement.lang = LOCALES[lang].htmlLang
  }, [lang])

  const value = useMemo<I18n>(() => {
    const dict = DICTS[lang]
    return {
      lang,
      setLang,
      t: (key, params) => {
        const tpl = dict[key] ?? ru[key]
        return typeof tpl === 'string' ? interpolate(tpl, params) : key
      },
      tl: (key) => {
        const v = dict[key] ?? ru[key]
        return Array.isArray(v) ? v : []
      },
    }
  }, [lang, setLang])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useI18n(): I18n {
  const v = useContext(Ctx)
  if (!v) throw new Error('useI18n must be used inside <LanguageProvider>')
  return v
}

// renderBold: абзацы словаря могут нести **жирные** фрагменты; режем на
// текст/<b>-узлы, чтобы справка оставалась чистыми данными во всех трёх локалях.
// renderBold：字典段落可含 **加粗** 片段；拆分为文本/<b> 节点，
// 使帮助文本在三种语言中都保持纯数据。
export function renderBold(text: string): ReactNode[] {
  return text.split('**').map((part, i) => (i % 2 === 1 ? <b key={i}>{part}</b> : part))
}

export type { Key }