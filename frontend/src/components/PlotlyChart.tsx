// Thin Plotly wrapper, lazy-loaded so plotly.js stays out of the main chunk.
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
    return () => { /* Plotly.purge on unmount handled by react() reuse */ }
  }, [data, layout])

  useEffect(() => {
    const el = ref.current
    return () => { if (el) Plotly.purge(el) }
  }, [])

  return <div ref={ref} className="w-full" style={{ minHeight: 320 }} />
}