export type TransferModule =
  | 'watchlist'
  | 'groups'
  | 'holdings'
  | 'alerts'
  | 'llm'

export const transferModules: TransferModule[] = [
  'watchlist',
  'groups',
  'holdings',
  'alerts',
  'llm',
]

interface TransferBundle {
  format: 'crazygame-transfer'
  version: 1
  generated_at: string
  modules: TransferModule[]
  credentials_included: boolean
  data: Record<string, unknown>
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function createTransferBundle(
  stateJson: string,
  selectedModules: TransferModule[],
  includeCredentials: boolean
) {
  const state = JSON.parse(stateJson) as Record<string, unknown>
  const modules = new Set(selectedModules)
  const data: Record<string, unknown> = {
    instruments: clone(state.instruments ?? []),
  }
  for (const module of ['watchlist', 'groups', 'holdings', 'alerts'] as const) {
    data[module] = modules.has(module) ? clone(state[module] ?? []) : []
  }
  if (modules.has('alerts')) {
    data.channels = clone(state.channels ?? [])
    data.alert_hits = clone(state.alert_hits ?? [])
  }
  if (modules.has('llm')) {
    const settings = clone((state.settings ?? {}) as Record<string, unknown>)
    const ai = (settings.ai ?? {}) as Record<string, unknown>
    const news = (settings.news ?? {}) as Record<string, unknown>
    data.settings = {
      ai: {
        ...ai,
        api_key: includeCredentials ? ai.api_key ?? '' : '',
      },
      news: {
        ...news,
        api_key: includeCredentials ? news.api_key ?? '' : '',
      },
    }
  }
  if (!includeCredentials && Array.isArray(data.channels)) {
    data.channels = (data.channels as Array<Record<string, unknown>>).map(
      (channel) => ({ ...channel, config: {} })
    )
  }
  const bundle: TransferBundle = {
    format: 'crazygame-transfer',
    version: 1,
    generated_at: new Date().toISOString(),
    modules: selectedModules,
    credentials_included: includeCredentials,
    data,
  }
  return JSON.stringify(bundle, null, 2)
}

function identity(item: Record<string, unknown>) {
  return `${String(item.market)}:${String(item.symbol)}:${String(item.asset_type)}`
}

function availableId(
  rows: Array<Record<string, unknown>>,
  requested: unknown
) {
  const used = new Set(rows.map((row) => Number(row.id)))
  const candidate = Number(requested)
  if (Number.isFinite(candidate) && candidate > 0 && !used.has(candidate)) {
    return candidate
  }
  return Math.max(0, ...used) + 1
}

export function mergeTransferBundle(
  currentJson: string,
  bundleInput: string | Record<string, unknown>,
  selectedModules?: TransferModule[]
) {
  const current = JSON.parse(currentJson) as Record<string, unknown>
  const bundle =
    typeof bundleInput === 'string'
      ? (JSON.parse(bundleInput) as TransferBundle)
      : (bundleInput as unknown as TransferBundle)
  if (bundle.format !== 'crazygame-transfer' || bundle.version !== 1) {
    throw new Error('unsupported_transfer_bundle')
  }
  const selected = new Set(selectedModules?.length ? selectedModules : bundle.modules)
  const importedInstruments = (bundle.data.instruments ?? []) as Array<
    Record<string, unknown>
  >
  const currentInstruments = (current.instruments ?? []) as Array<
    Record<string, unknown>
  >
  let nextInstrumentId =
    Math.max(0, ...currentInstruments.map((item) => Number(item.id) || 0)) + 1
  const idMap = new Map<number, number>()

  for (const imported of importedInstruments) {
    const existing = currentInstruments.find(
      (item) => identity(item) === identity(imported)
    )
    if (existing) {
      idMap.set(Number(imported.id), Number(existing.id))
      continue
    }
    const next = nextInstrumentId++
    const copy = { ...imported, id: next }
    currentInstruments.push(copy)
    idMap.set(Number(imported.id), next)
  }
  current.instruments = currentInstruments

  if (selected.has('watchlist')) {
    const rows = (current.watchlist ?? []) as Array<Record<string, unknown>>
    for (const imported of (bundle.data.watchlist ?? []) as Array<Record<string, unknown>>) {
      const instrumentId = idMap.get(Number(imported.instrument_id))
      if (!instrumentId) continue
      const existing = rows.find(
        (row) => row.instrument_id === instrumentId && row.kind === imported.kind
      )
      if (existing) {
        Object.assign(existing, imported, { instrument_id: instrumentId })
      } else {
        rows.push({
          ...imported,
          id: availableId(rows, imported.id),
          instrument_id: instrumentId,
        })
      }
    }
    current.watchlist = rows
  }

  if (selected.has('holdings')) {
    const rows = (current.holdings ?? []) as Array<Record<string, unknown>>
    for (const imported of (bundle.data.holdings ?? []) as Array<Record<string, unknown>>) {
      const instrumentId = idMap.get(Number(imported.instrument_id))
      if (!instrumentId) continue
      const existing = rows.find((row) => row.instrument_id === instrumentId)
      if (existing) Object.assign(existing, imported, { instrument_id: instrumentId })
      else {
        rows.push({
          ...imported,
          id: availableId(rows, imported.id),
          instrument_id: instrumentId,
        })
      }
    }
    current.holdings = rows
  }

  if (selected.has('groups')) {
    const rows = (current.groups ?? []) as Array<Record<string, unknown>>
    for (const imported of (bundle.data.groups ?? []) as Array<Record<string, unknown>>) {
      const members = ((imported.member_ids ?? []) as Array<Record<string, unknown>>)
        .map((member) => ({
          ...member,
          instrument_id: idMap.get(Number(member.instrument_id)),
        }))
        .filter((member) => member.instrument_id)
      const existing = rows.find(
        (row) => row.name === imported.name && row.id === imported.id
      )
      if (existing) {
        Object.assign(existing, imported, { member_ids: members })
      } else {
        rows.push({
          ...imported,
          id: availableId(rows, imported.id),
          member_ids: members,
        })
      }
    }
    current.groups = rows
  }

  if (selected.has('alerts')) {
    const channels = (current.channels ?? []) as Array<Record<string, unknown>>
    const channelMap = new Map<number, number>()
    for (const imported of (bundle.data.channels ?? []) as Array<Record<string, unknown>>) {
      const type = String(imported.type ?? '')
      const existing =
        type === 'local'
          ? channels.find((channel) => channel.type === 'local')
          : channels.find(
              (channel) =>
                channel.name === imported.name && channel.type === imported.type
            )
      if (existing) {
        channelMap.set(Number(imported.id), Number(existing.id))
        if (imported.config && Object.keys(imported.config).length) {
          existing.config = imported.config
        }
      } else {
        const id = availableId(channels, imported.id)
        channels.push({ ...imported, id })
        channelMap.set(Number(imported.id), id)
      }
    }
    current.channels = channels
    const rows = (current.alerts ?? []) as Array<Record<string, unknown>>
    for (const imported of (bundle.data.alerts ?? []) as Array<Record<string, unknown>>) {
      const instrumentId = idMap.get(Number(imported.instrument_id))
      if (!instrumentId) continue
      const duplicate = rows.find(
        (row) =>
          row.instrument_id === instrumentId &&
          row.metric === imported.metric &&
          row.direction === imported.direction &&
          row.threshold === imported.threshold
      )
      const channelIds = ((imported.channel_ids ?? []) as number[])
        .map((id) => channelMap.get(Number(id)))
        .filter((id): id is number => Boolean(id))
      if (duplicate) {
        Object.assign(duplicate, imported, {
          instrument_id: instrumentId,
          channel_ids: channelIds,
        })
      } else {
        rows.push({
          ...imported,
          id: availableId(rows, imported.id),
          instrument_id: instrumentId,
          channel_ids: channelIds,
        })
      }
    }
    current.alerts = rows
    if (bundle.data.alert_hits) current.alert_hits = bundle.data.alert_hits
  }

  if (selected.has('llm') && bundle.data.settings) {
    const currentSettings = (current.settings ?? {}) as Record<string, unknown>
    const imported = bundle.data.settings as Record<string, unknown>
    current.settings = {
      ...currentSettings,
      ai: {
        ...((currentSettings.ai ?? {}) as Record<string, unknown>),
        ...((imported.ai ?? {}) as Record<string, unknown>),
      },
      news: {
        ...((currentSettings.news ?? {}) as Record<string, unknown>),
        ...((imported.news ?? {}) as Record<string, unknown>),
      },
    }
  }

  return JSON.stringify(current)
}
