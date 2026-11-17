import { fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { Pressable, Skeleton } from './primitives'

describe('mobile primitives', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('en-US')
  })

  it('exposes a compact loading skeleton to assistive technology', () => {
    render(<Skeleton lines={3} />)

    const skeleton = screen.getByRole('status', { name: 'Loading' })
    expect(skeleton).toHaveAttribute('aria-busy', 'true')
    expect(skeleton.querySelectorAll('.skeleton-line')).toHaveLength(3)
  })

  it('dispatches an optional haptic signal only for meaningful actions', () => {
    const onHaptic = vi.fn()
    const onClick = vi.fn()
    window.addEventListener('crazygame:haptic', onHaptic)

    render(
      <Pressable haptic="selection" onClick={onClick}>
        Select instrument
      </Pressable>
    )
    fireEvent.click(screen.getByRole('button', { name: 'Select instrument' }))

    expect(onClick).toHaveBeenCalledTimes(1)
    expect(onHaptic).toHaveBeenCalledTimes(1)
    window.removeEventListener('crazygame:haptic', onHaptic)
  })
})
