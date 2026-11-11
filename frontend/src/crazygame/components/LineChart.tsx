import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  AreaSeries,
  ColorType,
  LineSeries,
  createChart,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts'

export interface ChartSeries {
  id: string
  label: string
  color: string
  points: Array<{ date: string; value: number }>
}

export function LineChart({
  series,
  height = 260,
}: {
  series: ChartSeries[]
  height?: number
}) {
  const { t } = useTranslation()
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!hostRef.current || series.length === 0) return
    const chart = createChart(hostRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'rgba(226,232,255,.46)',
        fontFamily: '"Manrope Variable", "PingFang SC", sans-serif',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,.035)' },
        horzLines: { color: 'rgba(255,255,255,.035)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,.06)',
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: false,
        rightOffset: 2,
      },
      crosshair: {
        vertLine: { color: 'rgba(255,255,255,.18)' },
        horzLine: { color: 'rgba(255,255,255,.18)' },
      },
      handleScale: { axisPressedMouseMove: false },
    })
    const created: ISeriesApi<'Area' | 'Line'>[] = []
    series.forEach((item, index) => {
      const formatted = item.points.map((point) => ({
        time: (Date.parse(`${point.date}T00:00:00Z`) / 1000) as UTCTimestamp,
        value: point.value,
      }))
      if (series.length === 1) {
        const area = chart.addSeries(AreaSeries, {
          lineColor: item.color,
          lineWidth: 2,
          topColor: `${item.color}52`,
          bottomColor: `${item.color}00`,
          priceLineVisible: false,
          lastValueVisible: true,
        })
        area.setData(formatted)
        created.push(area)
      } else {
        const line = chart.addSeries(LineSeries, {
          color: item.color,
          lineWidth: 2,
          priceLineVisible: index === 0,
          lastValueVisible: index === 0,
          title: item.label,
        })
        line.setData(formatted)
        created.push(line)
      }
    })
    chart.timeScale().fitContent()
    const observer = new ResizeObserver(() => {
      if (hostRef.current) chart.applyOptions({ width: hostRef.current.clientWidth })
    })
    observer.observe(hostRef.current)
    return () => {
      observer.disconnect()
      created.splice(0)
      chart.remove()
    }
  }, [series, height])

  return <div className="line-chart" ref={hostRef} aria-label={t('common.chart')} />
}

