import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import { api } from '../api'
import {
  AllocationRing,
  Button,
  EmptyState,
  Field,
  GlassPanel,
  Input,
  InstrumentMark,
  Loading,
  Modal,
  PageHeader,
  Select,
} from '../components/ui'
import {
  changeClass,
  currencyTotals,
  formatMoney,
  formatPercent,
  type Language,
} from '../lib'
import type { Holding, WatchlistItem } from '../types'

export function HoldingsPage() {
  const { t, i18n } = useTranslation()
  const language = i18n.language as Language
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Holding | null>(null)
  const [instrumentId, setInstrumentId] = useState<number | ''>('')
  const [quantity, setQuantity] = useState('')
  const [averageCost, setAverageCost] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [holdingPayload, stockPayload, fundPayload] = await Promise.all([
        api.holdings(),
        api.watchlist('stock'),
        api.watchlist('fund'),
      ])
      setHoldings(holdingPayload.items)
      setWatchlist([...stockPayload.items, ...fundPayload.items])
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load()
    }, 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const uniqueWatchlist = useMemo(() => {
    const seen = new Set<number>()
    return watchlist.filter((item) => {
      if (seen.has(item.instrument_id)) return false
      seen.add(item.instrument_id)
      return true
    })
  }, [watchlist])

  const totals = currencyTotals(holdings)
  const pnlByCurrency = holdings.reduce<Record<string, number>>((result, holding) => {
    if (holding.unrealized_pnl === null) return result
    result[holding.currency] = (result[holding.currency] ?? 0) + holding.unrealized_pnl
    return result
  }, {})
  const marketCounts = holdings.reduce<Record<string, number>>((result, holding) => {
    result[holding.market] = (result[holding.market] ?? 0) + 1
    return result
  }, {})
  const allocation = Object.entries(marketCounts).map(([market, count], index) => ({
    market,
    count,
    value: holdings.length ? (count / holdings.length) * 100 : 0,
    color: ['var(--color-accent)', 'var(--color-cyan)', 'var(--color-violet)', 'var(--color-amber)'][
      index % 4
    ],
  }))

  function openAdd() {
    setEditing(null)
    setInstrumentId('')
    setQuantity('')
    setAverageCost('')
    setNote('')
    setModalOpen(true)
  }

  function openEdit(holding: Holding) {
    setEditing(holding)
    setInstrumentId(holding.instrument_id)
    setQuantity(String(holding.quantity))
    setAverageCost(String(holding.average_cost))
    setNote(holding.note)
    setModalOpen(true)
  }

  async function save() {
    const target = Number(instrumentId)
    if (!target || Number(quantity) < 0 || Number(averageCost) < 0) {
      setError(t('common.required'))
      return
    }
    try {
      await api.upsertHolding({
        instrument_id: target,
        quantity: Number(quantity),
        average_cost: Number(averageCost),
        note,
      })
      setModalOpen(false)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    }
  }

  async function remove(holding: Holding) {
    await api.removeHolding(holding.id)
    await load()
  }

  return (
    <>
      <PageHeader
        eyebrow={t('holdings.eyebrow')}
        title={t('holdings.title')}
        subtitle={t('holdings.subtitle')}
        action={
          <Button onClick={openAdd}>
            <Plus size={16} />
            {t('holdings.add')}
          </Button>
        }
      />
      {error ? <p className="form-error">{error}</p> : null}
      {loading ? (
        <Loading />
      ) : holdings.length ? (
        <>
          <div className="holding-summary reveal">
            {Object.entries(totals).map(([currency, value], index) => (
              <GlassPanel
                className={`summary-card ${index === 0 ? 'summary-main' : ''}`}
                key={currency}
              >
                <p className="eyebrow">
                  {t('holdings.currencyValue')} · {currency}
                </p>
                <strong>{formatMoney(value, currency, language)}</strong>
                <span>
                  {t('holdings.pnlInCurrency', {
                    value: formatMoney(pnlByCurrency[currency] ?? 0, currency, language),
                  })}
                </span>
              </GlassPanel>
            ))}
            <GlassPanel className="summary-card allocation-card">
              <AllocationRing segments={allocation} />
              <div className="allocation-legend">
                <p className="eyebrow">{t('holdings.allocation')}</p>
                {allocation.map((item) => (
                  <span key={item.market}>
                    <i style={{ background: item.color }} />
                    {t(`market.${item.market}`)} {item.count}
                  </span>
                ))}
              </div>
            </GlassPanel>
          </div>
          <GlassPanel className="table-panel reveal reveal-delay-1">
            <div className="section-head">
              <div>
                <p className="eyebrow">{t('holdings.positions')}</p>
                <h2>{t('holdings.current')}</h2>
              </div>
              <span className="result-count">
                {t('holdings.count', { count: holdings.length })}
              </span>
            </div>
            <div className="data-table holdings-table">
              <div className="data-row data-head">
                <span>{t('holdings.instrument')}</span>
                <span>{t('holdings.quantity')}</span>
                <span>{t('holdings.averageCost')}</span>
                <span>{t('common.price')}</span>
                <span>{t('holdings.marketValue')}</span>
                <span>{t('holdings.pnl')}</span>
                <span />
              </div>
              {holdings.map((holding) => (
                <div className="data-row" key={holding.id}>
                  <div className="instrument-identity">
                    <InstrumentMark
                      name={holding.name}
                      symbol={holding.symbol}
                      market={holding.market}
                    />
                    <span>
                      <strong>{holding.name}</strong>
                      <small>{holding.symbol} · {t(`asset.${holding.asset_type}`)}</small>
                    </span>
                  </div>
                  <span>{holding.quantity}</span>
                  <span>{holding.average_cost.toFixed(2)}</span>
                  <span>{holding.current_price?.toFixed(2) ?? '--'}</span>
                  <span>
                    {holding.market_value === null
                      ? '--'
                      : formatMoney(holding.market_value, holding.currency, language)}
                  </span>
                  <span className={changeClass(holding.unrealized_pnl)}>
                    {holding.unrealized_pnl === null
                      ? '--'
                      : formatMoney(holding.unrealized_pnl, holding.currency, language)}
                    {holding.quote?.change_pct !== null && holding.quote?.change_pct !== undefined ? (
                      <small className="table-subvalue">{formatPercent(holding.quote.change_pct)}</small>
                    ) : null}
                  </span>
                  <span className="inline-actions">
                    <button className="icon-button" onClick={() => openEdit(holding)} aria-label={t('common.edit')}>
                      <Pencil size={15} />
                    </button>
                    <button className="icon-button danger" onClick={() => remove(holding)} aria-label={t('common.delete')}>
                      <Trash2 size={15} />
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </GlassPanel>
        </>
      ) : (
        <GlassPanel>
          <EmptyState title={t('holdings.empty')} action={<Button onClick={openAdd}>{t('holdings.add')}</Button>} />
        </GlassPanel>
      )}

      <Modal
        open={modalOpen}
        title={t(editing ? 'holdings.edit' : 'holdings.add')}
        onClose={() => setModalOpen(false)}
      >
        <div className="form-grid">
          <Field label={t('holdings.instrument')}>
            <Select
              value={instrumentId}
              onChange={(event) => setInstrumentId(Number(event.target.value))}
              disabled={Boolean(editing)}
            >
              <option value="">{t('holdings.chooseInstrument')}</option>
              {uniqueWatchlist.map((item) => (
                <option value={item.instrument_id} key={item.instrument_id}>
                  {item.name} · {item.symbol}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('holdings.quantity')}>
            <Input
              type="number"
              min="0"
              step="any"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />
          </Field>
          <Field label={t('holdings.averageCost')}>
            <Input
              type="number"
              min="0"
              step="any"
              value={averageCost}
              onChange={(event) => setAverageCost(event.target.value)}
            />
          </Field>
          <Field label={t('holdings.note')}>
            <Input value={note} onChange={(event) => setNote(event.target.value)} />
          </Field>
        </div>
        <div className="modal-actions">
          <Button variant="ghost" onClick={() => setModalOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button onClick={save}>{t('common.save')}</Button>
        </div>
      </Modal>
    </>
  )
}

