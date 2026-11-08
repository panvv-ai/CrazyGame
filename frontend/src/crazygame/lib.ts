export type Language = 'zh-CN' | 'en-US'
export type ChartRange = '1m' | '3m' | '1y' | '3y' | 'all'
export type InstrumentScope =
  | 'stock_cn'
  | 'stock_hk'
  | 'stock_us'
  | 'fund_listed'
  | 'fund_open_end'

export function instrumentScope(instrument: {
  market: string
  asset_type: string
}): InstrumentScope {
  if (instrument.asset_type === 'listed_etf') return 'fund_listed'
  if (instrument.asset_type === 'open_end_fund') return 'fund_open_end'
  if (instrument.asset_type === 'stock') {
    const market = instrument.market.toLowerCase()
    if (market === 'cn' || market === 'hk' || market === 'us') {
      return `stock_${market}` as InstrumentScope
    }
  }
  throw new Error(`Unsupported instrument scope: ${instrument.market}/${instrument.asset_type}`)
}

export function resolveInitialLanguage(stored: string | null): Language {
  return stored === 'en-US' ? 'en-US' : 'zh-CN'
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

export function changeClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return 'market-flat'
  return value > 0 ? 'market-up' : 'market-down'
}

export function formatMoney(value: number | null | undefined, currency: string, language: Language): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return new Intl.NumberFormat(language, {
    style: 'currency',
    currency,
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value)
}

export function formatDateTime(value: string | null | undefined, language: Language): string {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(language, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function chartRangeDays(range: ChartRange): number {
  if (range === '1m') return 31
  if (range === '3m') return 92
  if (range === '3y') return 1095
  if (range === 'all') return 3650
  return 365
}

export function currencyTotals(
  rows: Array<{ currency: string; market_value: number | null }>
): Record<string, number> {
  const result: Record<string, number> = {}
  for (const row of rows) {
    if (row.market_value === null) continue
    result[row.currency] = (result[row.currency] ?? 0) + row.market_value
  }
  return result
}

export function moveItem<T extends { id: number }>(
  items: T[],
  sourceId: number,
  targetId: number
): T[] {
  if (sourceId === targetId) return items
  const sourceIndex = items.findIndex((item) => item.id === sourceId)
  const targetIndex = items.findIndex((item) => item.id === targetId)
  if (sourceIndex < 0 || targetIndex < 0) return items
  const next = [...items]
  const [moved] = next.splice(sourceIndex, 1)
  const insertionIndex = sourceIndex < targetIndex ? targetIndex - 1 : targetIndex
  next.splice(insertionIndex, 0, moved)
  return next
}

export function freshnessLabelKey(freshness: string): string {
  if (freshness === 'estimated') return 'freshness.estimated'
  if (freshness === 'official_nav') return 'freshness.officialNav'
  if (freshness === 'stale') return 'freshness.stale'
  if (freshness === 'delayed') return 'freshness.delayed'
  return 'freshness.live'
}

