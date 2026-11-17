import { m, useReducedMotion, type HTMLMotionProps } from 'motion/react'
import {
  type Ref,
  forwardRef,
} from 'react'
import { useTranslation } from 'react-i18next'

import { motionTokens } from '../motion'

type HapticKind = 'selection' | 'success' | 'warning'

export interface PressableProps extends HTMLMotionProps<'button'> {
  haptic?: HapticKind
}

export const Pressable = forwardRef(function Pressable(
  { haptic, onClick, type = 'button', ...props }: PressableProps,
  ref: Ref<HTMLButtonElement>
) {
  const reduceMotion = useReducedMotion()
  return (
    <m.button
      ref={ref}
      type={type}
      whileTap={reduceMotion ? undefined : { scale: motionTokens.press.scale }}
      transition={motionTokens.press.spring}
      onClick={(event) => {
        if (haptic) {
          window.dispatchEvent(
            new CustomEvent('crazygame:haptic', { detail: { kind: haptic } })
          )
        }
        onClick?.(event)
      }}
      {...props}
    />
  )
})

export function Skeleton({
  lines = 1,
  className = '',
}: {
  lines?: number
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <div
      className={`skeleton ${className}`}
      role="status"
      aria-label={t('common.loading')}
      aria-busy="true"
    >
      {Array.from({ length: Math.max(1, lines) }, (_, index) => (
        <span
          className="skeleton-line"
          key={index}
          style={{ width: `${index === lines - 1 && lines > 1 ? 68 : 100}%` }}
        />
      ))}
    </div>
  )
}

export const SkeletonCard = ({ className = '' }: { className?: string }) => (
  <div className={`skeleton-card ${className}`} aria-hidden="true">
    <span className="skeleton-orb" />
    <div>
      <Skeleton lines={2} />
    </div>
  </div>
)
