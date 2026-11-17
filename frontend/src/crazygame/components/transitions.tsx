import {
  AnimatePresence,
  animate,
  m,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from 'motion/react'
import {
  Children,
  type ComponentPropsWithoutRef,
  type ReactNode,
  useEffect,
} from 'react'

import { motionTokens, staggerDelay } from '../motion'

export function PageTransition({
  routeKey,
  direction,
  children,
}: {
  routeKey: string
  direction: number
  children: ReactNode
}) {
  const reduceMotion = useReducedMotion()
  const offset = reduceMotion ? 0 : motionTokens.page.offset

  return (
    <AnimatePresence mode="wait" initial={false} custom={direction}>
      <m.div
        key={routeKey}
        className="page-transition"
        custom={direction}
        variants={{
          enter: (movement: number) => ({
            opacity: 0,
            x: movement * offset,
            transition: {
              duration: motionTokens.page.enterSeconds,
              ease: motionTokens.page.ease,
            },
          }),
          center: {
            opacity: 1,
            x: 0,
            transition: {
              duration: motionTokens.page.enterSeconds,
              ease: motionTokens.page.ease,
            },
          },
          exit: (movement: number) => ({
            opacity: 0,
            x: movement * offset * -0.55,
            transition: {
              duration: motionTokens.page.exitSeconds,
              ease: motionTokens.page.ease,
            },
          }),
        }}
        initial="enter"
        animate="center"
        exit="exit"
      >
        {children}
      </m.div>
    </AnimatePresence>
  )
}

export function StaggerList({
  children,
  className = '',
  ...props
}: ComponentPropsWithoutRef<'div'> & { children: ReactNode }) {
  const reduceMotion = useReducedMotion()
  return (
    <div className={`stagger-list ${className}`.trim()} {...props}>
      {Children.toArray(children).map((child, index) => (
        <m.div
          className="stagger-list-item"
          key={(child as { key?: string }).key ?? index}
          initial={reduceMotion ? false : { opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: motionTokens.quick.duration,
            ease: motionTokens.quick.ease,
            delay: reduceMotion ? 0 : staggerDelay(index),
          }}
        >
          {child}
        </m.div>
      ))}
    </div>
  )
}

export function AnimatedNumber({
  value,
  format,
  className = '',
}: {
  value: number
  format: (value: number) => string
  className?: string
}) {
  const reduceMotion = useReducedMotion()
  const latest = useMotionValue(value)
  const display = useTransform(latest, (current) => format(current))

  useEffect(() => {
    if (reduceMotion) {
      latest.set(value)
      return
    }
    const controls = animate(latest, value, {
      duration: 0.32,
      ease: motionTokens.page.ease,
    })
    return controls.stop
  }, [latest, reduceMotion, value])

  return (
    <m.span
      className={className}
      aria-label={format(value)}
      data-value={String(value)}
    >
      {display}
    </m.span>
  )
}
