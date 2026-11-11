import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BellRing,
  GripVertical,
  ImagePlus,
  LineChart as LineChartIcon,
  Plus,
  Search,
  Trash2,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { aiApi } from '../ai'
import { DataState } from '../components/DataState'
import { InstrumentDetailModal } from '../components/InstrumentDetailModal'
import {
  Badge,
  Button,
  EmptyState,
  GlassPanel,
  Input,
  InstrumentMark,
  Loading,
  PageHeader,
  Sparkline,
} from '../components/ui'
import {
  changeClass,
  formatPercent,
  instrumentScope,
  moveItem,
  type InstrumentScope,
} from '../lib'
import {
  defaultScope,
  scopesForKind,
  searchFiltersForScope,
} from '../scopes'
import type {
  Instrument,
  RecognizedInstrument,
  WatchlistItem,
  WatchlistKind,
} from '../types'

export function WatchlistPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [kind, setKind] = useState<WatchlistKind>('stock')
  const [scope, setScope] = useState<InstrumentScope>('stock_cn')
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Instrument[]>([])
  const [searching, setSearching] = useState(false)
  const [adding, setAdding] = useState('')
  const [error, setError] = useState('')
  const [chartItem, setChartItem] = useState<WatchlistItem | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)
  const [dragOverId, setDragOverId] = useState<number | null>(null)
  const [recognized, setRecognized] = useState<RecognizedInstrument[]>([])
  const [selectedCodes, setSelectedCodes] = useState<string[]>([])
  const [recognizing, setRecognizing] = useState(false)
  const [sparklines, setSparklines] = useState<Record<number, number[]>>({})

  async function load(showLoading = false) {
    if (showLoading) setLoading(true)
    try {
      const response = await api.watchlistQuotes(kind)
      setItems(response.items.filter((item) => instrumentScope(item) === scope))
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setItems([])
    void load(true)
  }, [kind, scope])

  useEffect(() => {
    if (!items.length) {
      setSparklines({})
      return
    }
    let active = true
    Promise.allSettled(
      items.slice(0, 20).map(async (item) => {
        const payload = await api.instrumentSeries(item.instrument_id, 31)
        return [item.instrument_id, payload.points.map((point) => point.value)] as const
      })
    ).then((results) => {
      if (!active) return
      const next: Record<number, number[]> = {}
      for (const result of results) {
        if (result.status === 'fulfilled') {
          next[result.value[0]] = result.value[1]
        }
      }
      setSparklines(next)
    })
    return () => {
      active = false
    }
  }, [items])

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load()
    }, 30_000)
    const onVisible = () => {
      if (document.visibilityState === 'visible') void load()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [kind, scope])

  useEffect(() => {
    setSearching(false)
    if (query.trim().length < 1) {
      setResults([])
      setError('')
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setSearching(true)
      setError('')
      try {
        const payload = await api.search(
          query.trim(),
          searchFiltersForScope(scope),
          controller.signal
        )
        setResults(payload.items.slice(0, 10))
      } catch (reason) {
        if (reason instanceof Error && reason.name === 'AbortError') return
        const message =
          reason instanceof Error ? reason.message : t('common.unknownError')
        setResults([])
        setError(
          message === 'instrument search unavailable'
            ? t('watchlist.searchUnavailable')
            : message
        )
      } finally {
        if (!controller.signal.aborted) setSearching(false)
      }
    }, 320)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, scope])

  const existingSymbols = useMemo(
    () => new Set(items.map((item) => `${item.market}:${item.symbol}:${item.asset_type}`)),
    [items]
  )

  async function add(item: Instrument) {
    const key = `${item.symbol}:${item.asset_type}`
    setAdding(key)
    try {
      await api.addWatchlist({ ...item, kind })
      setQuery('')
      setResults([])
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setAdding('')
    }
  }

  async function recognize(file: File) {
    setRecognizing(true)
    setError('')
    try {
      const payload = await aiApi.recognizeImage(file)
      setRecognized(payload.items)
      setSelectedCodes(
        payload.items.filter((item) => item.instrument).map((item) => item.code)
      )
    } catch {
      setError(t('watchlist.imageFailed'))
    } finally {
      setRecognizing(false)
    }
  }

  async function addRecognized() {
    const chosen = recognized.filter(
      (item) => item.instrument && selectedCodes.includes(item.code)
    )
    for (const item of chosen) {
      if (!item.instrument) continue
      await api.addWatchlist({
        ...item.instrument,
        kind: item.instrument.asset_type === 'stock' ? 'stock' : 'fund',
      })
    }
    setRecognized([])
    setSelectedCodes([])
    await load()
  }

  async function remove(item: WatchlistItem) {
    if (!window.confirm(t('watchlist.removeConfirm'))) return
    await api.removeWatchlist(item.id)
    await load()
  }

  async function reorder(sourceId: number, targetId: number) {
    const nextItems = moveItem(items, sourceId, targetId)
    if (nextItems === items) return
    setItems(nextItems)
    try {
      await api.reorderWatchlist(
        kind,
        nextItems.map((item) => item.id)
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
      await load()
    }
  }

  function switchKind(next: WatchlistKind) {
    setKind(next)
    setScope(defaultScope(next))
  }

  const visibleScopes = scopesForKind(kind)

  return (
    <>
      <PageHeader
        eyebrow={t('watchlist.eyebrow')}
        title={t('watchlist.title')}
        subtitle={t('watchlist.subtitle')}
        action={
          <Button variant="secondary" onClick={() => document.getElementById('watch-search')?.focus()}>
            <Plus size={16} />
            {t('common.add')}
          </Button>
        }
      />
      <div className="scope-switcher reveal">
        <div className="segmented-control">
          <button className={kind === 'stock' ? 'active' : ''} onClick={() => switchKind('stock')}>
            {t('watchlist.stocks')}
          </button>
          <button className={kind === 'fund' ? 'active' : ''} onClick={() => switchKind('fund')}>
            {t('watchlist.funds')}
          </button>
        </div>
        <div className="segmented-control scope-control">
          {visibleScopes.map((option) => (
            <button
              key={option.scope}
              className={scope === option.scope ? 'active' : ''}
              onClick={() => {
                setScope(option.scope)
              }}
            >
              {t(option.label)}
            </button>
          ))}
        </div>
        <span className="result-count">
          {t('watchlist.count', { count: items.length })}
        </span>
      </div>

      <GlassPanel className="search-panel reveal reveal-delay-1">
        <div className="search-input-wrap">
          <Search size={18} />
          <Input
            id="watch-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('common.search')}
            autoComplete="off"
          />
          <button
            className="icon-button"
            onClick={() => document.getElementById('watch-image')?.click()}
            disabled={recognizing}
            aria-label={t('watchlist.recognize')}
          >
            <ImagePlus size={16} />
          </button>
          <input
            id="watch-image"
            type="file"
            hidden
            accept=".jpg,.jpeg,.png,.webp,.gif"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void recognize(file)
              event.target.value = ''
            }}
          />
        </div>
        <p className="search-hint">{t('watchlist.addHint')}</p>
        {searching ? <Loading /> : null}
        {results.length ? (
          <div className="search-results">
            {results.map((item) => {
              const key = `${item.market}:${item.symbol}:${item.asset_type}`
              const exists = existingSymbols.has(key)
              return (
                <button
                  key={key}
                  className="search-result"
                  disabled={exists || adding === `${item.symbol}:${item.asset_type}`}
                  onClick={() => add(item)}
                >
                  <span>
                    <strong>{item.name}</strong>
                    <small>
                      {item.symbol} · {t(`market.${item.market}`)} · {t(`asset.${item.asset_type}`)}
                    </small>
                  </span>
                  <Badge tone={exists ? 'success' : 'accent'}>
                    {exists ? '✓' : adding === `${item.symbol}:${item.asset_type}` ? '…' : '+'}
                  </Badge>
                </button>
              )
            })}
          </div>
        ) : !searching && query.trim() && !error ? (
          <p className="muted-copy">{t('watchlist.noSearchResults')}</p>
        ) : null}
        {recognized.length ? (
          <div className="recognized-panel">
            <div className="section-head">
              <p>{t('watchlist.recognized')}</p>
              <Button
                onClick={() => void addRecognized()}
                disabled={!selectedCodes.length}
              >
                <Plus size={15} />
                {t('watchlist.addSelected')}
              </Button>
            </div>
            {recognized.map((item) => (
              <label key={item.code} className="recognized-row">
                <input
                  type="checkbox"
                  checked={selectedCodes.includes(item.code)}
                  disabled={!item.instrument}
                  onChange={(event) =>
                    setSelectedCodes((current) =>
                      event.target.checked
                        ? [...current, item.code]
                        : current.filter((code) => code !== item.code)
                    )
                  }
                />
                <span>
                  <strong>{item.name || item.code}</strong>
                  <small>
                    {item.code} · {t(`ai.imageConfidence.${item.confidence}`)}
                  </small>
                </span>
                {item.instrument ? (
                  <Badge tone="accent">{t(`asset.${item.instrument.asset_type}`)}</Badge>
                ) : (
                  <Badge tone="warn">{t('watchlist.imageUnresolved')}</Badge>
                )}
              </label>
            ))}
          </div>
        ) : null}
      </GlassPanel>

      {error ? <p className="form-error">{error}</p> : null}
      {loading ? (
        <Loading />
      ) : items.length ? (
        <div className="instrument-grid">
          {items.map((item) => (
            <div
              className={[
                'instrument-drag-shell',
                draggingId === item.id ? 'dragging' : '',
                dragOverId === item.id && draggingId !== item.id ? 'drag-over' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              key={item.id}
              draggable
              title={t('watchlist.dragHint')}
              onDragStart={(event) => {
                setDraggingId(item.id)
                event.dataTransfer.effectAllowed = 'move'
                event.dataTransfer.setData('text/plain', String(item.id))
              }}
              onDragOver={(event) => {
                event.preventDefault()
                event.dataTransfer.dropEffect = 'move'
                setDragOverId(item.id)
              }}
              onDrop={(event) => {
                event.preventDefault()
                const sourceId =
                  Number(event.dataTransfer.getData('text/plain')) || draggingId
                if (sourceId) void reorder(sourceId, item.id)
                setDraggingId(null)
                setDragOverId(null)
              }}
              onDragEnd={() => {
                setDraggingId(null)
                setDragOverId(null)
              }}
            >
              <GlassPanel className="instrument-card reveal">
                <div className="instrument-card-head">
                  <div className="instrument-identity">
                    <InstrumentMark name={item.name} symbol={item.symbol} market={item.market} />
                    <span>
                      <strong>{item.name}</strong>
                      <small>
                        {item.symbol} · {t(`asset.${item.asset_type}`)}
                      </small>
                    </span>
                  </div>
                  <div className="instrument-card-tools">
                    <DataState quote={item.quote} />
                    <span className="drag-handle" aria-hidden="true">
                      <GripVertical size={16} />
                    </span>
                  </div>
                </div>
                <div className="price-display">
                  <strong>{item.quote?.current_price?.toFixed(2) ?? '--'}</strong>
                  <span className={changeClass(item.quote?.change_pct)}>
                    {formatPercent(item.quote?.change_pct)}
                  </span>
                </div>
                <Sparkline
                  values={sparklines[item.instrument_id] ?? []}
                  tone={(item.quote?.change_pct ?? 0) < 0 ? 'down' : 'up'}
                />
                <div className="instrument-actions">
                  <button className="button button-ghost" onClick={() => setChartItem(item)}>
                    <LineChartIcon size={15} />
                    1Y
                  </button>
                  <Button
                    variant="ghost"
                    onClick={() => navigate(`/alerts?instrument=${item.instrument_id}`)}
                  >
                    <BellRing size={15} />
                    {t('alerts.create')}
                  </Button>
                  <button className="icon-button danger" onClick={() => remove(item)} aria-label={t('common.delete')}>
                    <Trash2 size={15} />
                  </button>
                </div>
              </GlassPanel>
            </div>
          ))}
        </div>
      ) : (
        <GlassPanel>
          <EmptyState title={t(kind === 'stock' ? 'watchlist.emptyStock' : 'watchlist.emptyFund')} />
        </GlassPanel>
      )}
      <InstrumentDetailModal item={chartItem} onClose={() => setChartItem(null)} />
    </>
  )
}

