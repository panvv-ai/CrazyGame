export type Market = 'CN' | 'HK' | 'US' | 'FUND'
export type AssetType = 'stock' | 'listed_etf' | 'open_end_fund'
export type WatchlistKind = 'stock' | 'fund'
export type Freshness = 'live' | 'delayed' | 'stale' | 'estimated' | 'official_nav'
export type GroupScope =
  | 'stock_cn'
  | 'stock_hk'
  | 'stock_us'
  | 'fund_listed'
  | 'fund_open_end'
  | 'mixed'

export interface Instrument {
  id?: number
  instrument_id?: number
  symbol: string
  name: string
  market: Market
  asset_type: AssetType
  currency: string
  quote_mode: 'realtime' | 'estimated' | 'nav'
}

export interface Quote {
  symbol: string
  name: string
  market: Market
  current_price: number | null
  change_pct: number | null
  previous_close: number | null
  as_of: string
  source: string
  freshness: Freshness
}

export interface WatchlistItem extends Instrument {
  id: number
  instrument_id: number
  kind: WatchlistKind
  sort_order: number
  quote?: Quote | null
}

export interface GroupMember extends Instrument {
  instrument_id: number
  weight: number
  normalized_weight: number
}

export interface AssetGroup {
  id: number
  name: string
  description: string
  scope: GroupScope
  members: GroupMember[]
  day_change_pct?: number | null
  coverage?: number
}

export interface GroupPoint {
  date: string
  value: number
  coverage: number
}

export interface GroupMemberPoint {
  instrument_id: number
  name: string
  symbol: string
  points: Array<{ date: string; value: number }>
}

export interface Holding extends Instrument {
  id: number
  instrument_id: number
  quantity: number
  average_cost: number
  note: string
  current_price: number | null
  market_value: number | null
  unrealized_pnl: number | null
  quote: Quote | null
}

export interface AlertRule extends Instrument {
  id: number
  instrument_id: number
  name: string
  metric: 'price' | 'change_pct'
  direction: 'above' | 'below'
  threshold: number
  channel_ids: number[]
  enabled: boolean
  once_per_day: boolean
  market_hours_only: boolean
  cooldown_minutes: number
  last_triggered_at: string | null
}

export interface Delivery {
  id: number
  channel_id: number
  status: string
  attempts: number
  error_code: string
}

export interface AlertHit {
  id: number
  rule_id: number
  rule_name: string
  symbol: string
  instrument_name: string
  market: Market
  triggered_at: string
  observed_value: number
  snapshot: Quote
  deliveries: Delivery[]
}

export interface NotifyChannel {
  id: number
  name: string
  type: 'feishu' | 'aliyun_sms'
  config: Record<string, unknown>
  enabled: boolean
}

export interface AISettings {
  base_url: string
  api_key: string
  model: string
}

export interface AppSettings {
  language: 'zh-CN' | 'en-US'
  ai: AISettings
  daily_review_channel_ids: number[]
  daily_review_enabled: boolean
}

export interface DailyReview {
  id: number
  trade_date: string
  language: 'zh-CN' | 'en-US'
  status: string
  title: string
  content: string
  notified_at: string | null
  error: string
  created_at: string
}

