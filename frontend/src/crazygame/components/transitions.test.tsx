import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AnimatedNumber, PageTransition, StaggerList } from './transitions'

describe('transition primitives', () => {
  it('swaps a route after its exit transition', async () => {
    const { rerender } = render(
      <PageTransition routeKey="/overview" direction={1}>
        <p>Overview content</p>
      </PageTransition>
    )

    rerender(
      <PageTransition routeKey="/watchlist" direction={1}>
        <p>Watchlist content</p>
      </PageTransition>
    )

    await waitFor(() => {
      expect(screen.getByText('Watchlist content')).toBeInTheDocument()
    })
    expect(screen.queryByText('Overview content')).not.toBeInTheDocument()
  })

  it('renders list children as a stable semantic group', () => {
    render(
      <StaggerList aria-label="Recent alerts">
        <article>First alert</article>
        <article>Second alert</article>
      </StaggerList>
    )

    expect(screen.getByLabelText('Recent alerts').children).toHaveLength(2)
  })

  it('keeps the final numeric value available while values animate', () => {
    render(<AnimatedNumber value={12.5} format={(value) => `${value.toFixed(1)}%`} />)

    expect(screen.getByLabelText('12.5%')).toHaveAttribute('data-value', '12.5')
  })
})
