import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { X } from 'lucide-react'

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
    <header className="page-header reveal">
      <div>
        {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {action ? <div className="page-header-action">{action}</div> : null}
    </header>
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
  return (
    <div className="loading" role="status" aria-label="loading">
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
          <button className="icon-button" onClick={onClose} aria-label="close">
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

