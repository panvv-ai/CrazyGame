import { AnimatePresence, m, useDragControls, type PanInfo } from 'motion/react'
import { X } from 'lucide-react'
import {
  type ReactNode,
  useEffect,
  useId,
  useRef,
} from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'

import { motionTokens } from '../motion'

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function shouldDismissDrag(info: PanInfo) {
  return info.offset.y > 110 || info.velocity.y > 720
}

export function BottomSheet({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
}) {
  const { t } = useTranslation()
  const titleId = useId()
  const sheetRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const restoreFocusRef = useRef<HTMLElement | null>(null)
  const onCloseRef = useRef(onClose)
  const dragControls = useDragControls()

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const visualViewport = window.visualViewport
    const syncViewport = () => {
      if (!visualViewport) return
      document.documentElement.style.setProperty(
        '--visual-viewport-height',
        `${visualViewport.height}px`
      )
    }
    syncViewport()
    visualViewport?.addEventListener('resize', syncViewport)

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab' || !sheetRef.current) return
      const focusable = Array.from(
        sheetRef.current.querySelectorAll<HTMLElement>(focusableSelector)
      )
      if (focusable.length === 0) {
        event.preventDefault()
        sheetRef.current.focus()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    const onAndroidBack = () => onCloseRef.current()

    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('crazygame:back', onAndroidBack)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('crazygame:back', onAndroidBack)
      visualViewport?.removeEventListener('resize', syncViewport)
      document.body.style.overflow = previousOverflow
      restoreFocusRef.current?.focus()
    }
  }, [open])

  return createPortal(
    <AnimatePresence>
      {open ? (
        <m.div
          className="bottom-sheet-backdrop"
          data-testid="bottom-sheet-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={motionTokens.quick}
          onClick={(event) => {
            if (event.target === event.currentTarget) onClose()
          }}
        >
          <m.div
            ref={sheetRef}
            className="bottom-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={motionTokens.sheet.spring}
            drag="y"
            dragControls={dragControls}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0.04, bottom: 0.7 }}
            dragMomentum={false}
            onDragEnd={(_, info) => {
              if (shouldDismissDrag(info)) onClose()
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <div
              className="bottom-sheet-handle"
              onPointerDown={(event) => dragControls.start(event)}
              aria-hidden="true"
            />
            <header className="bottom-sheet-head">
              <h2 id={titleId}>{title}</h2>
              <button
                ref={closeRef}
                type="button"
                className="icon-button"
                onClick={onClose}
                aria-label={t('common.close')}
              >
                <X size={18} />
              </button>
            </header>
            <div className="bottom-sheet-content">{children}</div>
          </m.div>
        </m.div>
      ) : null}
    </AnimatePresence>,
    document.body
  )
}
