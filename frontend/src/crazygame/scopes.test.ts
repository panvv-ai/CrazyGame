import { describe, expect, it } from 'vitest'

import {
  defaultScope,
  kindForScope,
  scopesForKind,
  searchFiltersForScope,
} from './scopes'

describe('scope navigation', () => {
  it('uses the first scope for each watchlist kind', () => {
    expect(defaultScope('stock')).toBe('stock_cn')
    expect(defaultScope('fund')).toBe('fund_listed')
  })

  it('maps every scope back to its top-level watchlist kind', () => {
    expect(kindForScope('stock_hk')).toBe('stock')
    expect(kindForScope('fund_open_end')).toBe('fund')
  })

  it('keeps stock markets and fund vehicles in separate tab groups', () => {
    expect(scopesForKind('stock').map((option) => option.scope)).toEqual([
      'stock_cn',
      'stock_hk',
      'stock_us',
    ])
    expect(scopesForKind('fund').map((option) => option.scope)).toEqual([
      'fund_listed',
      'fund_open_end',
    ])
  })

  it('builds exact search filters for each scope', () => {
    expect(searchFiltersForScope('stock_us')).toEqual({
      market: 'US',
      asset_type: 'stock',
    })
    expect(searchFiltersForScope('fund_open_end')).toEqual({
      market: 'FUND',
      asset_type: 'open_end_fund',
    })
  })
})
