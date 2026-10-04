// ProteinCard: карточка текущего белка в сайдбаре — имя из FASTA-заголовка,
// длина, валидность. Редактирование (textarea / FASTA / пресеты) — в модалке,
// поэтому ввод существует в одном месте и доступен с любой страницы.
// ProteinCard：侧栏中的当前蛋白卡片——FASTA 头中的名称、长度、有效性。
// 编辑（textarea / FASTA / 预设）在弹窗中进行，因此输入只有一处、任意页面可用。
import { useState } from 'react'
import { useI18n } from '../i18n'
import { LIMITS, useWorkspace } from '../state/workspace'
import SequenceInput from './SequenceInput'
import Modal from './Modal'

export default function ProteinCard() {
  const { t } = useI18n()
  const { input, setInput, seq, seqOk, presets } = useWorkspace()
  const [open, setOpen] = useState(false)

  const header = input.split('\n').find((l) => l.trim().startsWith('>'))
  const name = header ? header.replace(/^>\s*/, '').trim() : null

  return (
    <div className="panel p-3">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium text-neutral-900">{t('shell.protein')}</span>
        <button
          type="button"
          data-demo="protein-edit"
          onClick={() => setOpen(true)}
          className="text-[11px] text-neutral-500 underline hover:text-neutral-900"
        >
          {t('shell.proteinEdit')}
        </button>
      </div>

      {seq.length === 0 ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="w-full text-left text-xs text-neutral-400 hover:text-neutral-700"
        >
          {t('shell.proteinEmpty')}
        </button>
      ) : (
        <>
          <div className="truncate text-xs text-neutral-900" title={name ?? undefined}>
            {name ?? '—'}
          </div>
          <div className="mono mt-0.5 truncate text-[11px] text-neutral-500">
            {seq.slice(0, 26)}{seq.length > 26 ? '…' : ''}
          </div>
          <div className={`mono mt-1 text-[11px] ${seqOk ? 'text-neutral-600' : 'text-red-700'}`}>
            {seq.length} aa {seqOk ? '' : t('seq.lenRange', { min: LIMITS.min, max: LIMITS.max })}
          </div>
        </>
      )}

      {open && (
        <Modal title={t('shell.protein')} onClose={() => setOpen(false)} wide>
          <SequenceInput
            value={input}
            onChange={setInput}
            presets={presets}
            minLen={LIMITS.min}
            maxLen={LIMITS.max}
          />
        </Modal>
      )}
    </div>
  )
}
