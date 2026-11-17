import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { clearPageCache, useCachedState } from './cache'

describe('useCachedState', () => {
  beforeEach(() => {
    clearPageCache()
  })

  it('keeps data warm when a route unmounts and mounts again', () => {
    const first = renderHook(() => useCachedState('overview', () => ({ count: 1 })))
    act(() => first.result.current[1]({ count: 4 }))
    first.unmount()

    const second = renderHook(() => useCachedState('overview', () => ({ count: 0 })))
    expect(second.result.current[0]).toEqual({ count: 4 })
  })

  it('does not reuse cached data for a different page key', () => {
    const first = renderHook(() => useCachedState('watchlist', () => ['A']))
    first.unmount()

    const second = renderHook(() => useCachedState('holdings', () => ['B']))
    expect(second.result.current[0]).toEqual(['B'])
  })

  it('switches to the matching cache when a scoped key changes', async () => {
    const { result, rerender } = renderHook(
      ({ key, initial }) => useCachedState(key, () => initial),
      { initialProps: { key: 'scope:A', initial: ['A'] } }
    )

    rerender({ key: 'scope:B', initial: ['B'] })

    await waitFor(() => {
      expect(result.current[0]).toEqual(['B'])
    })
  })
})
