import { useTranslation } from 'react-i18next'
import { freshnessLabelKey, formatDateTime, type Language } from '../lib'
import type { Quote } from '../types'
import { Badge } from './ui'

export function DataState({ quote }: { quote: Quote | null | undefined }) {
  const { t, i18n } = useTranslation()
  if (!quote) return null
  const language = i18n.language as Language
  const tone = quote.freshness === 'stale' ? 'warn' : quote.freshness === 'estimated' ? 'accent' : 'neutral'
  return (
    <span className="data-state">
      <Badge tone={tone}>{t(freshnessLabelKey(quote.freshness))}</Badge>
      <span>{formatDateTime(quote.as_of, language)}</span>
    </span>
  )
}

