import { useEffect, useRef } from 'react'

export function useVisiblePolling(callback: () => void, intervalMs = 30_000) {
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    const run = () => {
      if (document.visibilityState === 'visible') callbackRef.current()
    }
    const timer = window.setInterval(run, intervalMs)
    document.addEventListener('visibilitychange', run)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', run)
    }
  }, [intervalMs])
}
