import { describe, expect, it } from 'vitest'

import {
  chartRangeDays,
  currencyTotals,
  formatPercent,
  instrumentScope,
  latestSeriesChange,
  moveItem,
  portfolioCurrencySnapshots,
  resolveInitialLanguage,
  seriesViewState,
} from './lib'

describe('resolveInitialLanguage', () => {
  it('defaults to Chinese when no preference is stored', () => {
    expect(resolveInitialLanguage(null)).toBe('zh-CN')
  })

  it('keeps a supported stored preference', () => {
    expect(resolveInitialLanguage('en-US')).toBe('en-US')
  })

  it('falls back to Chinese for an unsupported preference', () => {
    expect(resolveInitialLanguage('fr-FR')).toBe('zh-CN')
  })
})

describe('formatPercent', () => {
  it('keeps a sign for positive values', () => {
    expect(formatPercent(1.2)).toBe('+1.20%')
  })
})

describe('chartRangeDays', () => {
  it('maps human range names to data windows', () => {
    expect(chartRangeDays('1m')).toBe(31)
    expect(chartRangeDays('1y')).toBe(365)
    expect(chartRangeDays('3y')).toBe(1095)
  })
})

describe('currencyTotals', () => {
  it('keeps currencies separate', () => {
    expect(
      currencyTotals([
        { currency: 'CNY', market_value: 100 },
        { currency: 'CNY', market_value: 250 },
        { currency: 'USD', market_value: 20 },
      ])
    ).toEqual({ CNY: 350, USD: 20 })
  })
})

describe('instrumentScope', () => {
  it('separates stocks by market', () => {
    expect(instrumentScope({ market: 'CN', asset_type: 'stock' })).toBe('stock_cn')
    expect(instrumentScope({ market: 'HK', asset_type: 'stock' })).toBe('stock_hk')
    expect(instrumentScope({ market: 'US', asset_type: 'stock' })).toBe('stock_us')
  })

  it('separates listed and open-end funds', () => {
    expect(instrumentScope({ market: 'CN', asset_type: 'listed_etf' })).toBe(
      'fund_listed'
    )
    expect(instrumentScope({ market: 'FUND', asset_type: 'open_end_fund' })).toBe(
      'fund_open_end'
    )
  })
})

describe('moveItem', () => {
  it('moves an item to the drop target position', () => {
    const items = [{ id: 1 }, { id: 2 }, { id: 3 }]

    expect(moveItem(items, 3, 1).map((item) => item.id)).toEqual([3, 1, 2])
    expect(moveItem(items, 1, 3).map((item) => item.id)).toEqual([2, 1, 3])
    expect(items.map((item) => item.id)).toEqual([1, 2, 3])
  })

  it('keeps the original order when source and target match', () => {
    const items = [{ id: 1 }, { id: 2 }]

    expect(moveItem(items, 2, 2)).toBe(items)
  })
})

describe('portfolioCurrencySnapshots', () => {
  it('weights today changes by market value inside each currency', () => {
    expect(
      portfolioCurrencySnapshots([
        {
          currency: 'CNY',
          market_value: 100,
          quote: { change_pct: 2 },
        },
        {
          currency: 'CNY',
          market_value: 300,
          quote: { change_pct: -1 },
        },
        {
          currency: 'USD',
          market_value: 50,
          quote: { change_pct: 4 },
        },
      ])
    ).toEqual([
      {
        currency: 'CNY',
        dayChange: -0.25,
        coverage: 1,
        marketValue: 400,
      },
      {
        currency: 'USD',
        dayChange: 4,
        coverage: 1,
        marketValue: 50,
      },
    ])
  })

  it('reports zero coverage when a holding has no usable quote', () => {
    expect(
      portfolioCurrencySnapshots([
        {
          currency: 'USD',
          market_value: 120,
          quote: null,
        },
      ])
    ).toEqual([
      {
        currency: 'USD',
        dayChange: null,
        coverage: 0,
        marketValue: 120,
      },
    ])
  })
})

describe('seriesViewState', () => {
  it('does not stay loading after an empty or failed request', () => {
    expect(seriesViewState([], true, '')).toBe('loading')
    expect(seriesViewState([], false, '')).toBe('empty')
    expect(seriesViewState([], false, 'network failed')).toBe('error')
  })

  it('renders a chart once at least two points are available', () => {
    expect(
      seriesViewState(
        [
          { date: '2026-11-05', value: 100 },
          { date: '2026-11-06', value: 101 },
        ],
        false,
        ''
      )
    ).toBe('ready')
  })
})

describe('latestSeriesChange', () => {
  it('uses the latest two points when a quote has no daily change', () => {
    expect(
      latestSeriesChange([
        { date: '2026-11-05', value: 100 },
        { date: '2026-11-06', value: 102 },
      ])
    ).toBeCloseTo(2)
  })

  it('returns null when the series cannot produce a percentage', () => {
    expect(latestSeriesChange([])).toBeNull()
    expect(
      latestSeriesChange([
        { date: '2026-11-05', value: 0 },
        { date: '2026-11-06', value: 1 },
      ])
    ).toBeNull()
  })

  it('ignores points that are too far apart to represent a daily move', () => {
    expect(
      latestSeriesChange([
        { date: '2026-10-28', value: 100 },
        { date: '2026-11-06', value: 92 },
      ])
    ).toBeNull()
  })
})

