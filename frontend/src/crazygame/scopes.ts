import type { InstrumentScope } from './lib'
import type { WatchlistKind } from './types'

export interface ScopeOption {
  scope: InstrumentScope
  label: string
}

export const STOCK_SCOPES: ScopeOption[] = [
  { scope: 'stock_cn', label: 'market.CN' },
  { scope: 'stock_hk', label: 'market.HK' },
  { scope: 'stock_us', label: 'market.US' },
]

export const FUND_SCOPES: ScopeOption[] = [
  { scope: 'fund_listed', label: 'asset.listed_etf' },
  { scope: 'fund_open_end', label: 'asset.open_end_fund' },
]

export function defaultScope(kind: WatchlistKind): InstrumentScope {
  return kind === 'stock' ? 'stock_cn' : 'fund_listed'
}

export function kindForScope(scope: InstrumentScope): WatchlistKind {
  return scope.startsWith('stock_') ? 'stock' : 'fund'
}

export function scopesForKind(kind: WatchlistKind): ScopeOption[] {
  return kind === 'stock' ? STOCK_SCOPES : FUND_SCOPES
}

export function searchFiltersForScope(scope: InstrumentScope) {
  if (scope === 'stock_cn') return { market: 'CN', asset_type: 'stock' }
  if (scope === 'stock_hk') return { market: 'HK', asset_type: 'stock' }
  if (scope === 'stock_us') return { market: 'US', asset_type: 'stock' }
  if (scope === 'fund_listed') return { market: 'CN', asset_type: 'listed_etf' }
  return { market: 'FUND', asset_type: 'open_end_fund' }
}
