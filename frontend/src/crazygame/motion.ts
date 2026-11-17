export const motionTokens = {
  quick: {
    duration: 0.16,
    ease: [0.16, 1, 0.3, 1] as const,
  },
  page: {
    seconds: 0.24,
    enterSeconds: 0.16,
    exitSeconds: 0.08,
    offset: 6,
    ease: [0.22, 1, 0.36, 1] as const,
  },
  press: {
    scale: 0.98,
    spring: {
      type: 'spring' as const,
      stiffness: 520,
      damping: 36,
      mass: 0.7,
    },
  },
  sheet: {
    spring: {
      type: 'spring' as const,
      stiffness: 360,
      damping: 38,
      mass: 0.9,
    },
  },
  stagger: {
    step: 0.03,
    max: 0.12,
  },
}

export function staggerDelay(index: number) {
  return Math.min(Math.max(0, index) * motionTokens.stagger.step, motionTokens.stagger.max)
}
