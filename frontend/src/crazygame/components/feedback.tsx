import { AnimatePresence, m } from 'motion/react'
import { AlertTriangle, Check, Info, X } from 'lucide-react'
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

import { motionTokens } from '../motion'

type ToastTone = 'neutral' | 'success' | 'error'

interface ToastMessage {
  id: number
  message: string
  tone: ToastTone
}

interface ToastContextValue {
  notify: (message: string, tone?: ToastTone) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)
let toastId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const [toast, setToast] = useState<ToastMessage | null>(null)

  const dismiss = useCallback(() => setToast(null), [])
  const notify = useCallback((message: string, tone: ToastTone = 'neutral') => {
    toastId += 1
    setToast({ id: toastId, message, tone })
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(dismiss, 3600)
    return () => window.clearTimeout(timer)
  }, [dismiss, toast])

  const Icon = toast?.tone === 'success' ? Check : toast?.tone === 'error' ? AlertTriangle : Info

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      {createPortal(
        <div className="toast-region" aria-live="polite" aria-atomic="true">
          <AnimatePresence>
            {toast ? (
              <m.div
                key={toast.id}
                className={`toast toast-${toast.tone}`}
                role="status"
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 6, scale: 0.99 }}
                transition={motionTokens.quick}
              >
                <Icon size={17} aria-hidden="true" />
                <span>{toast.message}</span>
                <button
                  type="button"
                  className="toast-dismiss"
                  onClick={dismiss}
                  aria-label={t('common.dismissNotification')}
                >
                  <X size={16} />
                </button>
              </m.div>
            ) : null}
          </AnimatePresence>
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const value = useContext(ToastContext)
  if (!value) throw new Error('useToast must be used inside ToastProvider')
  return value
}
