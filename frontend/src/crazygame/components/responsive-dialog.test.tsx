import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import '../i18n'
import { ResponsiveDialog } from './responsive-dialog'

function setMobileMatch(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: (query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }),
  })
}

describe('ResponsiveDialog', () => {
  afterEach(() => {
    cleanup()
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  it('uses a draggable sheet on narrow screens', () => {
    setMobileMatch(true)
    render(
      <ResponsiveDialog open title="Edit" onClose={() => undefined}>
        <button type="button">Save</button>
      </ResponsiveDialog>
    )

    expect(screen.getByTestId('bottom-sheet-backdrop')).toBeInTheDocument()
  })

  it('keeps a centered modal on desktop', () => {
    setMobileMatch(false)
    render(
      <ResponsiveDialog open title="Edit" onClose={() => undefined}>
        <button type="button">Save</button>
      </ResponsiveDialog>
    )

    expect(screen.getByRole('dialog', { name: 'Edit' })).toHaveClass('modal')
  })
})
