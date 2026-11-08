import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('instrument search request', () => {
  it('sends scope filters and the current abort signal', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await api.search(
      '茅台',
      { market: 'CN', asset_type: 'stock' },
      controller.signal
    )

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(
      '/api/instruments/search?q=%E8%8C%85%E5%8F%B0&market=CN&asset_type=stock'
    )
    expect(init.signal).toBe(controller.signal)
  })
})
