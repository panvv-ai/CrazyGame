import type {
  AIChatMessage,
  AIChatSession,
  AIChatSessionDetail,
  AIDecisionReport,
  AIReportRecord,
  AISseEvent,
  AlertRule,
  AppSettings,
  AssetGroup,
  GroupMember,
  GroupPoint,
  Holding,
  Instrument,
  NotifyChannel,
  Quote,
  RecognizedInstrument,
  WatchlistItem,
  WatchlistKind,
} from './types'
import { instrumentScope } from './lib'
import {
  cancelNativeRequest,
  nativeAiStream,
  nativeBridge,
  nativeHttpRequest,
} from './native'

const LOCAL_NOTIFICATION_CHANNEL_ID = 1
const CJK_FUND = '\u57fa\u91d1'
const CJK_SHANGHAI = '\u6caa'
const CJK_SHENZHEN = '\u6df1'
const CJK_BEIJING = '\u5317'
const CJK_HONG_KONG = '\u6e2f'
const CJK_UNITED_STATES = '\u7f8e'
let cachedState: MobileState | null = null

interface StoredInstrument extends Instrument {
  id: number
  created_at: string
}

interface StoredWatchlist {
  id: number
  instrument_id: number
  kind: WatchlistKind
  sort_order: number
}

interface StoredGroup {
  id: number
  name: string
  description: string
  sort_order: number
  member_ids: Array<{ instrument_id: number; weight: number }>
  updated_at: string
}

interface StoredHolding {
  id: number
  instrument_id: number
  quantity: number
  average_cost: number
  note: string
  updated_at: string
}

interface StoredAlert {
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
  created_at: string
  updated_at: string
}

interface StoredHit {
  id: number
  rule_id: number
  instrument_id: number
  triggered_at: string
  observed_value: number
  snapshot: Quote | null
}

interface StoredSession {
  id: string
  title: string
  active_instrument_id: number | null
  created_at: string
  updated_at: string
  messages: AIChatMessage[]
}

interface MobileState {
  version: 1
  instruments: StoredInstrument[]
  watchlist: StoredWatchlist[]
  groups: StoredGroup[]
  holdings: StoredHolding[]
  alerts: StoredAlert[]
  alert_hits: StoredHit[]
  channels: NotifyChannel[]
  settings: AppSettings
  quotes: Record<string, Quote>
  series: Record<string, Array<{ date: string; value: number }>>
  reviews: unknown[]
  reports: AIReportRecord[]
  sessions: StoredSession[]
  next_ids: Record<string, number>
}

const defaultSettings: AppSettings = {
  language: 'zh-CN',
  ai: { base_url: 'https://api.openai.com/v1', api_key: '', model: '', vision_model: '' },
  news: { enabled: true, provider: 'eastmoney', api_key: '' },
  daily_review_channel_ids: [LOCAL_NOTIFICATION_CHANNEL_ID],
  daily_review_enabled: true,
}

function emptyState(): MobileState {
  return {
    version: 1,
    instruments: [],
    watchlist: [],
    groups: [],
    holdings: [],
    alerts: [],
    alert_hits: [],
    channels: [
      {
        id: LOCAL_NOTIFICATION_CHANNEL_ID,
        name: 'Device notifications',
        type: 'local',
        config: {},
        enabled: true,
      },
    ],
    settings: defaultSettings,
    quotes: {},
    series: {},
    reviews: [],
    reports: [],
    sessions: [],
    next_ids: {},
  }
}

function readState(): MobileState {
  const bridge = nativeBridge()
  if (!bridge) throw new Error('native_bridge_unavailable')
  if (cachedState) return cachedState
  const raw = bridge.readState()
  if (!raw) {
    cachedState = emptyState()
    return cachedState
  }
  try {
    const parsed = JSON.parse(raw) as Partial<MobileState>
    const fallback = emptyState()
    cachedState = {
      ...fallback,
      ...parsed,
      settings: {
        ...fallback.settings,
        ...(parsed.settings ?? {}),
        ai: { ...fallback.settings.ai, ...(parsed.settings?.ai ?? {}) },
        news: { ...fallback.settings.news, ...(parsed.settings?.news ?? {}) },
      },
      channels: parsed.channels?.length ? parsed.channels : fallback.channels,
      quotes: parsed.quotes ?? {},
      series: parsed.series ?? {},
      next_ids: parsed.next_ids ?? {},
    }
  } catch {
    cachedState = emptyState()
  }
  return cachedState
}

function saveState(state: MobileState) {
  const bridge = nativeBridge()
  if (!bridge) throw new Error('native_bridge_unavailable')
  cachedState = state
  bridge.writeState(JSON.stringify(state))
}

export function initializeMobileRuntime() {
  const state = readState()
  nativeBridge()?.scheduleAlerts(
    state.alerts.some((rule) => rule.enabled),
    15
  )
}

function nextId(state: MobileState, table: string) {
  const rows = (state as unknown as Record<string, unknown>)[table]
  const ids = Array.isArray(rows)
    ? (rows as Array<{ id?: number | string }>).map((item) =>
        typeof item.id === 'number' ? item.id : 0
      )
    : []
  const current = Math.max(state.next_ids[table] ?? 0, ...ids, 0)
  const next = current + 1
  state.next_ids[table] = next
  return next
}

function instrumentKey(instrument: Pick<Instrument, 'symbol' | 'market' | 'asset_type'>) {
  return `${instrument.market}:${instrument.symbol}:${instrument.asset_type}`
}

function findInstrument(state: MobileState, id: number) {
  return state.instruments.find((item) => item.id === id)
}

function normalizeInstrument(state: MobileState, input: Instrument): StoredInstrument {
  const key = instrumentKey(input)
  const existing = state.instruments.find((item) => instrumentKey(item) === key)
  if (existing) {
    existing.name = input.name || existing.name
    existing.quote_id = input.quote_id || existing.quote_id
    return existing
  }
  const stored: StoredInstrument = {
    ...input,
    id: nextId(state, 'instruments'),
    created_at: new Date().toISOString(),
  }
  state.instruments.push(stored)
  return stored
}

function instrumentPublic(item: StoredInstrument): Instrument {
  return {
    id: item.id,
    instrument_id: item.id,
    symbol: item.symbol,
    name: item.name,
    market: item.market,
    asset_type: item.asset_type,
    currency: item.currency,
    quote_mode: item.quote_mode,
    quote_id: item.quote_id,
  }
}

async function httpJson<T>(
  url: string,
  headers: Record<string, string> = {}
): Promise<T> {
  const response = await nativeHttpRequest('GET', url, {
    'User-Agent': 'Mozilla/5.0 CrazyGame Android',
    ...headers,
  })
  if (response.status < 200 || response.status >= 300) {
    throw new Error(`market_http_${response.status}`)
  }
  return JSON.parse(response.body) as T
}

function normalizeSearchSymbol(raw: string, market: string) {
  let code = raw.trim().toUpperCase()
  for (const prefix of ['SH', 'SZ', 'BJ', 'US', 'HK']) {
    if (code.startsWith(prefix)) {
      code = code.slice(prefix.length)
      break
    }
  }
  if (code.includes('.')) code = code.split('.', 1)[0]
  if (market === 'HK') code = code.padStart(5, '0')
  if (market === 'FUND') code = code.padStart(6, '0')
  return code
}

function classifySearchItem(row: Record<string, unknown>): Instrument | null {
  const classify = String(row.Classify ?? '').trim()
  const securityType = String(row.SecurityTypeName ?? '').trim()
  const marketType = String(row.MarketType ?? '').trim()
  const quoteId = String(row.QuoteID ?? '').trim()
  const rawCode = String(row.Code ?? '').trim()
  if (!rawCode) return null
  const listedFund =
    /^\d{6}$/.test(rawCode) &&
    ['5', '15', '16', '18'].some((prefix) => rawCode.startsWith(prefix))
  if (
    classify === 'Fund' ||
    classify === 'ETF' ||
    classify === 'OTCFUND' ||
    securityType.includes(CJK_FUND)
  ) {
    if (classify === 'ETF' || securityType.toUpperCase().includes('ETF') || listedFund) {
      return {
        symbol: normalizeSearchSymbol(rawCode, 'CN'),
        name: String(row.Name ?? rawCode),
        market: 'CN',
        asset_type: 'listed_etf',
        currency: 'CNY',
        quote_mode: 'realtime',
        quote_id: quoteId || undefined,
      }
    }
    return {
      symbol: normalizeSearchSymbol(rawCode, 'FUND'),
      name: String(row.Name ?? rawCode),
      market: 'FUND',
      asset_type: 'open_end_fund',
      currency: 'CNY',
      quote_mode: 'estimated',
      quote_id: quoteId || undefined,
    }
  }
  if (
    classify === 'AStock' ||
    classify === 'BJStock' ||
    [CJK_SHANGHAI, CJK_SHENZHEN, CJK_BEIJING].some((marker) =>
      securityType.includes(marker)
    )
  ) {
    return {
      symbol: normalizeSearchSymbol(rawCode, 'CN'),
      name: String(row.Name ?? rawCode),
      market: 'CN',
      asset_type: 'stock',
      currency: 'CNY',
      quote_mode: 'realtime',
      quote_id: quoteId || undefined,
    }
  }
  if (classify === 'HKStock' || securityType.includes(CJK_HONG_KONG)) {
    return {
      symbol: normalizeSearchSymbol(rawCode, 'HK'),
      name: String(row.Name ?? rawCode),
      market: 'HK',
      asset_type: 'stock',
      currency: 'HKD',
      quote_mode: 'realtime',
      quote_id: quoteId || undefined,
    }
  }
  if (classify === 'UsStock' || securityType.includes(CJK_UNITED_STATES)) {
    return {
      symbol: normalizeSearchSymbol(rawCode, 'US'),
      name: String(row.Name ?? rawCode),
      market: 'US',
      asset_type: 'stock',
      currency: 'USD',
      quote_mode: 'realtime',
      quote_id: quoteId || undefined,
    }
  }
  if (marketType === '1' || marketType === '2') {
    return null
  }
  return null
}

async function searchInstruments(query: string, market = '', assetType = '') {
  const params = new URLSearchParams({
    input: query,
    type: '14',
    count: '80',
  })
  const payload = await httpJson<{
    QuotationCodeTable?: { Data?: Array<Record<string, unknown>> }
  }>(`https://searchapi.eastmoney.com/api/suggest/get?${params}`)
  const rows = payload.QuotationCodeTable?.Data ?? []
  const seen = new Set<string>()
  const output: Instrument[] = []
  for (const row of rows) {
    const item = classifySearchItem(row)
    if (!item) continue
    if (market && item.market !== market) continue
    if (assetType && item.asset_type !== assetType) continue
    const key = instrumentKey(item)
    if (seen.has(key)) continue
    seen.add(key)
    output.push(item)
    if (output.length >= 20) break
  }
  return output
}

function tencentSymbol(item: StoredInstrument) {
  if (item.market === 'HK') return `hk${item.symbol}`
  if (item.market === 'US') return `us${item.symbol}`
  if (item.market === 'CN') {
    if (/^[5689]/.test(item.symbol)) return `sh${item.symbol}`
    if (/^[48]/.test(item.symbol)) return `bj${item.symbol}`
    return `sz${item.symbol}`
  }
  return ''
}

async function fetchListedQuotes(items: StoredInstrument[]): Promise<Record<string, Quote>> {
  const listed = items.filter((item) => item.market !== 'FUND')
  const symbols = [...new Set(listed.map(tencentSymbol).filter(Boolean))]
  if (!symbols.length) return {}
  const response = await nativeHttpRequest(
    'GET',
    `https://qt.gtimg.cn/q=${symbols.join(',')}`,
    { Referer: 'https://gu.qq.com/' }
  )
  if (response.status < 200 || response.status >= 300) return {}
  const output: Record<string, Quote> = {}
  for (const line of response.body.split(';')) {
    if (!line.includes('="')) continue
    const value = line.split('="', 2)[1]?.replace(/";?\s*$/, '')
    const parts = value?.split('~') ?? []
    if (parts.length < 35) continue
    const symbol = String(parts[2] ?? '').split('.')[0]
    const item = listed.find((candidate) => candidate.symbol === symbol)
    if (!item) continue
    output[instrumentKey(item)] = {
      symbol: item.symbol,
      name: parts[1] || item.name,
      market: item.market,
      current_price: numberOrNull(parts[3]),
      change_pct: numberOrNull(parts[32]),
      previous_close: numberOrNull(parts[4]),
      as_of: new Date().toISOString(),
      source: 'tencent',
      freshness: 'live',
    }
  }
  return output
}

async function fetchEastmoneyQuote(item: StoredInstrument): Promise<Quote | null> {
  const secid = item.quote_id || deriveEastmoneySecid(item)
  if (!secid) return null
  const fields =
    'f43,f44,f45,f46,f47,f48,f50,f57,f58,f59,f60,f116,f117,f168,f169,f170'
  const payload = await httpJson<{
    data?: Record<string, number | string | null>
  }>(
    `https://push2.eastmoney.com/api/qt/stock/get?secid=${encodeURIComponent(secid)}&fields=${fields}`,
    { Referer: 'https://quote.eastmoney.com/' }
  )
  const data = payload.data
  if (!data || data.f43 == null) return null
  const decimals = numberOrNull(data.f59) ?? 2
  return {
    symbol: String(data.f57 ?? item.symbol),
    name: String(data.f58 ?? item.name),
    market: item.market,
    current_price: scaled(data.f43, decimals),
    previous_close: scaled(data.f60, decimals),
    change_pct: percent(data.f170),
    as_of: new Date().toISOString(),
    source: 'eastmoney',
    freshness: 'live',
  }
}

async function fetchFundQuote(item: StoredInstrument): Promise<Quote | null> {
  const response = await nativeHttpRequest(
    'GET',
    `https://fundgz.1234567.com.cn/js/${item.symbol}.js`,
    { Referer: 'https://fund.eastmoney.com/' }
  )
  const match = response.body.match(/jsonpgz\((.*)\)\s*;?/)
  if (!match) return null
  const data = JSON.parse(match[1]) as Record<string, string>
  const current = numberOrNull(data.gsz)
  const previous = numberOrNull(data.dwjz)
  return {
    symbol: item.symbol,
    name: data.name || item.name,
    market: 'FUND',
    current_price: current ?? previous,
    previous_close: previous,
    change_pct: numberOrNull(data.gszzl),
    as_of: data.gztime || data.jzrq || new Date().toISOString(),
    source: 'eastmoney_fund',
    freshness: current != null ? 'estimated' : 'official_nav',
  }
}

function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === '' || value === '-') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function scaled(value: unknown, decimals: number) {
  const parsed = numberOrNull(value)
  return parsed === null ? null : parsed / 10 ** decimals
}

function percent(value: unknown) {
  const parsed = numberOrNull(value)
  return parsed === null ? null : parsed / 100
}

function deriveEastmoneySecid(item: StoredInstrument) {
  if (item.quote_id) return item.quote_id
  if (item.market === 'HK') return `116.${item.symbol}`
  if (item.market === 'US') return `105.${item.symbol}`
  if (item.market === 'CN') {
    return `${/^[5689]/.test(item.symbol) ? '1' : '0'}.${item.symbol}`
  }
  return ''
}

async function quotesFor(state: MobileState, items: StoredInstrument[]) {
  const wanted = new Map(items.map((item) => [instrumentKey(item), item]))
  let fetched: Record<string, Quote> = {}
  try {
    fetched = await fetchListedQuotes(items)
  } catch {
    fetched = {}
  }
  for (const item of items) {
    const key = instrumentKey(item)
    if (fetched[key]) continue
    try {
      const quote =
        item.market === 'FUND'
          ? await fetchFundQuote(item)
          : await fetchEastmoneyQuote(item)
      if (quote) fetched[key] = quote
    } catch {
      // Fall back to the last cached value below.
    }
  }
  const output: Record<string, Quote> = {}
  for (const key of wanted.keys()) {
    const quote = fetched[key] ?? state.quotes[key]
    if (!quote) continue
    const next = fetched[key]
      ? quote
      : { ...quote, freshness: 'stale' as const }
    output[key] = next
    state.quotes[key] = next
  }
  return output
}

async function seriesFor(
  state: MobileState,
  item: StoredInstrument,
  days: number
): Promise<Array<{ date: string; value: number }>> {
  const cacheKey = `${instrumentKey(item)}:${days}`
  if (state.series[cacheKey]?.length) return state.series[cacheKey]
  try {
    let points: Array<{ date: string; value: number }> = []
    if (item.market === 'FUND') {
      const payload = await httpJson<{
        Data?: {
          LSJZList?: Array<{ FSRQ?: string; DWJZ?: string }>
        }
      }>(
        `https://api.fund.eastmoney.com/f10/lsjz?fundCode=${item.symbol}&pageIndex=1&pageSize=${days}`,
        { Referer: `https://fundf10.eastmoney.com/jjjz_${item.symbol}.html` }
      )
      points = (payload.Data?.LSJZList ?? [])
        .map((row) => ({
          date: String(row.FSRQ ?? ''),
          value: Number(row.DWJZ),
        }))
        .filter((point) => point.date && Number.isFinite(point.value))
        .reverse()
    } else {
      const secid = deriveEastmoneySecid(item)
      const payload = await httpJson<{
        data?: { klines?: string[] }
      }>(
        `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=${encodeURIComponent(secid)}&klt=101&fqt=1&lmt=${days}&end=20500101&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f53`,
        { Referer: 'https://quote.eastmoney.com/' }
      )
      points = (payload.data?.klines ?? [])
        .map((row) => row.split(','))
        .map(([date, close]) => ({ date, value: Number(close) }))
        .filter((point) => point.date && Number.isFinite(point.value))
    }
    if (points.length) state.series[cacheKey] = points
    return points
  } catch {
    return state.series[cacheKey] ?? []
  }
}

function normalizedMembers(state: MobileState, group: StoredGroup) {
  const members = group.member_ids
    .map((member) => ({
      member,
      instrument: findInstrument(state, member.instrument_id),
    }))
    .filter(
      (entry): entry is { member: { instrument_id: number; weight: number }; instrument: StoredInstrument } =>
        Boolean(entry.instrument)
    )
  const total = members.reduce((sum, entry) => sum + Math.max(0, entry.member.weight), 0)
  return members.map((entry) => ({
    ...entry,
    normalized: total > 0 ? Math.max(0, entry.member.weight) / total : 0,
  }))
}

function groupScope(state: MobileState, group: StoredGroup) {
  const scopes = new Set(
    normalizedMembers(state, group).map((entry) => instrumentScope(entry.instrument))
  )
  return scopes.size === 1 ? [...scopes][0] : 'mixed'
}

async function groupDict(state: MobileState, group: StoredGroup): Promise<AssetGroup> {
  const entries = normalizedMembers(state, group)
  const quotes = await quotesFor(state, entries.map((entry) => entry.instrument))
  let availableWeight = 0
  let weightedChange = 0
  const members: GroupMember[] = entries.map((entry) => {
    const quote = quotes[instrumentKey(entry.instrument)]
    if (quote?.change_pct != null) {
      availableWeight += entry.normalized
      weightedChange += entry.normalized * quote.change_pct
    }
    return {
      ...instrumentPublic(entry.instrument),
      instrument_id: entry.instrument.id,
      weight: entry.member.weight,
      normalized_weight: entry.normalized,
    }
  })
  return {
    id: group.id,
    name: group.name,
    description: group.description,
    scope: groupScope(state, group) as AssetGroup['scope'],
    members,
    day_change_pct: availableWeight > 0 ? weightedChange / availableWeight : null,
    coverage: availableWeight,
  }
}

function requestBody(init: RequestInit): Record<string, unknown> {
  if (!init.body) return {}
  if (typeof init.body !== 'string') throw new Error('unsupported_native_body')
  return JSON.parse(init.body) as Record<string, unknown>
}

function watchlistItem(
  item: StoredWatchlist,
  instrument: StoredInstrument,
  quote?: Quote
): WatchlistItem {
  return {
    ...instrumentPublic(instrument),
    id: item.id,
    instrument_id: instrument.id,
    kind: item.kind,
    sort_order: item.sort_order,
    quote: quote ?? null,
  }
}

function holdingItem(
  item: StoredHolding,
  instrument: StoredInstrument,
  quote?: Quote
): Holding {
  const currentPrice = quote?.current_price ?? null
  const marketValue = currentPrice === null ? null : currentPrice * item.quantity
  return {
    ...instrumentPublic(instrument),
    id: item.id,
    instrument_id: instrument.id,
    quantity: item.quantity,
    average_cost: item.average_cost,
    note: item.note,
    current_price: currentPrice,
    market_value: marketValue,
    unrealized_pnl:
      marketValue === null ? null : marketValue - item.average_cost * item.quantity,
    quote: quote ?? null,
  }
}

function alertItem(
  item: StoredAlert,
  instrument: StoredInstrument,
  quote?: Quote
): AlertRule {
  return {
    ...instrumentPublic(instrument),
    id: item.id,
    instrument_id: instrument.id,
    instrument_name: instrument.name,
    name: item.name,
    metric: item.metric,
    direction: item.direction,
    threshold: item.threshold,
    channel_ids: item.channel_ids,
    enabled: item.enabled,
    once_per_day: item.once_per_day,
    market_hours_only: item.market_hours_only,
    cooldown_minutes: item.cooldown_minutes,
    last_triggered_at: item.last_triggered_at,
    quote: quote ?? null,
  }
}

function maskedSettings(settings: AppSettings): AppSettings {
  return {
    ...settings,
    ai: {
      ...settings.ai,
      api_key: settings.ai.api_key ? '••••••••' : '',
    },
    news: {
      ...settings.news,
      api_key: settings.news.api_key ? '••••••••' : '',
    },
  }
}

function sessionView(state: MobileState, session: StoredSession): AIChatSession {
  const instrument = session.active_instrument_id
    ? findInstrument(state, session.active_instrument_id)
    : null
  return {
    id: session.id,
    title: session.title,
    message_count: session.messages.length,
    updated_at: session.updated_at,
    active_instrument: instrument
      ? { ...instrumentPublic(instrument), id: instrument.id }
      : null,
  }
}

function sessionDetail(state: MobileState, session: StoredSession): AIChatSessionDetail {
  const view = sessionView(state, session)
  return {
    id: session.id,
    title: session.title,
    active_instrument: view.active_instrument,
    messages: session.messages,
  }
}

async function scanRule(
  state: MobileState,
  rule: StoredAlert,
  now = new Date()
): Promise<'triggered' | 'condition_not_met' | 'quote_unavailable' | 'cooldown'> {
  const instrument = findInstrument(state, rule.instrument_id)
  if (!instrument) return 'quote_unavailable'
  const quote = (await quotesFor(state, [instrument]))[instrumentKey(instrument)]
  if (!quote) return 'quote_unavailable'
  const observed = rule.metric === 'price' ? quote.current_price : quote.change_pct
  if (observed == null) return 'quote_unavailable'
  if (rule.once_per_day && rule.last_triggered_at) {
    if (rule.last_triggered_at.slice(0, 10) === now.toISOString().slice(0, 10)) {
      return 'cooldown'
    }
  }
  if (!rule.once_per_day && rule.last_triggered_at) {
    const elapsed = now.getTime() - Date.parse(rule.last_triggered_at)
    if (elapsed < rule.cooldown_minutes * 60_000) return 'cooldown'
  }
  const matches =
    rule.direction === 'above' ? observed > rule.threshold : observed < rule.threshold
  if (!matches) return 'condition_not_met'
  rule.last_triggered_at = now.toISOString()
  state.alert_hits.unshift({
    id: nextId(state, 'alert_hits'),
    rule_id: rule.id,
    instrument_id: instrument.id,
    triggered_at: now.toISOString(),
    observed_value: observed,
    snapshot: quote,
  })
  nativeBridge()?.notify(rule.name || instrument.name, `${instrument.name} ${observed}`)
  return 'triggered'
}

export async function mobileApiRequest<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const state = readState()
  const url = new URL(path, 'https://crazygame.local')
  const method = (init.method ?? 'GET').toUpperCase()
  const body = requestBody(init)
  const segments = url.pathname.split('/').filter(Boolean)

  if (url.pathname === '/instruments/search') {
    return {
      items: await searchInstruments(
        url.searchParams.get('q') ?? '',
        url.searchParams.get('market') ?? '',
        url.searchParams.get('asset_type') ?? ''
      ),
    } as T
  }

  if (url.pathname === '/watchlist' && method === 'GET') {
    const kind = url.searchParams.get('kind')
    const items = state.watchlist
      .filter((item) => !kind || item.kind === kind)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((item) => {
        const instrument = findInstrument(state, item.instrument_id)
        return instrument ? watchlistItem(item, instrument) : null
      })
      .filter(Boolean)
    return { items } as T
  }

  if (url.pathname === '/watchlist' && method === 'POST') {
    const instrument = normalizeInstrument(state, body as unknown as Instrument)
    const kind = body.kind as WatchlistKind
    const existing = state.watchlist.find(
      (item) => item.instrument_id === instrument.id && item.kind === kind
    )
    if (existing) return watchlistItem(existing, instrument) as T
    const item = {
      id: nextId(state, 'watchlist'),
      instrument_id: instrument.id,
      kind,
      sort_order: state.watchlist.filter((row) => row.kind === kind).length,
    }
    state.watchlist.push(item)
    saveState(state)
    return watchlistItem(item, instrument) as T
  }

  if (url.pathname === '/watchlist/order' && method === 'PUT') {
    const kind = body.kind as WatchlistKind
    const ids = (body.item_ids as number[]) ?? []
    ids.forEach((id, index) => {
      const item = state.watchlist.find((row) => row.id === id && row.kind === kind)
      if (item) item.sort_order = index
    })
    saveState(state)
    return {
      items: state.watchlist
        .filter((row) => row.kind === kind)
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((row) => {
          const instrument = findInstrument(state, row.instrument_id)
          return instrument ? watchlistItem(row, instrument) : null
        })
        .filter(Boolean),
    } as T
  }

  if (segments[0] === 'watchlist' && segments[1] && method === 'DELETE') {
    state.watchlist = state.watchlist.filter((item) => item.id !== Number(segments[1]))
    saveState(state)
    return { ok: true } as T
  }

  if (url.pathname === '/quotes') {
    const kind = url.searchParams.get('kind')
    const rows = state.watchlist.filter((item) => !kind || item.kind === kind)
    const instruments = rows
      .map((item) => findInstrument(state, item.instrument_id))
      .filter((item): item is StoredInstrument => Boolean(item))
    const quotes = await quotesFor(state, instruments)
    saveState(state)
    return {
      items: rows
        .map((row) => {
          const instrument = findInstrument(state, row.instrument_id)
          return instrument
            ? watchlistItem(row, instrument, quotes[instrumentKey(instrument)])
            : null
        })
        .filter(Boolean),
    } as T
  }

  if (segments[0] === 'instruments' && segments[2] === 'series') {
    const instrument = findInstrument(state, Number(segments[1]))
    if (!instrument) throw new Error('instrument_not_found')
    const days = Number(url.searchParams.get('days') || 365)
    const points = await seriesFor(state, instrument, days)
    saveState(state)
    return { points } as T
  }

  if (url.pathname === '/groups' && method === 'GET') {
    return { items: await Promise.all(state.groups.map((group) => groupDict(state, group))) } as T
  }

  if (url.pathname === '/groups' && method === 'POST') {
    const instrumentIds = (body.members as Array<{ instrument_id: number; weight: number }>).map(
      (member) => member.instrument_id
    )
    const scopes = new Set(
      instrumentIds
        .map((id) => findInstrument(state, id))
        .filter((item): item is StoredInstrument => Boolean(item))
        .map((item) => instrumentScope(item))
    )
    if (scopes.size !== 1) throw new Error('group_scope_mismatch')
    const group: StoredGroup = {
      id: nextId(state, 'groups'),
      name: String(body.name ?? ''),
      description: String(body.description ?? ''),
      sort_order: state.groups.length,
      member_ids: body.members as Array<{ instrument_id: number; weight: number }>,
      updated_at: new Date().toISOString(),
    }
    state.groups.push(group)
    saveState(state)
    return groupDict(state, group) as T
  }

  if (segments[0] === 'groups' && segments[1]) {
    const group = state.groups.find((item) => item.id === Number(segments[1]))
    if (!group) throw new Error('group_not_found')
    if (segments[2] === 'summary') return groupDict(state, group) as T
    if (segments[2] === 'series') {
      const days = Number(url.searchParams.get('days') || 365)
      const entries = normalizedMembers(state, group)
      const histories = await Promise.all(
        entries.map(async (entry) => ({
          entry,
          points: await seriesFor(state, entry.instrument, days),
        }))
      )
      const dates = [...new Set(histories.flatMap((item) => item.points.map((point) => point.date)))]
        .sort()
      const starts = new Map<number, number>()
      const last = new Map<number, number>()
      const points: GroupPoint[] = []
      for (const date of dates) {
        let available = 0
        let value = 0
        for (const { entry, points: history } of histories) {
          const point = history.find((candidate) => candidate.date === date)
          if (point) last.set(entry.instrument.id, point.value)
          const current = last.get(entry.instrument.id)
          if (current == null) continue
          const start = starts.get(entry.instrument.id) ?? current
          starts.set(entry.instrument.id, start)
          if (start <= 0) continue
          available += entry.normalized
          value += entry.normalized * (current / start)
        }
        if (available > 0) {
          points.push({
            date,
            value: (value / available) * 100,
            coverage: available,
          })
        }
      }
      return {
        points,
        members: histories.map(({ entry, points: memberPoints }) => ({
          instrument_id: entry.instrument.id,
          name: entry.instrument.name,
          symbol: entry.instrument.symbol,
          points: memberPoints,
        })),
      } as T
    }
    if (method === 'PUT') {
      group.name = String(body.name ?? group.name)
      group.description = String(body.description ?? group.description)
      group.member_ids = body.members as Array<{ instrument_id: number; weight: number }>
      group.updated_at = new Date().toISOString()
      saveState(state)
      return groupDict(state, group) as T
    }
    if (method === 'DELETE') {
      state.groups = state.groups.filter((item) => item.id !== group.id)
      saveState(state)
      return { ok: true } as T
    }
  }

  if (url.pathname === '/holdings' && method === 'GET') {
    const instruments = state.holdings
      .map((item) => findInstrument(state, item.instrument_id))
      .filter((item): item is StoredInstrument => Boolean(item))
    const quotes = await quotesFor(state, instruments)
    saveState(state)
    return {
      items: state.holdings
        .map((item) => {
          const instrument = findInstrument(state, item.instrument_id)
          return instrument
            ? holdingItem(item, instrument, quotes[instrumentKey(instrument)])
            : null
        })
        .filter(Boolean),
    } as T
  }

  if (url.pathname === '/holdings' && method === 'PUT') {
    const instrument = findInstrument(state, Number(body.instrument_id))
    if (!instrument) throw new Error('instrument_not_found')
    let holding = state.holdings.find((item) => item.instrument_id === instrument.id)
    if (!holding) {
      holding = {
        id: nextId(state, 'holdings'),
        instrument_id: instrument.id,
        quantity: 0,
        average_cost: 0,
        note: '',
        updated_at: new Date().toISOString(),
      }
      state.holdings.push(holding)
    }
    holding.quantity = Number(body.quantity ?? 0)
    holding.average_cost = Number(body.average_cost ?? 0)
    holding.note = String(body.note ?? '')
    holding.updated_at = new Date().toISOString()
    saveState(state)
    return { ok: true, id: holding.id } as T
  }

  if (segments[0] === 'holdings' && segments[1] && method === 'DELETE') {
    state.holdings = state.holdings.filter((item) => item.id !== Number(segments[1]))
    saveState(state)
    return { ok: true } as T
  }

  if (url.pathname === '/holdings/series') {
    const days = Number(url.searchParams.get('days') || 365)
    const grouped = new Map<string, StoredHolding[]>()
    for (const holding of state.holdings) {
      const instrument = findInstrument(state, holding.instrument_id)
      if (!instrument) continue
      const rows = grouped.get(instrument.currency) ?? []
      rows.push(holding)
      grouped.set(instrument.currency, rows)
    }
    const series = await Promise.all(
      [...grouped.entries()].map(async ([currency, rows]) => {
        const synthetic: StoredGroup = {
          id: 0,
          name: currency,
          description: '',
          sort_order: 0,
          member_ids: rows.map((holding) => ({
            instrument_id: holding.instrument_id,
            weight: Math.max(1, holding.quantity * holding.average_cost),
          })),
          updated_at: new Date().toISOString(),
        }
        const entries = normalizedMembers(state, synthetic)
        const histories = await Promise.all(
          entries.map(async (entry) => ({
            entry,
            points: await seriesFor(state, entry.instrument, days),
          }))
        )
        const dates = [...new Set(histories.flatMap((item) => item.points.map((point) => point.date)))]
          .sort()
        const starts = new Map<number, number>()
        const last = new Map<number, number>()
        const points: GroupPoint[] = []
        for (const date of dates) {
          let available = 0
          let value = 0
          for (const entry of histories) {
            const point = entry.points.find((candidate) => candidate.date === date)
            if (point) last.set(entry.entry.instrument.id, point.value)
            const current = last.get(entry.entry.instrument.id)
            if (current == null) continue
            const start = starts.get(entry.entry.instrument.id) ?? current
            starts.set(entry.entry.instrument.id, start)
            if (start <= 0) continue
            available += entry.entry.normalized
            value += entry.entry.normalized * (current / start)
          }
          if (available > 0) points.push({ date, value: (value / available) * 100, coverage: available })
        }
        return { currency, points }
      })
    )
    saveState(state)
    return { series } as T
  }

  if (url.pathname === '/alerts' && method === 'GET') {
    const instruments = state.alerts
      .map((item) => findInstrument(state, item.instrument_id))
      .filter((item): item is StoredInstrument => Boolean(item))
    const quotes = await quotesFor(state, instruments)
    return {
      items: state.alerts.map((item) => {
        const instrument = findInstrument(state, item.instrument_id)!
        return alertItem(item, instrument, quotes[instrumentKey(instrument)])
      }),
    } as T
  }

  if (url.pathname === '/alerts/hits') {
    return {
      items: state.alert_hits.map((hit) => {
        const rule = state.alerts.find((item) => item.id === hit.rule_id)
        const instrument = findInstrument(state, hit.instrument_id)
        return {
          id: hit.id,
          rule_id: hit.rule_id,
          rule_name: rule?.name ?? '',
          symbol: instrument?.symbol ?? '',
          instrument_name: instrument?.name ?? '',
          market: instrument?.market ?? 'CN',
          triggered_at: hit.triggered_at,
          observed_value: hit.observed_value,
          snapshot: hit.snapshot ?? {},
          deliveries: [],
        }
      }),
    } as T
  }

  if (url.pathname === '/alerts' && method === 'POST') {
    const rule: StoredAlert = {
      id: nextId(state, 'alerts'),
      instrument_id: Number(body.instrument_id),
      name: String(body.name ?? ''),
      metric: body.metric as 'price' | 'change_pct',
      direction: body.direction as 'above' | 'below',
      threshold: Number(body.threshold),
      channel_ids: (body.channel_ids as number[]) ?? [LOCAL_NOTIFICATION_CHANNEL_ID],
      enabled: true,
      once_per_day: Boolean(body.once_per_day),
      market_hours_only: Boolean(body.market_hours_only),
      cooldown_minutes: Number(body.cooldown_minutes ?? 30),
      last_triggered_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    state.alerts.push(rule)
    let runResult = { scan: { triggered: 0, skipped: 1, reason: 'not_requested' }, delivery: { processed: 0 } }
    if (body.run_now) {
      const result = await scanRule(state, rule)
      runResult = {
        scan: {
          triggered: result === 'triggered' ? 1 : 0,
          skipped: result === 'triggered' ? 0 : 1,
          reason: result,
        },
        delivery: { processed: 0 },
      }
    }
    saveState(state)
    initializeMobileRuntime()
    const instrument = findInstrument(state, rule.instrument_id)!
    return { ...alertItem(rule, instrument), run_result: runResult } as T
  }

  if (segments[0] === 'alerts' && segments[1] && method === 'PATCH') {
    const rule = state.alerts.find((item) => item.id === Number(segments[1]))
    if (!rule) throw new Error('alert_not_found')
    Object.assign(rule, body, { updated_at: new Date().toISOString() })
    saveState(state)
    initializeMobileRuntime()
    const instrument = findInstrument(state, rule.instrument_id)!
    return alertItem(rule, instrument) as T
  }

  if (segments[0] === 'alerts' && segments[1] && method === 'DELETE') {
    state.alerts = state.alerts.filter((item) => item.id !== Number(segments[1]))
    state.alert_hits = state.alert_hits.filter((hit) => hit.rule_id !== Number(segments[1]))
    saveState(state)
    initializeMobileRuntime()
    return { ok: true } as T
  }

  if (url.pathname === '/channels' && method === 'GET') {
    return { items: state.channels } as T
  }

  if (url.pathname === '/channels' && method === 'POST') {
    const channel: NotifyChannel = {
      id: nextId(state, 'channels'),
      name: String(body.name ?? ''),
      type: body.type as NotifyChannel['type'],
      config: (body.config as Record<string, unknown>) ?? {},
      enabled: Boolean(body.enabled ?? true),
    }
    state.channels.push(channel)
    saveState(state)
    return channel as T
  }

  if (url.pathname === '/channels/test' && method === 'POST') {
    const bridge = nativeBridge()
    if (!bridge) throw new Error('native_bridge_unavailable')
    const type = String(body.type ?? '')
    if (type === 'local') bridge.notify('CrazyGame', 'Test notification')
    else {
      const result = JSON.parse(
        bridge.sendNotification(
          JSON.stringify({ type, config: body.config ?? {} }),
          'CrazyGame',
          'Test notification'
        )
      ) as { ok?: boolean; error?: string }
      if (!result.ok) throw new Error(result.error || 'channel_test_failed')
    }
    return { ok: true } as T
  }

  if (segments[0] === 'channels' && segments[1]) {
    const channel = state.channels.find((item) => item.id === Number(segments[1]))
    if (!channel) throw new Error('channel_not_found')
    if (segments[2] === 'test') {
      const bridge = nativeBridge()
      if (!bridge) throw new Error('native_bridge_unavailable')
      if (channel.type === 'local') bridge.notify(channel.name, 'Test notification')
      else {
        const result = JSON.parse(
          bridge.sendNotification(
            JSON.stringify(channel),
            channel.name,
            'Test notification'
          )
        ) as { ok?: boolean; error?: string }
        if (!result.ok) throw new Error(result.error || 'channel_test_failed')
      }
      return { ok: true } as T
    }
    if (method === 'DELETE') {
      state.channels = state.channels.filter((item) => item.id !== channel.id)
      state.settings.daily_review_channel_ids = state.settings.daily_review_channel_ids.filter(
        (id) => id !== channel.id
      )
      saveState(state)
      return { ok: true } as T
    }
  }

  if (url.pathname === '/settings' && method === 'GET') {
    return maskedSettings(state.settings) as T
  }

  if (url.pathname === '/settings' && method === 'PUT') {
    const incoming = body as unknown as AppSettings
    if (incoming.ai.api_key === '••••••••') incoming.ai.api_key = state.settings.ai.api_key
    if (incoming.news.api_key === '••••••••') incoming.news.api_key = state.settings.news.api_key
    state.settings = incoming
    saveState(state)
    initializeMobileRuntime()
    return maskedSettings(state.settings) as T
  }

  if (url.pathname === '/settings/ai/test') {
    let content = ''
    await nativeAiStream(
      [{ role: 'user', content: 'Reply with exactly: ok' }],
      (event) => {
        if (event.type === 'delta') content += event.content ?? ''
        if (event.type === 'error') throw new Error(event.code || 'ai_config_failed')
      },
      undefined,
      body
    )
    return {
      json: false,
      tools: false,
      stream: Boolean(content),
      vision: false,
      ok: Boolean(content),
      code: content ? '' : 'ai_config_failed',
      errors: {},
    } as T
  }

  if (url.pathname === '/reviews/daily') {
    return { items: state.reviews } as T
  }

  if (url.pathname === '/reviews/daily/run') {
    if (!state.holdings.length) {
      return { status: 'skipped', reason: 'no_holdings' } as T
    }
    const tradeDate = new Date().toISOString().slice(0, 10)
    const existing = (state.reviews as Array<Record<string, unknown>>).find(
      (review) =>
        review.trade_date === tradeDate && review.status === 'success'
    )
    if (existing) {
      return { status: 'success', id: existing.id, cached: true } as T
    }
    const instruments = state.holdings
      .map((holding) => findInstrument(state, holding.instrument_id))
      .filter((item): item is StoredInstrument => Boolean(item))
    const quotes = await quotesFor(state, instruments)
    let content = ''
    await nativeAiStream(
      [
        {
          role: 'system',
          content:
            'Create a concise portfolio health review in Markdown. Discuss health, concentration, trend, hold/watch/reduce/add observations, and include a disclaimer. Do not predict prices.',
        },
        {
          role: 'user',
          content: JSON.stringify(
            state.holdings.map((holding) => {
              const instrument = findInstrument(state, holding.instrument_id)
              return {
                ...holding,
                instrument,
                quote: instrument ? quotes[instrumentKey(instrument)] : null,
              }
            })
          ),
        },
      ],
      (event) => {
        if (event.type === 'delta') content += event.content ?? ''
        if (event.type === 'error') throw new Error(event.code || 'ai_report_failed')
      },
      undefined,
      state.settings.ai
    )
    const review = {
      id: Date.now(),
      trade_date: tradeDate,
      language: state.settings.language,
      status: 'success',
      title:
        state.settings.language === 'zh-CN'
          ? '\u6bcf\u65e5\u6301\u4ed3\u5065\u5eb7\u7b80\u62a5'
          : 'Daily portfolio health',
      content,
      snapshot_json: '{}',
      model_label: state.settings.ai.model,
      notified_at: new Date().toISOString(),
      error: '',
      created_at: new Date().toISOString(),
    }
    state.reviews.unshift(review)
    saveState(state)
    nativeBridge()?.notify(review.title, content.slice(0, 180))
    return { status: 'success', id: review.id } as T
  }

  saveState(state)
  throw new Error(`native_endpoint_not_supported:${method}:${url.pathname}`)
}

export async function mobileChatStream(
  body: { message: string; session_id?: string; instrument_id?: number },
  onEvent: (event: AISseEvent) => void,
  signal?: AbortSignal
) {
  const state = readState()
  const now = new Date().toISOString()
  let session = body.session_id
    ? state.sessions.find((item) => item.id === body.session_id)
    : undefined
  if (!session) {
    session = {
      id: crypto.randomUUID(),
      title: body.message.slice(0, 48),
      active_instrument_id: body.instrument_id ?? null,
      created_at: now,
      updated_at: now,
      messages: [],
    }
    state.sessions.unshift(session)
  }
  const instrument = body.instrument_id
    ? findInstrument(state, body.instrument_id)
    : session.active_instrument_id
      ? findInstrument(state, session.active_instrument_id)
      : undefined
  const userMessage: AIChatMessage = {
    id: `local-${Date.now()}`,
    role: 'user',
    content: body.message,
    created_at: now,
  }
  session.messages.push(userMessage)
  session.updated_at = now
  saveState(state)
  onEvent({
    type: 'accepted',
    request_id: crypto.randomUUID(),
    session_id: session.id,
    active_instrument: instrument
      ? { ...instrumentPublic(instrument), id: instrument.id }
      : null,
  })
  onEvent({ type: 'stage', stage: 'context' })
  let content = ''
  await nativeAiStream(
    [
      {
        role: 'system',
        content:
          'You are a long-term market observation assistant. Be concise, evidence-aware, and never promise returns.',
      },
      ...(instrument
        ? [
            {
              role: 'system',
              content: `Current instrument: ${instrument.name} (${instrument.symbol}, ${instrument.market}).`,
            },
          ]
        : []),
      ...session.messages.map((message) => ({
        role: message.role,
        content: message.content,
      })),
    ],
    (event) => {
      if (event.type === 'delta' && event.content) {
        content += event.content
        onEvent({ type: 'delta', content: event.content })
      }
      if (event.type === 'error') {
        onEvent({ type: 'error', code: event.code || 'ai_provider_error' })
      }
    },
    signal,
    state.settings.ai
  )
  session.messages.push({
    id: `local-${Date.now()}-assistant`,
    role: 'assistant',
    content,
    created_at: new Date().toISOString(),
  })
  session.updated_at = new Date().toISOString()
  saveState(state)
  onEvent({ type: 'done', content })
}

export async function mobileReportStream(
  instrumentId: number,
  onEvent: (event: AISseEvent) => void,
  signal?: AbortSignal
) {
  const state = readState()
  const instrument = findInstrument(state, instrumentId)
  if (!instrument) throw new Error('instrument_not_found')
  const quote = (await quotesFor(state, [instrument]))[instrumentKey(instrument)]
  const history = await seriesFor(state, instrument, 120)
  onEvent({ type: 'stage', stage: 'context' })
  onEvent({ type: 'stage', stage: 'generate' })
  let content = ''
  await nativeAiStream(
    [
      {
        role: 'system',
        content:
          'Create a concise long-term market observation report in Markdown. Do not predict prices or recommend trades. Include trend, risks, catalysts, data limitations, and a disclaimer.',
      },
      {
        role: 'user',
        content: JSON.stringify({
          instrument,
          quote,
          recent_points: history.slice(-120),
          holdings: state.holdings.filter((item) => item.instrument_id === instrumentId),
        }),
      },
    ],
    (event) => {
      if (event.type === 'delta') content += event.content ?? ''
      if (event.type === 'error') onEvent({ type: 'error', code: event.code || 'ai_provider_error' })
    },
    signal,
    state.settings.ai
  )
  const report: AIDecisionReport = {
    instrument: instrumentPublic(instrument),
    score: 50,
    verdict: 'neutral',
    confidence: quote ? 'medium' : 'low',
    core_conclusion: content.split('\n').find((line) => line.trim()) ?? content,
    trend: content,
    quote: quote ?? {},
    hotspots: [],
    risks: [],
    catalysts: [],
    position_advice: { no_position: '', has_position: '' },
    price_plan: { support: null, resistance: null, invalidation_reference: null },
    action_checklist: [],
    data_quality: {
      level: quote ? 'limited' : 'poor',
      limitations: ['Local Android analysis uses public market endpoints.'],
      quote_as_of: quote?.as_of ?? '',
      quote_source: quote?.source ?? '',
      quote_freshness: quote?.freshness ?? 'stale',
    },
    disclaimer: 'For personal research only. Not investment advice.',
  }
  const record: AIReportRecord = {
    id: Date.now(),
    instrument: instrumentPublic(instrument),
    status: 'success',
    language: state.settings.language,
    title: `${instrument.name} AI report`,
    verdict: 'neutral',
    confidence: report.confidence,
    score: 50,
    content_markdown: content,
    report,
    model_label: state.settings.ai.model,
    error: '',
    created_at: new Date().toISOString(),
  }
  state.reports.unshift(record)
  saveState(state)
  onEvent({ type: 'done', id: record.id })
}

export function mobileSessions() {
  const state = readState()
  return { items: state.sessions.map((session) => sessionView(state, session)) }
}

export function mobileSession(id: string) {
  const state = readState()
  const session = state.sessions.find((item) => item.id === id)
  if (!session) throw new Error('session_not_found')
  return sessionDetail(state, session)
}

export function mobileDeleteSession(id: string) {
  const state = readState()
  state.sessions = state.sessions.filter((item) => item.id !== id)
  saveState(state)
  return { ok: true }
}

export function mobileReports(instrumentId?: number, limit = 30) {
  const state = readState()
  return {
    items: state.reports
      .filter((report) => !instrumentId || report.instrument.id === instrumentId)
      .slice(0, limit),
  }
}

export function mobileReport(id: number) {
  const state = readState()
  const report = state.reports.find((item) => item.id === id)
  if (!report) throw new Error('report_not_found')
  return report
}

export function mobileDeleteReport(id: number) {
  const state = readState()
  state.reports = state.reports.filter((item) => item.id !== id)
  saveState(state)
  return { ok: true }
}

function fileDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error ?? new Error('file_read_failed'))
    reader.readAsDataURL(file)
  })
}

export async function mobileRecognizeImage(file: File) {
  const state = readState()
  const imageUrl = await fileDataUrl(file)
  let content = ''
  await nativeAiStream(
    [
      {
        role: 'system',
        content:
          'Identify visible stocks, ETFs, or funds. Return only a JSON array of objects with code, name, and confidence where confidence is high, medium, or low.',
      },
      {
        role: 'user',
        content: [
          { type: 'text', text: 'Identify the investment instruments in this screenshot.' },
          { type: 'image_url', image_url: { url: imageUrl } },
        ],
      },
    ],
    (event) => {
      if (event.type === 'delta') content += event.content ?? ''
      if (event.type === 'error') throw new Error(event.code || 'image_recognition_failed')
    },
    undefined,
    state.settings.ai,
    true
  )
  const normalized = content.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
  const parsed = JSON.parse(normalized) as Array<Record<string, unknown>>
  const items = await Promise.all(
    parsed.slice(0, 10).map(async (row) => {
      const code = String(row.code ?? '').trim()
      const matches = code ? await searchInstruments(code) : []
      return {
        code,
        name: row.name ? String(row.name) : null,
        confidence: ['high', 'medium', 'low'].includes(String(row.confidence))
          ? (String(row.confidence) as RecognizedInstrument['confidence'])
          : 'low',
        instrument: matches[0] ?? null,
      } satisfies RecognizedInstrument
    })
  )
  return { items }
}

export function mobileCancelRequest(id: string) {
  cancelNativeRequest(id)
}
