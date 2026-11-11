import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight, BellRing, Plus, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { DataState } from '../components/DataState'
import { InstrumentDetailModal } from '../components/InstrumentDetailModal'
import { LineChart } from '../components/LineChart'
import { MarkdownReport } from '../components/MarkdownReport'
import {
  Badge,
  Button,
  EmptyState,
  GlassPanel,
  Loading,
  Metric,
  Modal,
  PageHeader,
} from '../components/ui'
import {
  changeClass,
  formatDateTime,
  formatPercent,
  latestSeriesChange,
  portfolioCurrencySnapshots,
  type Language,
} from '../lib'
import type {
  AlertHit,
  AssetGroup,
  DailyReview,
  GroupPoint,
  Holding,
  PortfolioSeries,
  WatchlistItem,
} from '../types'

interface OverviewData {
  watchlist: WatchlistItem[]
  groups: AssetGroup[]
  hits: AlertHit[]
  review: DailyReview | null
  holdings: Holding[]
  groupSeries: GroupPoint[]
}

export function OverviewPage() {
  const { t, i18n } = useTranslation()
  const language = i18n.language as Language
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [detailItem, setDetailItem] = useState<WatchlistItem | null>(null)
  const [heroMode, setHeroMode] = useState<'holdings' | 'groups'>('holdings')
  const [holdingSeries, setHoldingSeries] = useState<PortfolioSeries[]>([])

  async function load() {
    try {
      setError('')
      const [watchlist, groupPayload, hits, reviews, holdingPayload] = await Promise.all([
        api.watchlistQuotes(),
        api.groups(),
        api.alertHits(),
        api.dailyReviews(),
        api.holdings(),
      ])
      const groups = await Promise.all(
        groupPayload.items.map((group) => api.groupSummary(group.id))
      ).then((items) => items.filter((group) => group.scope !== 'mixed'))
      setData((current) => ({
        watchlist: watchlist.items,
        groups,
        hits: hits.items.slice(0, 4),
        review: reviews.items[0] ?? null,
        holdings: holdingPayload.items,
        groupSeries: current?.groupSeries ?? [],
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    }
  }

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load()
    }, 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const leadGroupId = data?.groups[0]?.id
  useEffect(() => {
    if (!leadGroupId) {
      setData((current) => (current ? { ...current, groupSeries: [] } : current))
      return
    }
    let active = true
    api
      .groupSeries(leadGroupId, 365)
      .then((payload) => {
        if (active) {
          setData((current) =>
            current ? { ...current, groupSeries: payload.points } : current
          )
        }
      })
      .catch(() => {
        if (active) {
          setData((current) =>
            current ? { ...current, groupSeries: [] } : current
          )
        }
      })
    return () => {
      active = false
    }
  }, [leadGroupId])

  const holdingSeriesKey =
    data?.holdings
      .map((holding) => `${holding.instrument_id}:${holding.quantity}`)
      .sort()
      .join('|') ?? ''
  useEffect(() => {
    if (!holdingSeriesKey) {
      setHoldingSeries([])
      return
    }
    let active = true
    api
      .holdingSeries(365)
      .then((payload) => {
        if (active) setHoldingSeries(payload.series)
      })
      .catch(() => {
        if (active) setHoldingSeries([])
      })
    return () => {
      active = false
    }
  }, [holdingSeriesKey])

  async function runReview() {
    setRunning(true)
    try {
      const result = await api.runDailyReview()
      if (result.status === 'skipped') {
        setError(t('overview.aiNotConfigured'))
        return
      }
      await load()
    } finally {
      setRunning(false)
    }
  }

  if (!data && !error) {
    return <Loading />
  }
  if (!data) {
    return (
      <GlassPanel>
        <p className="form-error">{error}</p>
        <Button onClick={load}>{t('common.retry')}</Button>
      </GlassPanel>
    )
  }

  const leadGroup = data.groups[0]
  const holdingSnapshots = portfolioCurrencySnapshots(data.holdings)
  const holdingMetrics = holdingSnapshots.slice(0, 3).map((snapshot) => {
    const series = holdingSeries.find(
      (item) => item.currency === snapshot.currency
    )
    const lastPoint = series?.points[series.points.length - 1]
    return {
      currency: snapshot.currency,
      dayChange:
        snapshot.dayChange ?? latestSeriesChange(series?.points ?? []),
      coverage: snapshot.coverage || lastPoint?.coverage || 0,
    }
  })
  const today = new Intl.DateTimeFormat(language, {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date())

  return (
    <>
      <PageHeader
        eyebrow={t('overview.eyebrow')}
        title={t('overview.greeting')}
        subtitle={t('overview.subtitle')}
        action={<span className="quiet-date">{today}</span>}
      />
      {error ? <p className="form-error">{error}</p> : null}

      <section className="overview-hero reveal">
        <div className="hero-copy">
          <div className="hero-mode-switch segmented-control" role="tablist">
            <button
              role="tab"
              aria-selected={heroMode === 'holdings'}
              className={heroMode === 'holdings' ? 'active' : ''}
              onClick={() => setHeroMode('holdings')}
            >
              {t('overview.holdingsTab')}
            </button>
            <button
              role="tab"
              aria-selected={heroMode === 'groups'}
              className={heroMode === 'groups' ? 'active' : ''}
              onClick={() => setHeroMode('groups')}
            >
              {t('overview.groupsTab')}
            </button>
          </div>
          {heroMode === 'holdings' ? (
            <>
              <div className="hero-eyebrow">{t('nav.holdings')}</div>
              <h2>{t('overview.myHoldings')}</h2>
              <p>
                {data.holdings.length
                  ? t('overview.holdingCount', { count: data.holdings.length })
                  : t('overview.noHoldings')}
              </p>
              {data.holdings.length ? (
                <div className="hero-value-row">
                  <div className="portfolio-day-metrics">
                    {holdingMetrics.map((snapshot) => (
                      <Metric
                        key={snapshot.currency}
                        label={`${t('overview.todayHolding')} · ${snapshot.currency}`}
                        value={formatPercent(snapshot.dayChange)}
                        tone={changeClass(snapshot.dayChange)}
                        detail={`${t('groups.coverage')} ${Math.round(snapshot.coverage * 100)}%`}
                      />
                    ))}
                  </div>
                  <div className="member-dots">
                    {data.holdings.slice(0, 5).map((holding) => (
                      <span key={holding.instrument_id} title={holding.name}>
                        {holding.name.slice(0, 1)}
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <Link className="button button-secondary hero-empty-action" to="/holdings">
                  {t('overview.addHolding')}
                  <Plus size={15} />
                </Link>
              )}
            </>
          ) : leadGroup ? (
            <>
              <div className="hero-eyebrow">{t('overview.groups')}</div>
              <h2>{leadGroup.name}</h2>
              <p>{leadGroup.description || `${leadGroup.members.length} ${t('groups.members')}`}</p>
              <div className="hero-value-row">
                <Metric
                  label={t('groups.dayChange')}
                  value={formatPercent(leadGroup.day_change_pct)}
                  tone={changeClass(leadGroup.day_change_pct)}
                  detail={`${t('groups.coverage')} ${Math.round((leadGroup.coverage ?? 0) * 100)}%`}
                />
                <div className="member-dots">
                  {leadGroup.members.slice(0, 5).map((member) => (
                    <span
                      key={member.instrument_id}
                      title={`${member.name} ${Math.round(member.normalized_weight * 100)}%`}
                    >
                      {member.name.slice(0, 1)}
                    </span>
                  ))}
                </div>
              </div>
              <Link className="button button-secondary hero-empty-action" to="/groups">
                {t('overview.openGroups')}
              </Link>
            </>
          ) : (
            <>
              <div className="hero-eyebrow">{t('overview.groups')}</div>
              <h2>{t('overview.noGroups')}</h2>
              <Link className="button button-secondary hero-empty-action" to="/groups">
                {t('overview.createGroup')}
                <Plus size={15} />
              </Link>
            </>
          )}
        </div>
        <div className="hero-chart">
          {heroMode === 'holdings' ? (
            holdingSeries.some((series) => series.points.length > 1) ? (
              <LineChart
                height={260}
                series={holdingSeries.map((series, index, items) => ({
                  id: `holding-series-${series.currency}`,
                  label:
                    items.length > 1
                      ? `${t('overview.holdingCurve')} · ${series.currency}`
                      : t('overview.holdingCurve'),
                  color: ['#8ea7ff', '#81d8e8', '#a78bfa'][index % 3],
                  points: series.points,
                }))}
              />
            ) : (
              <div className="chart-placeholder">
                <Sparkles size={26} />
                <span>{t('common.noData')}</span>
              </div>
            )
          ) : leadGroup && data.groupSeries.length > 1 ? (
            <LineChart
              height={260}
              series={[
                {
                  id: `group-${leadGroup.id}`,
                  label: leadGroup.name,
                  color: '#8ea7ff',
                  points: data.groupSeries,
                },
              ]}
            />
          ) : (
            <div className="chart-placeholder">
              <Sparkles size={26} />
              <span>{t('common.noData')}</span>
            </div>
          )}
        </div>
      </section>

      <div className="overview-grid">
        <GlassPanel className="watch-pulse reveal reveal-delay-1">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('overview.watchlist')}</p>
              <h2>{t('nav.watchlist')}</h2>
            </div>
            <Link to="/watchlist" className="text-link">
              {t('overview.goWatchlist')}
              <ArrowUpRight size={15} />
            </Link>
          </div>
          {data.watchlist.length ? (
            <div className="pulse-list">
              {data.watchlist.slice(0, 6).map((item) => (
                <div className="pulse-row" key={item.id}>
                  <div className="instrument-identity">
                    <span className="market-monogram">{item.market.slice(0, 2)}</span>
                    <span>
                      <strong>{item.name}</strong>
                      <small>
                        {item.symbol} · {t(`asset.${item.asset_type}`)}
                      </small>
                    </span>
                  </div>
                  <div className="quote-value">
                    <strong>{item.quote?.current_price?.toFixed(2) ?? '--'}</strong>
                    <small className={changeClass(item.quote?.change_pct)}>
                      {formatPercent(item.quote?.change_pct)}
                    </small>
                  </div>
                  <DataState
                    quote={item.quote}
                    onClick={() => setDetailItem(item)}
                    ariaLabel={`${t('watchlist.viewDetails')} ${item.name}`}
                  />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title={t('overview.noWatchlist')}
              action={
                <Link className="button button-secondary" to="/watchlist">
                  {t('common.add')}
                </Link>
              }
            />
          )}
        </GlassPanel>

        <GlassPanel className="daily-review-card reveal reveal-delay-2">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('overview.dailyReview')}</p>
              <h2>{data.review?.title || t('overview.dailyReview')}</h2>
            </div>
            <Badge tone={data.review?.status === 'success' ? 'success' : 'neutral'}>
              {data.review?.trade_date || t('common.today')}
            </Badge>
          </div>
          {data.review ? (
            <MarkdownReport
              className="review-excerpt"
              content={data.review.content}
            />
          ) : (
            <div className="review-empty">
              <Sparkles size={24} />
              <p>{t('overview.noReview')}</p>
            </div>
          )}
          <div className="inline-actions">
            {data.review ? (
              <Button variant="ghost" onClick={() => setReviewOpen(true)}>
                {t('overview.viewFull')}
              </Button>
            ) : null}
            <Button variant="secondary" onClick={runReview} disabled={running}>
              {running ? t('common.loading') : t('overview.runReview')}
            </Button>
          </div>
        </GlassPanel>

        <GlassPanel className="recent-alerts reveal reveal-delay-3">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('overview.recentAlerts')}</p>
              <h2>{t('nav.alerts')}</h2>
            </div>
            <BellRing size={18} />
          </div>
          {data.hits.length ? (
            <div className="timeline">
              {data.hits.map((hit) => (
                <div className="timeline-row" key={hit.id}>
                  <span className="timeline-dot" />
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
            <p className="muted-copy">{t('overview.noAlerts')}</p>
          )}
        </GlassPanel>
      </div>
      <Modal
        open={reviewOpen && Boolean(data.review)}
        title={data.review?.title || t('overview.dailyReview')}
        onClose={() => setReviewOpen(false)}
      >
        <MarkdownReport
          className="review-full"
          content={data.review?.content ?? ''}
        />
      </Modal>
      <InstrumentDetailModal item={detailItem} onClose={() => setDetailItem(null)} />
    </>
  )
}

