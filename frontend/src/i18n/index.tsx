// i18n: tiny context-based translations (ru / en / zh), no runtime dependency.
// The dictionaries are typed against ru (the source of truth), so a missing
// key in en/zh is a compile error; t() falls back to ru at run time. The
// choice persists in localStorage ('ui-lang') and drives <html lang>.
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

// api.ts reads this per request so backend-generated texts (summaries, stage
// messages, preset descriptions) arrive in the active UI language.
export function currentLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'ru' || v === 'en' || v === 'zh') return v
  } catch { /* private mode / blocked storage */ }
  return 'ru'
}

function initialLang(): Lang {
  return currentLang()
}

export type Interp = Record<string, string | number>

// translation function type, passed down into canvas draw helpers
export type TFn = (key: Key, params?: Interp) => string

function interpolate(tpl: string, params?: Interp): string {
  if (!params) return tpl
  return tpl.replace(/\{(\w+)\}/g, (m, key) => (key in params ? String(params[key]) : m))
}

interface I18n {
  lang: Lang
  setLang: (l: Lang) => void
  t: TFn
  tl: (key: Key) => string[] // paragraph lists (help texts)
}

const Ctx = createContext<I18n | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try { localStorage.setItem(STORAGE_KEY, l) } catch { /* ignore */ }
  }, [])

  // keep <html lang> in sync with the active locale
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

// renderBold: dictionary paragraphs may carry **bold** spans; split into
// text/<b> nodes so help texts stay plain data in all three locales.
export function renderBold(text: string): ReactNode[] {
  return text.split('**').map((part, i) => (i % 2 === 1 ? <b key={i}>{part}</b> : part))
}

export type { Key }