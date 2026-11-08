import type {
  AlertHit,
  AlertRule,
  AppSettings,
  AssetGroup,
  DailyReview,
  GroupMemberPoint,
  GroupPoint,
  Holding,
  Instrument,
  NotifyChannel,
  PortfolioSeries,
  WatchlistItem,
  WatchlistKind,
} from './types'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...init, headers })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      detail = payload.detail ?? detail
    } catch {
      // Keep the status text.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  search: (query: string, filters?: { market?: string; asset_type?: string }) => {
    const params = new URLSearchParams({ q: query })
    if (filters?.market) params.set('market', filters.market)
    if (filters?.asset_type) params.set('asset_type', filters.asset_type)
    return request<{ items: Instrument[] }>(`/instruments/search?${params}`)
  },

  watchlist: (kind?: WatchlistKind) =>
    request<{ items: WatchlistItem[] }>(`/watchlist${kind ? `?kind=${kind}` : ''}`),
  addWatchlist: (payload: Instrument & { kind: WatchlistKind }) =>
    request<WatchlistItem>('/watchlist', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  removeWatchlist: (id: number) =>
    request<{ ok: boolean }>(`/watchlist/${id}`, { method: 'DELETE' }),
  reorderWatchlist: (kind: WatchlistKind, itemIds: number[]) =>
    request<{ items: WatchlistItem[] }>('/watchlist/order', {
      method: 'PUT',
      body: JSON.stringify({ kind, item_ids: itemIds }),
    }),
  watchlistQuotes: (kind?: WatchlistKind) =>
    request<{ items: WatchlistItem[] }>(`/quotes${kind ? `?kind=${kind}` : ''}`),
  instrumentSeries: (id: number, days = 365) =>
    request<{ points: Array<{ date: string; value: number }> }>(
      `/instruments/${id}/series?days=${days}`
    ),

  groups: () => request<{ items: AssetGroup[] }>('/groups'),
  groupSummary: (id: number) => request<AssetGroup>(`/groups/${id}/summary`),
  groupSeries: (id: number, days = 365) =>
    request<{ points: GroupPoint[]; members: GroupMemberPoint[] }>(
      `/groups/${id}/series?days=${days}`
    ),
  createGroup: (payload: { name: string; description: string; members: Array<{ instrument_id: number; weight: number }> }) =>
    request<AssetGroup>('/groups', { method: 'POST', body: JSON.stringify(payload) }),
  updateGroup: (id: number, payload: { name: string; description: string; members: Array<{ instrument_id: number; weight: number }> }) =>
    request<AssetGroup>(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  removeGroup: (id: number) => request<{ ok: boolean }>(`/groups/${id}`, { method: 'DELETE' }),

  holdings: () => request<{ items: Holding[] }>('/holdings'),
  holdingSeries: (days = 365) =>
    request<{ series: PortfolioSeries[] }>(`/holdings/series?days=${days}`),
  upsertHolding: (payload: { instrument_id: number; quantity: number; average_cost: number; note: string }) =>
    request<{ ok: boolean; id: number }>('/holdings', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  removeHolding: (id: number) => request<{ ok: boolean }>(`/holdings/${id}`, { method: 'DELETE' }),

  alerts: () => request<{ items: AlertRule[] }>('/alerts'),
  alertHits: () => request<{ items: AlertHit[] }>('/alerts/hits'),
  createAlert: (payload: {
    instrument_id: number
    name: string
    metric: 'price' | 'change_pct'
    direction: 'above' | 'below'
    threshold: number
    channel_ids: number[]
    once_per_day: boolean
    market_hours_only: boolean
    cooldown_minutes: number
  }) => request<AlertRule>('/alerts', { method: 'POST', body: JSON.stringify(payload) }),
  removeAlert: (id: number) => request<{ ok: boolean }>(`/alerts/${id}`, { method: 'DELETE' }),
  setAlertEnabled: (id: number, enabled: boolean) =>
    request<AlertRule>(`/alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),

  channels: () => request<{ items: NotifyChannel[] }>('/channels'),
  createChannel: (payload: {
    name: string
    type: 'feishu' | 'aliyun_sms'
    config: Record<string, unknown>
    enabled: boolean
  }) => request<NotifyChannel>('/channels', { method: 'POST', body: JSON.stringify(payload) }),
  removeChannel: (id: number) => request<{ ok: boolean }>(`/channels/${id}`, { method: 'DELETE' }),
  testChannel: (id: number) => request<{ ok: boolean }>(`/channels/${id}/test`, { method: 'POST' }),

  settings: () => request<AppSettings>('/settings'),
  updateSettings: (payload: AppSettings) =>
    request<AppSettings>('/settings', { method: 'PUT', body: JSON.stringify(payload) }),

  dailyReviews: () => request<{ items: DailyReview[] }>('/reviews/daily'),
  runDailyReview: () => request<{ status: string; id?: number }>('/reviews/daily/run', { method: 'POST' }),
}

