import { useTranslation } from 'react-i18next'

import type { AIDecisionReport, AIReportRecord, Quote } from '../types'
import { DataState } from './DataState'
import { MarkdownReport } from './MarkdownReport'
import { Badge, GlassPanel } from './ui'

function isReport(value: AIReportRecord['report']): value is AIDecisionReport {
  return Boolean(value && 'instrument' in value && 'core_conclusion' in value)
}

export function AIReportView({ record }: { record: AIReportRecord }) {
  const { t } = useTranslation()
  if (!isReport(record.report)) {
    return (
      <GlassPanel className="ai-report-panel">
        <p className="form-error">
          {record.status === 'failed' ? t('ai.reportFailed') : t('ai.reportUnavailable')}
        </p>
        <MarkdownReport content={record.content_markdown} />
      </GlassPanel>
    )
  }
  const report = record.report
  const quote = report.quote as Partial<Quote>
  const tone =
    report.verdict === 'bullish'
      ? 'success'
      : report.verdict === 'bearish'
        ? 'warn'
        : 'neutral'

  return (
    <GlassPanel className="ai-report-panel reveal">
      <div className="ai-report-head">
        <div>
          <p className="eyebrow">{t('ai.decisionReport')}</p>
          <h2>{report.instrument.name}</h2>
          <small>
            {report.instrument.symbol} · {t(`market.${report.instrument.market}`)}
          </small>
        </div>
        <div className="ai-report-score">
          <strong>{report.score}</strong>
          <span>/ 100</span>
        </div>
      </div>

      <div className="ai-report-badges">
        <Badge tone={tone}>{t(`ai.verdict.${report.verdict}`)}</Badge>
        <Badge tone={report.confidence === 'high' ? 'success' : 'neutral'}>
          {t(`ai.confidence.${report.confidence}`)}
        </Badge>
        <Badge tone={report.data_quality.level === 'good' ? 'success' : 'warn'}>
          {t(`ai.quality.${report.data_quality.level}`)}
        </Badge>
        {quote.current_price != null && quote.as_of ? (
          <DataState quote={quote as Quote} />
        ) : null}
      </div>

      <p className="ai-core-conclusion">{report.core_conclusion}</p>

      <div className="ai-report-grid">
        <section>
          <h3>{t('ai.trend')}</h3>
          <p>{report.trend || t('common.noData')}</p>
          <div className="ai-price-plan">
            <span>
              {t('ai.support')} <strong>{report.price_plan.support ?? '--'}</strong>
            </span>
            <span>
              {t('ai.resistance')} <strong>{report.price_plan.resistance ?? '--'}</strong>
            </span>
            <span>
              {t('ai.invalidation')}{' '}
              <strong>{report.price_plan.invalidation_reference ?? '--'}</strong>
            </span>
          </div>
        </section>

        <section>
          <h3>{t('ai.hotspots')}</h3>
          {report.hotspots.length ? (
            <div className="ai-hotspot-list">
              {report.hotspots.slice(0, 3).map((item) =>
                item.url ? (
                  <a
                    key={`${item.url}-${item.title}`}
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <strong>{item.title}</strong>
                    <small>
                      {item.source} · {t(`ai.relevance.${item.relevance_kind}`)}
                    </small>
                    {item.summary ? <p>{item.summary}</p> : null}
                  </a>
                ) : (
                  <span className="ai-hotspot-card" key={item.title}>
                    <strong>{item.title}</strong>
                    <small>
                      {item.source} · {t(`ai.relevance.${item.relevance_kind}`)}
                    </small>
                    {item.summary ? <p>{item.summary}</p> : null}
                  </span>
                )
              )}
            </div>
          ) : (
            <p className="muted-copy">{t('ai.noHotspots')}</p>
          )}
        </section>

        <section>
          <h3>{t('ai.risks')}</h3>
          <ul>
            {(report.risks.length ? report.risks : [t('ai.noRisks')]).map(
              (item) => <li key={item}>{item}</li>
            )}
          </ul>
        </section>

        <section>
          <h3>{t('ai.catalysts')}</h3>
          <ul>
            {(report.catalysts.length ? report.catalysts : [t('ai.noCatalysts')]).map(
              (item) => <li key={item}>{item}</li>
            )}
          </ul>
        </section>
      </div>

      <div className="ai-advice-grid">
        <section>
          <h3>{t('ai.emptyPosition')}</h3>
          <p>{report.position_advice.no_position || t('common.noData')}</p>
        </section>
        <section>
          <h3>{t('ai.hasPosition')}</h3>
          <p>{report.position_advice.has_position || t('common.noData')}</p>
        </section>
      </div>

      <section className="ai-checklist">
        <h3>{t('ai.checklist')}</h3>
        <ul>
          {report.action_checklist.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

      {report.data_quality.limitations.length ? (
        <div className="ai-limitations">
          <strong>{t('ai.dataLimitations')}</strong>
          <span>{report.data_quality.limitations.join(' · ')}</span>
        </div>
      ) : null}

      <details className="ai-markdown-details">
        <summary>{t('ai.viewMarkdown')}</summary>
        <MarkdownReport content={record.content_markdown} />
      </details>
      <p className="ai-disclaimer">{report.disclaimer}</p>
    </GlassPanel>
  )
}
