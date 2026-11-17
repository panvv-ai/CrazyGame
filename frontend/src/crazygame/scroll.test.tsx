import { render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useScrollMemory } from './scroll'

function ScrollProbe({
  pathname,
  navigationType,
}: {
  pathname: string
  navigationType: 'POP' | 'PUSH'
}) {
  useScrollMemory(pathname, navigationType)
  return null
}

describe('useScrollMemory', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  it('restores the saved position for history navigation', () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    sessionStorage.setItem('crazygame:scroll:/watchlist', '180')

    render(<ScrollProbe pathname="/watchlist" navigationType="POP" />)

    expect(scrollTo).toHaveBeenCalledWith({ top: 180, left: 0, behavior: 'auto' })
  })

  it('starts a newly pushed page at the top', () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    sessionStorage.setItem('crazygame:scroll:/holdings', '320')

    render(<ScrollProbe pathname="/holdings" navigationType="PUSH" />)

    expect(scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' })
  })
})
