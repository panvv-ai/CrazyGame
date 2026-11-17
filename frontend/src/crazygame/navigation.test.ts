import { describe, expect, it } from 'vitest'

import { primaryNavigation } from './navigation'

describe('primary navigation', () => {
  it('keeps the product loop in the mobile bottom bar', () => {
    expect(primaryNavigation.map((item) => item.path)).toEqual([
      '/',
      '/watchlist',
      '/groups',
      '/holdings',
      '/alerts',
    ])
  })

  it('keeps AI and settings in the utility controls', () => {
    expect(primaryNavigation.some((item) => item.path === '/ai')).toBe(false)
    expect(primaryNavigation.some((item) => item.path === '/settings')).toBe(false)
  })
})
