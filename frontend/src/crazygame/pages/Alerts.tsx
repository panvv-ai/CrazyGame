import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BellPlus, CheckCircle2, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { api } from '../api'
import {
  Badge,
  Button,
  EmptyState,
  Field,
  GlassPanel,
  Input,
  Loading,
  Modal,
  PageHeader,
  Select,
} from '../components/ui'
import { changeClass, formatDateTime, type Language } from '../lib'
import type { AlertHit, AlertRule, NotifyChannel, WatchlistItem } from '../types'

type Tab = 'rules' | 'hits'

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
  const [instrumentId, setInstrumentId] = useState<number | ''>(initialInstrument || '')
  const [name, setName] = useState('')
  const [metric, setMetric] = useState<'price' | 'change_pct'>('price')
  const [direction, setDirection] = useState<'above' | 'below'>('above')
  const [threshold, setThreshold] = useState('')
  const [selectedChannels, setSelectedChannels] = useState<number[]>([])
  const [oncePerDay, setOncePerDay] = useState(true)
  const [marketHoursOnly, setMarketHoursOnly] = useState(true)
  const [cooldown, setCooldown] = useState('30')
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [rulePayload, hitPayload, channelPayload, stockPayload, fundPayload] =
        await Promise.all([
          api.alerts(),
          api.alertHits(),
          api.channels(),
          api.watchlist('stock'),
          api.watchlist('fund'),
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

  async function create() {
    const target = Number(instrumentId)
    if (!target || threshold === '' || !selectedChannels.length) {
      setError(t('common.required'))
      return
    }
    try {
      await api.createAlert({
        instrument_id: target,
        name: name.trim() || `${metric} ${direction} ${threshold}`,
        metric,
        direction,
        threshold: Number(threshold),
        channel_ids: selectedChannels,
        once_per_day: oncePerDay,
        market_hours_only: marketHoursOnly,
        cooldown_minutes: Number(cooldown),
      })
      setModalOpen(false)
      setName('')
      setThreshold('')
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

  return (
    <>
      <PageHeader
        title={t('alerts.title')}
        subtitle={t('alerts.subtitle')}
        action={
          <Button onClick={() => setModalOpen(true)}>
            <BellPlus size={16} />
            {t('alerts.create')}
          </Button>
        }
      />
      {error ? <p className="form-error">{error}</p> : null}
      <div className="segmented-control reveal">
        <button className={tab === 'rules' ? 'active' : ''} onClick={() => setTab('rules')}>
          {t('alerts.rules')}
        </button>
        <button className={tab === 'hits' ? 'active' : ''} onClick={() => setTab('hits')}>
          {t('alerts.hits')}
        </button>
      </div>

      {loading ? (
        <Loading />
      ) : tab === 'rules' ? (
        rules.length ? (
          <div className="alert-grid">
            {rules.map((rule) => (
              <GlassPanel className="alert-card reveal" key={rule.id}>
                <div className="instrument-card-head">
                  <div className="instrument-identity">
                    <span className="market-monogram">{rule.market.slice(0, 2)}</span>
                    <span>
                      <strong>{rule.name}</strong>
                      <small>
                        {rule.symbol} · {t(`market.${rule.market}`)}
                      </small>
                    </span>
                  </div>
                  <button className="plain-status" onClick={() => toggle(rule)}>
                    <Badge tone={rule.enabled ? 'success' : 'neutral'}>
                      {rule.enabled ? 'ON' : 'OFF'}
                    </Badge>
                  </button>
                </div>
                <div className="rule-expression">
                  <span>{t(rule.metric === 'price' ? 'alerts.metricPrice' : 'alerts.metricChange')}</span>
                  <strong>{t(rule.direction === 'above' ? 'alerts.above' : 'alerts.below')}</strong>
                  <em>{rule.threshold}</em>
                </div>
                <div className="alert-meta">
                  <span>{rule.channel_ids.length} {t('alerts.channels')}</span>
                  <span>{rule.once_per_day ? t('alerts.oncePerDay') : `${rule.cooldown_minutes} min`}</span>
                </div>
                <button className="icon-button danger alert-delete" onClick={() => remove(rule)} aria-label={t('common.delete')}>
                  <Trash2 size={15} />
                </button>
              </GlassPanel>
            ))}
          </div>
        ) : (
          <GlassPanel>
            <EmptyState
              title={t('alerts.noRules')}
              action={<Button onClick={() => setModalOpen(true)}>{t('alerts.create')}</Button>}
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

      <Modal open={modalOpen} title={t('alerts.create')} onClose={() => setModalOpen(false)}>
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
          <Field label={t('alerts.cooldown')}>
            <Input type="number" min="0" value={cooldown} onChange={(event) => setCooldown(event.target.value)} />
          </Field>
        </div>
        <div className="check-grid">
          <label className="check-row">
            <input type="checkbox" checked={oncePerDay} onChange={(event) => setOncePerDay(event.target.checked)} />
            {t('alerts.oncePerDay')}
          </label>
          <label className="check-row">
            <input type="checkbox" checked={marketHoursOnly} onChange={(event) => setMarketHoursOnly(event.target.checked)} />
            {t('alerts.marketHoursOnly')}
          </label>
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
          <Button variant="ghost" onClick={() => setModalOpen(false)}>{t('common.cancel')}</Button>
          <Button onClick={create}>{t('common.save')}</Button>
        </div>
      </Modal>
    </>
  )
}

