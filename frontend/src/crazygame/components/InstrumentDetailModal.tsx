import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageSquare, RefreshCw, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { changeClass, formatPercent, seriesViewState } from '../lib'
import type { Quote } from '../types'
import { DataState } from './DataState'
import { LineChart } from './LineChart'
import { Button, EmptyState, Loading, Metric, Modal } from './ui'

export interface DetailInstrument {
  instrument_id: number
  name: string
  symbol: string
  quote?: Quote | null
}

export function InstrumentDetailModal({
  item,
  onClose,
}: {
  item: DetailInstrument | null
  onClose: () => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [points, setPoints] = useState<Array<{ date: string; value: number }>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const instrumentId = item?.instrument_id

  useEffect(() => {
    if (!instrumentId) return
    let active = true
    setLoading(true)
    setError('')
    setPoints([])
    api
      .instrumentSeries(instrumentId, 365)
      .then((payload) => {
        if (active) setPoints(payload.points)
      })
      .catch((reason) => {
        if (active) {
          setError(
            reason instanceof Error ? reason.message : t('common.unknownError')
          )
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [instrumentId, reloadKey])

  const state = seriesViewState(points, loading, error)

  return (
    <Modal
      open={Boolean(item)}
      title={item ? `${item.name} · ${item.symbol}` : ''}
      onClose={onClose}
    >
      {item ? (
        <>
          <div className="instrument-detail-meta">
            <Metric
              label={t('common.price')}
              value={item.quote?.current_price?.toFixed(2) ?? '--'}
              tone={changeClass(item.quote?.change_pct)}
            />
            <span className={changeClass(item.quote?.change_pct)}>
              {formatPercent(item.quote?.change_pct)}
            </span>
            <DataState quote={item.quote} />
          </div>
          <div className="ai-detail-actions">
            <Button
              variant="secondary"
              onClick={() => navigate(`/ai?instrument=${item.instrument_id}&tab=reports`)}
            >
              <Sparkles size={15} />
              {t('ai.diagnose')}
            </Button>
            <Button
              variant="ghost"
              onClick={() => navigate(`/ai?instrument=${item.instrument_id}&tab=chat`)}
            >
              <MessageSquare size={15} />
              {t('ai.continueChat')}
            </Button>
          </div>
          {state === 'ready' ? (
            <LineChart
              height={320}
              series={[
                {
                  id: `instrument-${item.instrument_id}`,
                  label: item.name,
                  color: '#8ea7ff',
                  points,
                },
              ]}
            />
          ) : state === 'loading' ? (
            <div className="detail-state">
              <Loading />
            </div>
          ) : (
            <EmptyState
              title={
                state === 'error'
                  ? `${t('watchlist.detailUnavailable')}：${error}`
                  : t('common.noData')
              }
              action={
                <Button
                  variant="secondary"
                  onClick={() => setReloadKey((value) => value + 1)}
                >
                  <RefreshCw size={15} />
                  {t('common.retry')}
                </Button>
              }
            />
          )}
        </>
      ) : null}
    </Modal>
  )
}
