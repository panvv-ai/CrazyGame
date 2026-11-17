import type { ReactNode } from 'react'

import { useMediaQuery } from '../useMediaQuery'
import { BottomSheet } from './overlays'
import { Modal } from './ui'

export function ResponsiveDialog({
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
  const mobile = useMediaQuery('(max-width: 47.99rem)')
  if (mobile) {
    return (
      <BottomSheet open={open} title={title} onClose={onClose}>
        {children}
      </BottomSheet>
    )
  }
  return (
    <Modal open={open} title={title} onClose={onClose}>
      {children}
    </Modal>
  )
}
