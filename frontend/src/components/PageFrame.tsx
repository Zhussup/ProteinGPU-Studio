// PageFrame: единый каркас страницы анализа — заголовок, вводная строка,
// узкая колонка параметров и область результата. У страниц без параметров
// (сравнение, история) колонка не рендерится вовсе.
// PageFrame：分析页统一骨架——标题、导语、窄参数列与结果区。
// 无参数的页面（对比、历史）不渲染参数列。
import type { ReactNode } from 'react'
import { useI18n, type Key } from '../i18n'

export interface PageFrameProps {
  titleKey: Key
  leadKey: Key
  controls?: ReactNode
  children: ReactNode
}

export default function PageFrame({ titleKey, leadKey, controls, children }: PageFrameProps) {
  const { t } = useI18n()
  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-base font-semibold tracking-tight text-neutral-900">{t(titleKey)}</h2>
        <p className="mt-0.5 max-w-3xl text-xs text-neutral-500">{t(leadKey)}</p>
      </header>

      {controls ? (
        <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
          <div className="panel space-y-5 p-4">{controls}</div>
          <div className="space-y-5">{children}</div>
        </div>
      ) : (
        <div className="space-y-5">{children}</div>
      )}
    </div>
  )
}
