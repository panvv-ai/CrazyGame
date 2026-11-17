import { describe, expect, it } from 'vitest'

import { createTransferBundle, mergeTransferBundle } from './transfer'

const state = {
  version: 1,
  instruments: [
    { id: 1, symbol: '600000', name: 'A', market: 'CN', asset_type: 'stock' },
    { id: 2, symbol: '000001', name: 'B', market: 'CN', asset_type: 'stock' },
  ],
  watchlist: [{ id: 1, instrument_id: 1, kind: 'stock', sort_order: 0 }],
  groups: [{ id: 1, name: 'Core', member_ids: [{ instrument_id: 1, weight: 1 }] }],
  holdings: [{ id: 1, instrument_id: 2, quantity: 2, average_cost: 3 }],
  alerts: [{ id: 1, instrument_id: 1, channel_ids: [1], name: 'Price' }],
  alert_hits: [],
  channels: [{ id: 1, name: 'Local', type: 'local', config: {}, enabled: true }],
  settings: {
    language: 'zh-CN',
    ai: { base_url: 'https://api.example.com', api_key: 'secret', model: 'm', vision_model: '' },
    news: { enabled: true, provider: 'eastmoney', api_key: 'news-secret' },
    daily_review_enabled: true,
    daily_review_channel_ids: [1],
  },
  quotes: {},
  series: {},
  reports: [],
  sessions: [],
  reviews: [],
  next_ids: {},
}

describe('transfer bundles', () => {
  it('exports only selected modules and strips credentials when disabled', () => {
    const bundle = JSON.parse(
      createTransferBundle(JSON.stringify(state), ['watchlist', 'llm'], false)
    )

    expect(bundle.modules).toEqual(['watchlist', 'llm'])
    expect(bundle.data.watchlist).toHaveLength(1)
    expect(bundle.data.holdings).toEqual([])
    expect(bundle.data.settings.ai.api_key).toBe('')
    expect(bundle.data.settings.news.api_key).toBe('')
  })

  it('merges imported holdings without duplicating an existing instrument', () => {
    const imported = JSON.parse(
      createTransferBundle(JSON.stringify(state), ['holdings'], false)
    )
    const current = {
      ...state,
      holdings: [],
      instruments: [state.instruments[1]],
    }

    const merged = JSON.parse(
      mergeTransferBundle(JSON.stringify(current), imported, ['holdings'])
    )
    expect(merged.holdings).toHaveLength(1)
    expect(merged.holdings[0].instrument_id).toBe(2)
  })

  it('keeps the Android local notification channel when importing alerts', () => {
    const imported = {
      ...JSON.parse(createTransferBundle(JSON.stringify(state), ['alerts'], false)),
    }
    imported.data.channels = [
      { id: 7, name: 'Feishu', type: 'feishu', config: {}, enabled: true },
    ]
    imported.data.alerts = [
      {
        id: 9,
        instrument_id: 1,
        name: 'Price',
        metric: 'price',
        direction: 'above',
        threshold: 10,
        channel_ids: [7],
        enabled: true,
      },
    ]

    const merged = JSON.parse(
      mergeTransferBundle(JSON.stringify(state), imported, ['alerts'])
    )
    expect(merged.channels.some((channel: { type: string }) => channel.type === 'local')).toBe(true)
    const importedRule = merged.alerts.find((rule: { name: string }) => rule.name === 'Price')
    expect(importedRule.channel_ids).toHaveLength(1)
  })
})
