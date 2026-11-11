import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function Button({
  variant = 'primary',
  className = '',
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
}) {
  return (
    <button className={`button button-${variant} ${className}`} {...props}>
      {children}
    </button>
  )
}

export function GlassPanel({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <section className={`glass-panel ${className}`}>{children}</section>
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="eyebrow">{children}</div>
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  action,
}: {
  eyebrow?: string
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <header className="route-rail reveal">
      <div className="route-copy">
        {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {action ? <div className="route-actions">{action}</div> : null}
    </header>
  )
}

export function InstrumentMark({
  name,
  symbol,
  market,
}: {
  name?: string
  symbol?: string
  market?: string
}) {
  const label = symbol && /^[A-Za-z]/.test(symbol)
    ? symbol.slice(0, 2).toUpperCase()
    : name?.slice(0, 1) || market?.slice(0, 2) || '--'
  return <span className="instrument-mark">{label}</span>
}

export function Sparkline({
  values,
  tone,
}: {
  values: number[]
  tone?: 'up' | 'down'
}) {
  if (values.length < 2) {
    return <span className="sparkline sparkline-empty" aria-hidden="true" />
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const spread = max - min || 1
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100
      const y = 32 - ((value - min) / spread) * 28
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
  return (
    <svg
      className={`sparkline ${tone === 'down' ? 'spark-down' : ''}`}
      viewBox="0 0 100 36"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline points={points} />
    </svg>
  )
}

export function ProgressBar({
  value,
  tone = 'default',
}: {
  value: number
  tone?: 'default' | 'muted'
}) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <span className={`rule-progress ${tone === 'muted' ? 'is-muted' : ''}`} aria-hidden="true">
      <i style={{ width: `${clamped}%` }} />
    </span>
  )
}

export function AllocationRing({
  segments,
}: {
  segments: Array<{ value: number; color: string }>
}) {
  let cursor = 0
  const stops = segments.map((segment) => {
    const start = cursor
    cursor += Math.max(0, segment.value)
    return `${segment.color} ${start}% ${cursor}%`
  })
  return (
    <div
      className="allocation-ring"
      style={{
        background: `radial-gradient(circle, var(--color-paper-raised) 0 52%, transparent 53%), conic-gradient(${stops.join(', ')})`,
      }}
      aria-hidden="true"
    >
      <span />
    </div>
  )
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string
  children: ReactNode
  hint?: string
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className="input select" {...props} />
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'accent' | 'warn' | 'success'
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function EmptyState({
  title,
  action,
}: {
  title: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-orbit" aria-hidden="true">
        <span />
        <span />
      </div>
      <p>{title}</p>
      {action}
    </div>
  )
}

export function Loading() {
  const { t } = useTranslation()
  return (
    <div className="loading" role="status" aria-label={t('common.loading')}>
      <span />
      <span />
      <span />
    </div>
  )
}

export function Modal({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
}) {
  const { t } = useTranslation()
  if (!open) return null
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="modal glass-panel"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label={t('common.close')}>
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Metric({
  label,
  value,
  detail,
  tone = '',
}: {
  label: string
  value: ReactNode
  detail?: ReactNode
  tone?: string
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  )
}

