import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowUpRight, BellRing, Plus, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { DataState } from '../components/DataState'
import { LineChart } from '../components/LineChart'
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
  type Language,
} from '../lib'
import type { AlertHit, AssetGroup, DailyReview, GroupPoint, WatchlistItem } from '../types'

interface OverviewData {
  watchlist: WatchlistItem[]
  groups: AssetGroup[]
  hits: AlertHit[]
  review: DailyReview | null
  groupSeries: GroupPoint[]
}

export function OverviewPage() {
  const { t, i18n } = useTranslation()
  const language = i18n.language as Language
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)

  async function load() {
    try {
      setError('')
      const [watchlist, groupPayload, hits, reviews] = await Promise.all([
        api.watchlistQuotes(),
        api.groups(),
        api.alertHits(),
        api.dailyReviews(),
      ])
      const groups = await Promise.all(
        groupPayload.items.map((group) => api.groupSummary(group.id))
      ).then((items) => items.filter((group) => group.scope !== 'mixed'))
      const groupSeries = groups[0]
        ? (await api.groupSeries(groups[0].id, 365)).points
        : []
      setData({
        watchlist: watchlist.items,
        groups,
        hits: hits.items.slice(0, 4),
        review: reviews.items[0] ?? null,
        groupSeries,
      })
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

      {leadGroup ? (
        <section className="overview-hero reveal">
          <div className="hero-copy">
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
          </div>
          <div className="hero-chart">
            {data.groupSeries.length > 1 ? (
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
      ) : (
        <GlassPanel className="reveal">
          <EmptyState
            title={t('overview.noGroups')}
            action={
              <Link className="button button-secondary" to="/groups">
                {t('overview.createGroup')}
                <Plus size={15} />
              </Link>
            }
          />
        </GlassPanel>
      )}

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
                  <DataState quote={item.quote} />
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
            <div className="review-excerpt">
              {data.review.content
                .replace(/[#*_>`-]/g, '')
                .split('\n')
                .filter(Boolean)
                .slice(0, 6)
                .map((line, index) => (
                  <p key={`${line}-${index}`}>{line}</p>
                ))}
            </div>
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
        <article className="review-full">{data.review?.content}</article>
      </Modal>
    </>
  )
}

