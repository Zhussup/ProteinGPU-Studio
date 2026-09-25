// useJob: опрашивает backend-задачу до done/error. Возвращает живой статус + результат.
// useJob：轮询后端任务直至完成/出错。返回实时状态 + 结果。
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { useI18n } from '../i18n'
import type { JobStatus } from './types'

export function useJob() {
  const { t } = useI18n()
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stop = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = null
    }
  }, [])

  useEffect(() => stop, [stop])

  const run = useCallback(
    (submit: () => Promise<{ job_id: string }>) => {
      stop()
      setStatus(null)
      setResult(null)
      setError(null)
      let jobId = ''
      submit()
        .then((r) => {
          jobId = r.job_id
          const poll = async () => {
            try {
              const s = await api.job(jobId)
              setStatus(s)
              if (s.status === 'done') {
                setResult(await api.result(jobId))
                return
              }
              if (s.status === 'error') {
                setError(s.error ?? t('run.jobFailed'))
                return
              }
              timer.current = setTimeout(poll, 700)
            } catch (e) {
              setError(String(e))
            }
          }
          void poll()
        })
        .catch((e) => setError(String(e)))
    },
    [stop, t],
  )

  return { status, result, error, run, running: status?.status === 'running' || status?.status === 'queued' }
}