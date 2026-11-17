import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import '../i18n'
import { BottomSheet } from './overlays'

describe('BottomSheet', () => {
  it('closes from the overlay without closing from sheet content', () => {
    const onClose = vi.fn()
    render(
      <BottomSheet open title="Edit holding" onClose={onClose}>
        <button type="button">Save</button>
      </BottomSheet>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.click(screen.getByTestId('bottom-sheet-backdrop'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('handles escape and the Android back event', () => {
    const onClose = vi.fn()
    render(
      <BottomSheet open title="Edit holding" onClose={onClose}>
        <p>Content</p>
      </BottomSheet>
    )

    fireEvent.keyDown(document, { key: 'Escape' })
    window.dispatchEvent(new Event('crazygame:back'))

    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('does not steal focus when the parent supplies a new close callback', () => {
    const { rerender } = render(
      <BottomSheet open title="Edit holding" onClose={() => undefined}>
        <input aria-label="Quantity" />
      </BottomSheet>
    )
    const quantity = screen.getByRole('textbox', { name: 'Quantity' })
    quantity.focus()

    rerender(
      <BottomSheet open title="Edit holding" onClose={() => undefined}>
        <input aria-label="Quantity" />
      </BottomSheet>
    )

    expect(quantity).toHaveFocus()
  })
})
