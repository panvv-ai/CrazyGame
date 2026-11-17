import { describe, expect, it } from 'vitest'

import { motionTokens, staggerDelay } from './motion'

describe('motion tokens', () => {
  it('keeps page transitions short and restrained', () => {
    expect(motionTokens.page.seconds).toBeGreaterThanOrEqual(0.22)
    expect(motionTokens.page.seconds).toBeLessThanOrEqual(0.28)
    expect(
      motionTokens.page.enterSeconds + motionTokens.page.exitSeconds
    ).toBeCloseTo(motionTokens.page.seconds)
    expect(motionTokens.page.offset).toBeLessThanOrEqual(8)
    expect(motionTokens.press.scale).toBeCloseTo(0.98)
  })

  it('caps list stagger feedback to the first visible items', () => {
    expect(staggerDelay(0)).toBe(0)
    expect(staggerDelay(3)).toBe(0.09)
    expect(staggerDelay(8)).toBe(0.12)
    expect(staggerDelay(20)).toBe(0.12)
  })
})
