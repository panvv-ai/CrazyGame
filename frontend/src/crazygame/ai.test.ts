import { describe, expect, it } from 'vitest'

import { consumeSseResponse, parseSseChunks } from './ai'

describe('parseSseChunks', () => {
  it('keeps incomplete events buffered across stream chunks', () => {
    const first = parseSseChunks(
      '',
      'data: {"type":"accepted","session_id":"s1"}\n\ndata: {"type":"delta",'
    )
    const second = parseSseChunks(
      first.buffer,
      '"content":"趋势"}\n\ndata: {"type":"done","content":"趋势"}\n\n'
    )

    expect(first.events).toEqual([
      { type: 'accepted', session_id: 's1' },
    ])
    expect(second.events).toEqual([
      { type: 'delta', content: '趋势' },
      { type: 'done', content: '趋势' },
    ])
    expect(second.buffer).toBe('')
  })

  it('ignores malformed and empty SSE lines', () => {
    const result = parseSseChunks(
      '',
      ': keep-alive\n\ndata: not-json\n\ndata: {"type":"done"}\n\n'
    )

    expect(result.events).toEqual([{ type: 'done' }])
  })

  it('rejects a stream that ends before a terminal event', async () => {
    const response = new Response(
      'data: {"type":"accepted","request_id":"r1","session_id":"s1"}\n\n' +
        'data: {"type":"delta","request_id":"r1","content":"部分"}\n\n'
    )

    await expect(consumeSseResponse(response, () => undefined)).rejects.toThrow(
      'stream_incomplete'
    )
  })

  it('rejects events before acceptance and mismatched request ids', async () => {
    const early = new Response(
      'data: {"type":"delta","request_id":"r1","content":"部分"}\n\n'
    )
    const mismatch = new Response(
      'data: {"type":"accepted","request_id":"r1","session_id":"s1"}\n\n' +
        'data: {"type":"done","request_id":"r2","content":"完成"}\n\n'
    )

    await expect(consumeSseResponse(early, () => undefined)).rejects.toThrow(
      'stream_not_accepted'
    )
    await expect(consumeSseResponse(mismatch, () => undefined)).rejects.toThrow(
      'stream_request_mismatch'
    )
  })

  it('accepts one owned terminal event', async () => {
    const events: string[] = []
    const response = new Response(
      'data: {"type":"accepted","request_id":"r1","session_id":"s1"}\n\n' +
        'data: {"type":"delta","request_id":"r1","content":"完成"}\n\n' +
        'data: {"type":"done","request_id":"r1","content":"完成"}\n\n'
    )

    await consumeSseResponse(response, (event) => {
      events.push(event.type)
    })

    expect(events).toEqual(['accepted', 'delta', 'done'])
  })

  it('treats clarification as a terminal result', async () => {
    const response = new Response(
      'data: {"type":"accepted","request_id":"r1","session_id":"s1"}\n\n' +
        'data: {"type":"clarification","request_id":"r1","message":"choose"}\n\n'
    )

    await expect(
      consumeSseResponse(response, () => undefined)
    ).resolves.toBeUndefined()
  })
})
