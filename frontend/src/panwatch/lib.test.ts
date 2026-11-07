import { describe, expect, it } from 'vitest'

import {
  chartRangeDays,
  currencyTotals,
  formatPercent,
  resolveInitialLanguage,
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

