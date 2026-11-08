import { useTranslation } from 'react-i18next'
import { freshnessLabelKey, formatDateTime, type Language } from '../lib'
import type { Quote } from '../types'
import { Badge } from './ui'

export function DataState({
  quote,
  onClick,
  ariaLabel,
}: {
  quote: Quote | null | undefined
  onClick?: () => void
  ariaLabel?: string
}) {
  const { t, i18n } = useTranslation()
  if (!quote) return null
  const language = i18n.language as Language
  const tone = quote.freshness === 'stale' ? 'warn' : quote.freshness === 'estimated' ? 'accent' : 'neutral'
  const content = (
    <>
      <Badge tone={tone}>{t(freshnessLabelKey(quote.freshness))}</Badge>
      <span>{formatDateTime(quote.as_of, language)}</span>
    </>
  )
  if (onClick) {
    return (
      <button
        type="button"
        className="data-state data-state-interactive"
        onClick={onClick}
        aria-label={ariaLabel || t('watchlist.viewDetails')}
      >
        {content}
      </button>
    )
  }
  return <span className="data-state">{content}</span>
}

