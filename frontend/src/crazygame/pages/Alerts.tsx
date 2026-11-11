import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BellPlus, CheckCircle2, Pencil, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { api } from '../api'
import {
  Badge,
  Button,
  EmptyState,
  Field,
  GlassPanel,
  Input,
  InstrumentMark,
  Loading,
  Modal,
  PageHeader,
  ProgressBar,
  Select,
} from '../components/ui'
import { changeClass, formatDateTime, formatPercent, type Language } from '../lib'
import type { AlertHit, AlertRule, NotifyChannel, WatchlistItem } from '../types'

type Tab = 'rules' | 'hits'
type AlertFrequency = 'daily' | '30m' | '1h' | '6h' | `minutes:${number}`

const FREQUENCY_MINUTES: Record<Exclude<AlertFrequency, 'daily' | `minutes:${number}`>, number> = {
  '30m': 30,
  '1h': 60,
  '6h': 360,
}

function frequencyForRule(rule: AlertRule): AlertFrequency {
  if (rule.once_per_day) return 'daily'
  const standard = (Object.entries(FREQUENCY_MINUTES) as Array<
    [Exclude<AlertFrequency, 'daily' | `minutes:${number}`>, number]
  >).find(([, minutes]) => minutes === rule.cooldown_minutes)
  return standard?.[0] ?? `minutes:${rule.cooldown_minutes}`
}

function frequencyMinutes(frequency: AlertFrequency): number {
  if (frequency === 'daily') return 30
  if (frequency.startsWith('minutes:')) {
    return Math.max(1, Number(frequency.split(':')[1]) || 30)
  }
  return FREQUENCY_MINUTES[frequency as keyof typeof FREQUENCY_MINUTES]
}

export function AlertsPage() {
  const { t, i18n } = useTranslation()
  const language = i18n.language as Language
  const [searchParams] = useSearchParams()
  const initialInstrument = Number(searchParams.get('instrument') || 0)
  const [tab, setTab] = useState<Tab>('rules')
  const [rules, setRules] = useState<AlertRule[]>([])
  const [hits, setHits] = useState<AlertHit[]>([])
  const [channels, setChannels] = useState<NotifyChannel[]>([])
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(Boolean(initialInstrument))
  const [editing, setEditing] = useState<AlertRule | null>(null)
  const [instrumentId, setInstrumentId] = useState<number | ''>(initialInstrument || '')
  const [name, setName] = useState('')
  const [metric, setMetric] = useState<'price' | 'change_pct'>('price')
  const [direction, setDirection] = useState<'above' | 'below'>('above')
  const [threshold, setThreshold] = useState('')
  const [selectedChannels, setSelectedChannels] = useState<number[]>([])
  const [frequency, setFrequency] = useState<AlertFrequency>('daily')
  const [marketHoursOnly, setMarketHoursOnly] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [runNow, setRunNow] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [rulePayload, hitPayload, channelPayload, stockPayload, fundPayload] =
        await Promise.all([
          api.alerts(),
          api.alertHits(),
          api.channels(),
          api.watchlistQuotes('stock'),
          api.watchlistQuotes('fund'),
        ])
      setRules(rulePayload.items)
      setHits(hitPayload.items)
      setChannels(channelPayload.items)
      setWatchlist([...stockPayload.items, ...fundPayload.items])
      setSelectedChannels((current) =>
        current.length
          ? current
          : channelPayload.items.filter((channel) => channel.enabled).map((channel) => channel.id)
      )
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const uniqueWatchlist = useMemo(() => {
    const seen = new Set<number>()
    return watchlist.filter((item) => {
      if (seen.has(item.instrument_id)) return false
      seen.add(item.instrument_id)
      return true
    })
  }, [watchlist])

  function openCreate() {
    setEditing(null)
    setInstrumentId(initialInstrument || '')
    setName('')
    setMetric('price')
    setDirection('above')
    setThreshold('')
    setFrequency('daily')
    setMarketHoursOnly(true)
    setRunNow(false)
    setNotice('')
    setModalOpen(true)
  }

  function openEdit(rule: AlertRule) {
    setEditing(rule)
    setInstrumentId(rule.instrument_id)
    setName(rule.name)
    setMetric(rule.metric)
    setDirection(rule.direction)
    setThreshold(String(rule.threshold))
    setSelectedChannels(rule.channel_ids)
    setFrequency(frequencyForRule(rule))
    setMarketHoursOnly(rule.market_hours_only)
    setRunNow(false)
    setNotice('')
    setModalOpen(true)
  }

  async function save() {
    setError('')
    setNotice('')
    const target = Number(instrumentId)
    if (!target || threshold === '' || !selectedChannels.length) {
      setError(t('common.required'))
      return
    }
    try {
      const payload = {
        name:
          name.trim() ||
          t('alerts.defaultName', {
            metric: t(metric === 'price' ? 'alerts.metricPrice' : 'alerts.metricChange'),
            direction: t(direction === 'above' ? 'alerts.above' : 'alerts.below'),
            threshold,
          }),
        metric,
        direction,
        threshold: Number(threshold),
        channel_ids: selectedChannels,
        once_per_day: frequency === 'daily',
        market_hours_only: marketHoursOnly,
        cooldown_minutes: frequencyMinutes(frequency),
      } as const
      if (editing) {
        await api.updateAlert(editing.id, payload)
        setNotice(t('alerts.updated'))
      } else {
        const created = await api.createAlert({
          instrument_id: target,
          ...payload,
          run_now: runNow,
        })
        const immediate = created.run_result?.scan
        setNotice(
          runNow
            ? immediate?.triggered
              ? t('alerts.immediateTriggered')
              : immediate?.reason === 'market_closed'
                ? t('alerts.immediateMarketClosed')
                : immediate?.reason === 'quote_unavailable'
                  ? t('alerts.immediateQuoteUnavailable')
                  : t('alerts.immediateChecked')
            : t('alerts.saved')
        )
      }
      setModalOpen(false)
      setEditing(null)
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    }
  }

  async function remove(rule: AlertRule) {
    if (!window.confirm(t('alerts.deleteConfirm'))) return
    await api.removeAlert(rule.id)
    await load()
  }

  async function toggle(rule: AlertRule) {
    await api.setAlertEnabled(rule.id, !rule.enabled)
    await load()
  }

  function ruleValue(rule: AlertRule): number | null {
    if (rule.metric === 'price') return rule.quote?.current_price ?? null
    return rule.quote?.change_pct ?? null
  }

  function progressFor(rule: AlertRule): number {
    const value = ruleValue(rule)
    if (value === null || !rule.enabled) return 0
    const span = Math.max(Math.abs(rule.threshold), 1)
    return Math.max(0, Math.min(100, 100 - (Math.abs(value - rule.threshold) / span) * 100))
  }

  function valueText(rule: AlertRule): string {
    const value = ruleValue(rule)
    if (rule.metric === 'change_pct') return formatPercent(value)
    return value === null ? '--' : value.toFixed(2)
  }

  return (
    <>
      <PageHeader
        eyebrow={t('alerts.eyebrow')}
        title={t('alerts.title')}
        subtitle={t('alerts.subtitle')}
        action={
          <Button onClick={openCreate}>
            <BellPlus size={16} />
            {t('alerts.create')}
          </Button>
        }
      />
      {error ? <p className="form-error">{error}</p> : null}
      {notice ? <p className="form-success"><CheckCircle2 size={15} />{notice}</p> : null}
      <div className="alert-toolbar reveal">
        <div className="segmented-control">
        <button className={tab === 'rules' ? 'active' : ''} onClick={() => setTab('rules')}>
          {t('alerts.rules')} <span>{rules.length}</span>
        </button>
        <button className={tab === 'hits' ? 'active' : ''} onClick={() => setTab('hits')}>
          {t('alerts.hits')} <span>{hits.length}</span>
        </button>
        </div>
        <span className="status-chip">
          <i />
          {t('alerts.armedCount', {
            count: rules.filter((rule) => rule.enabled).length,
          })}
        </span>
      </div>

      {loading ? (
        <Loading />
      ) : tab === 'rules' ? (
        rules.length ? (
          <div className="alert-layout">
          <div className="alert-cards">
            {rules.map((rule) => (
              <GlassPanel
                className={`alert-card reveal ${rule.enabled ? 'is-armed' : 'is-paused'}`}
                key={rule.id}
              >
                <div className="alert-card-top">
                  <InstrumentMark
                    name={rule.instrument_name}
                    symbol={rule.symbol}
                    market={rule.market}
                  />
                  <button
                    className="plain-status"
                    onClick={() => toggle(rule)}
                    aria-label={t(rule.enabled ? 'alerts.disable' : 'alerts.enable')}
                  >
                    <Badge tone={rule.enabled ? 'success' : 'neutral'}>
                      <i className="status-dot" />
                      {t(rule.enabled ? 'alerts.monitoring' : 'alerts.paused')}
                    </Badge>
                  </button>
                </div>
                <p className="eyebrow">
                  {t(rule.metric === 'price' ? 'alerts.priceRule' : 'alerts.changeRule')}
                </p>
                <h2>{rule.instrument_name}</h2>
                <p className="alert-rule-name">{rule.name}</p>
                <div className="alert-rule">
                  <span>
                    {t(rule.direction === 'above' ? 'alerts.above' : 'alerts.below')}
                  </span>
                  <strong>
                    {rule.metric === 'change_pct'
                      ? formatPercent(rule.threshold)
                      : rule.threshold.toFixed(2)}
                  </strong>
                  <small>
                    {t('alerts.currentValue', { value: valueText(rule) })}
                  </small>
                </div>
                <ProgressBar
                  value={progressFor(rule)}
                  tone={rule.enabled ? 'default' : 'muted'}
                />
                <div className="alert-meta">
                  <span>
                    {rule.market_hours_only ? t('alerts.marketHoursOnly') : t('alerts.allHours')}
                    {' · '}
                    {rule.once_per_day
                      ? t('alerts.oncePerDay')
                      : t('alerts.cooldownMinutes', { count: rule.cooldown_minutes })}
                  </span>
                  <button type="button" onClick={() => openEdit(rule)}>
                    <Pencil size={13} />
                    {t('common.edit')}
                  </button>
                </div>
                <button
                  className="icon-button danger alert-delete"
                  onClick={() => remove(rule)}
                  aria-label={t('common.delete')}
                >
                  <Trash2 size={15} />
                </button>
              </GlassPanel>
            ))}
          </div>
          <GlassPanel className="alert-timeline reveal">
            <div className="section-head">
              <div>
                <p className="eyebrow">{t('alerts.recentHits')}</p>
                <h2>{t('alerts.hits')}</h2>
              </div>
              <Badge>{hits.length}</Badge>
            </div>
            {hits.length ? (
              <div className="timeline-list">
                {hits.slice(0, 4).map((hit) => (
                  <div className="timeline-item" key={hit.id}>
                    <i className="timeline-glow" />
                    <div>
                      <strong>{hit.rule_name}</strong>
                      <p>
                        {hit.instrument_name} · {hit.observed_value.toFixed(2)}
                      </p>
                      <small>{formatDateTime(hit.triggered_at, language)}</small>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-copy">{t('alerts.noHits')}</p>
            )}
            <Button variant="ghost" className="full-button" onClick={() => setTab('hits')}>
              {t('alerts.viewAllHits')}
            </Button>
          </GlassPanel>
          </div>
        ) : (
          <GlassPanel>
            <EmptyState
              title={t('alerts.noRules')}
              action={<Button onClick={openCreate}>{t('alerts.create')}</Button>}
            />
          </GlassPanel>
        )
      ) : hits.length ? (
        <GlassPanel className="table-panel reveal">
          <div className="hit-list">
            {hits.map((hit) => (
              <div className="hit-row" key={hit.id}>
                <CheckCircle2 size={17} />
                <div>
                  <strong>{hit.rule_name}</strong>
                  <p>
                    {hit.instrument_name} {hit.symbol} ·{' '}
                    <span className={changeClass(hit.observed_value)}>
                      {hit.observed_value.toFixed(2)}
                    </span>
                  </p>
                </div>
                <small>{formatDateTime(hit.triggered_at, language)}</small>
                <div className="delivery-pills">
                  {hit.deliveries.map((delivery) => (
                    <Badge
                      key={delivery.id}
                      tone={delivery.status === 'delivered' ? 'success' : delivery.status === 'failed' ? 'warn' : 'neutral'}
                    >
                      {delivery.status}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </GlassPanel>
      ) : (
        <GlassPanel>
          <EmptyState title={t('alerts.noHits')} />
        </GlassPanel>
      )}

      <Modal
        open={modalOpen}
        title={t(editing ? 'alerts.edit' : 'alerts.create')}
        onClose={() => {
          setModalOpen(false)
          setEditing(null)
        }}
      >
        {!channels.length ? <p className="form-error">{t('alerts.noChannels')}</p> : null}
        <div className="form-grid">
          <Field label={t('alerts.instrument')}>
            <Select value={instrumentId} onChange={(event) => setInstrumentId(Number(event.target.value))}>
              <option value="">{t('holdings.chooseInstrument')}</option>
              {uniqueWatchlist.map((item) => (
                <option value={item.instrument_id} key={item.instrument_id}>
                  {item.name} · {item.symbol}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('alerts.ruleName')}>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label={t('alerts.metric')}>
            <Select value={metric} onChange={(event) => setMetric(event.target.value as 'price' | 'change_pct')}>
              <option value="price">{t('alerts.metricPrice')}</option>
              <option value="change_pct">{t('alerts.metricChange')}</option>
            </Select>
          </Field>
          <Field label={t('alerts.direction')}>
            <Select value={direction} onChange={(event) => setDirection(event.target.value as 'above' | 'below')}>
              <option value="above">{t('alerts.above')}</option>
              <option value="below">{t('alerts.below')}</option>
            </Select>
          </Field>
          <Field label={t('alerts.threshold')}>
            <Input
              type="number"
              step="any"
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
            />
          </Field>
          <Field label={t('alerts.frequency')}>
            <Select
              value={frequency}
              onChange={(event) => setFrequency(event.target.value as AlertFrequency)}
            >
              <option value="daily">{t('alerts.frequencyDaily')}</option>
              <option value="30m">{t('alerts.frequency30m')}</option>
              <option value="1h">{t('alerts.frequency1h')}</option>
              <option value="6h">{t('alerts.frequency6h')}</option>
              {frequency.startsWith('minutes:') ? (
                <option value={frequency}>
                  {t('alerts.frequencyCustom', {
                    count: frequencyMinutes(frequency),
                  })}
                </option>
              ) : null}
            </Select>
          </Field>
        </div>
        <div className="check-grid">
          <label className="check-row">
            <input type="checkbox" checked={marketHoursOnly} onChange={(event) => setMarketHoursOnly(event.target.checked)} />
            {t('alerts.marketHoursOnly')}
          </label>
          {!editing ? (
            <label className="check-row">
              <input type="checkbox" checked={runNow} onChange={(event) => setRunNow(event.target.checked)} />
              {t('alerts.runNow')}
            </label>
          ) : null}
        </div>
        <Field label={t('alerts.channels')}>
          <div className="channel-checks">
            {channels.map((channel) => (
              <label key={channel.id} className="check-row">
                <input
                  type="checkbox"
                  checked={selectedChannels.includes(channel.id)}
                  onChange={(event) =>
                    setSelectedChannels((current) =>
                      event.target.checked
                        ? [...current, channel.id]
                        : current.filter((id) => id !== channel.id)
                    )
                  }
                />
                {channel.name} · {channel.type === 'feishu' ? 'Feishu' : 'SMS'}
              </label>
            ))}
          </div>
        </Field>
        <div className="modal-actions">
          <Button
            variant="ghost"
            onClick={() => {
              setModalOpen(false)
              setEditing(null)
            }}
          >
            {t('common.cancel')}
          </Button>
          <Button onClick={save}>{t('common.save')}</Button>
        </div>
      </Modal>
    </>
  )
}

