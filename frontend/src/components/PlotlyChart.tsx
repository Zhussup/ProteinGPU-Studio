// Тонкая обёртка Plotly, ленивая загрузка, чтобы plotly.js не попадал в основной чанк.
// 轻量 Plotly 封装，懒加载以避免 plotly.js 进入主 chunk。
import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

export interface PlotProps {
  data: Record<string, unknown>[]
  layout: Record<string, unknown>
}

export default function PlotlyChart({ data, layout }: PlotProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    Plotly.react(ref.current, data as never, {
      responsive: true,
      ...layout,
    } as never)
    return () => { /* повторное использование react() обрабатывает purge при размонтировании */ }
  }, [data, layout])

  useEffect(() => {
    const el = ref.current
    return () => { if (el) Plotly.purge(el) }
  }, [])

  return <div ref={ref} className="w-full" style={{ minHeight: 320 }} />
}