import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { MarkdownReport } from './MarkdownReport'

describe('MarkdownReport', () => {
  it('renders headings, emphasis, lists, and GFM tables', () => {
    const html = renderToStaticMarkup(
      createElement(MarkdownReport, {
        content: [
          '# 持仓健康',
          '',
          '- **组合稳定**',
          '- 继续观察',
          '',
          '| 状态 | 建议 |',
          '| --- | --- |',
          '| 稳定 | 持有 |',
        ].join('\n'),
      })
    )

    expect(html).toContain('<h1>持仓健康</h1>')
    expect(html).toContain('<strong>组合稳定</strong>')
    expect(html).toContain('<ul>')
    expect(html).toContain('<table>')
  })

  it('keeps raw HTML inert', () => {
    const html = renderToStaticMarkup(
      createElement(MarkdownReport, {
        content: '<script>alert("x")</script>',
      })
    )

    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })
})
