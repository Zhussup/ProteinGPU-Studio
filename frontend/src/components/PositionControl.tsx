// PositionControl: выбор одной позиции (1-based) с живым превью —
// общий элемент страниц скана и ансамбля (в структуре позицию выбирает
// MutationPicker вместе с новым остатком).
// PositionControl：选择单个位点（1-based）并实时预览——
// 位点扫描与 ensemble 页共用（结构页由 MutationPicker 连同新残基一起选择）。
import { useI18n } from '../i18n'
import { SequenceStrip } from './MutationPicker'

export interface PositionControlProps {
  sequence: string
  position: number
  onChange: (p: number) => void
}

export default function PositionControl({ sequence, position, onChange }: PositionControlProps) {
  const { t } = useI18n()
  const ok = position >= 1 && position <= sequence.length
  const wtAA = ok ? sequence[position - 1] : '?'

  return (
    <div className="space-y-2" data-demo="position">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-900">{t('mut.position')}</label>
        <span className="mono text-xs text-neutral-700">{ok ? `${wtAA}${position}` : '—'}</span>
      </div>
      <input
        type="number"
        min={1}
        max={sequence.length || undefined}
        value={position || ''}
        onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
        className="mono w-24 border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 outline-none focus:border-neutral-900"
      />
      {ok && <SequenceStrip sequence={sequence} position={position} />}
    </div>
  )
}
