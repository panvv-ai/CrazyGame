import type {
  AIChatSession,
  AIChatSessionDetail,
  AIReportRecord,
  AISseEvent,
  RecognizedInstrument,
} from './types'
import {
  mobileChatStream,
  mobileDeleteReport,
  mobileDeleteSession,
  mobileReport,
  mobileReports,
  mobileReportStream,
  mobileRecognizeImage,
  mobileSession,
  mobileSessions,
} from './mobileApi'
import { isNativeCrazyGame } from './native'

async function jsonRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`/api${path}`, { ...init, headers })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      message = payload.detail ?? message
    } catch {
      // Keep status text.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function parseSseChunks(
  buffer: string,
  chunk: string
): { buffer: string; events: AISseEvent[] } {
  const combined = buffer + chunk
  const blocks = combined.split(/\r?\n\r?\n/)
  const nextBuffer = blocks.pop() ?? ''
  const events: AISseEvent[] = []
  for (const block of blocks) {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n')
    if (!data || data === '[DONE]') continue
    try {
      const parsed = JSON.parse(data)
      if (parsed && typeof parsed === 'object' && typeof parsed.type === 'string') {
        events.push(parsed as AISseEvent)
      }
    } catch {
      // Ignore keep-alives and malformed event fragments.
    }
  }
  return { buffer: nextBuffer, events }
}

export async function consumeSseResponse(
  response: Response,
  onEvent: (event: AISseEvent) => void
): Promise<void> {
  if (!response.body) throw new Error('stream_unavailable')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let accepted = false
  let terminal = false
  let requestId: string | null = null

  const handle = (event: AISseEvent) => {
    if (event.type === 'accepted') {
      if (accepted) throw new Error('stream_duplicate_accepted')
      accepted = true
      if (typeof event.request_id !== 'string' || !event.request_id) {
        throw new Error('stream_protocol_error')
      }
      requestId = event.request_id
      onEvent(event)
      return
    }
    if (!accepted) throw new Error('stream_not_accepted')
    if (terminal) throw new Error('stream_event_after_terminal')
    if (
      requestId &&
      event.request_id !== requestId
    ) {
      throw new Error('stream_request_mismatch')
    }
    if (
      event.type === 'done' ||
      event.type === 'error' ||
      event.type === 'clarification'
    ) {
      terminal = true
    }
    onEvent(event)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const parsed = parseSseChunks(buffer, decoder.decode(value, { stream: true }))
    buffer = parsed.buffer
    parsed.events.forEach(handle)
  }
  buffer += decoder.decode()
  parseSseChunks(buffer, '\n\n').events.forEach(handle)

  if (!accepted) throw new Error('stream_not_accepted')
  if (!terminal) throw new Error('stream_incomplete')
}

async function streamRequest(
  path: string,
  body: Record<string, unknown>,
  onEvent: (event: AISseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  if (isNativeCrazyGame()) {
    if (path === '/ai/chat/stream') {
      return mobileChatStream(
        body as {
          message: string
          session_id?: string
          instrument_id?: number
        },
        onEvent,
        signal
      )
    }
    if (path === '/ai/reports/stream') {
      return mobileReportStream(Number(body.instrument_id), onEvent, signal)
    }
  }
  const response = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      message = payload.detail ?? message
    } catch {
      // Keep status text.
    }
    throw new Error(message)
  }
  await consumeSseResponse(response, onEvent)
}

export const aiApi = {
  chatStream: (
    body: {
      message: string
      session_id?: string
      instrument_id?: number
    },
    onEvent: (event: AISseEvent) => void,
    signal?: AbortSignal
  ) => streamRequest('/ai/chat/stream', body, onEvent, signal),

  reportStream: (
    instrumentId: number,
    onEvent: (event: AISseEvent) => void,
    signal?: AbortSignal
  ) =>
    streamRequest(
      '/ai/reports/stream',
      { instrument_id: instrumentId },
      onEvent,
      signal
    ),

  sessions: () =>
    isNativeCrazyGame()
      ? Promise.resolve(mobileSessions() as { items: AIChatSession[] })
      : jsonRequest<{ items: AIChatSession[] }>('/ai/chat/sessions'),
  session: (id: string) =>
    isNativeCrazyGame()
      ? Promise.resolve(mobileSession(id) as AIChatSessionDetail)
      : jsonRequest<AIChatSessionDetail>(`/ai/chat/sessions/${id}`),
  deleteSession: (id: string) =>
    isNativeCrazyGame()
      ? Promise.resolve(mobileDeleteSession(id))
      : jsonRequest<{ ok: boolean }>(`/ai/chat/sessions/${id}`, { method: 'DELETE' }),

  reports: (instrumentId?: number, limit = 30) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (instrumentId) params.set('instrument_id', String(instrumentId))
    return isNativeCrazyGame()
      ? Promise.resolve(
          mobileReports(instrumentId, limit) as { items: AIReportRecord[] }
        )
      : jsonRequest<{ items: AIReportRecord[] }>(`/ai/reports?${params}`)
  },
  report: (id: number) =>
    isNativeCrazyGame()
      ? Promise.resolve(mobileReport(id))
      : jsonRequest<AIReportRecord>(`/ai/reports/${id}`),
  deleteReport: (id: number) =>
    isNativeCrazyGame()
      ? Promise.resolve(mobileDeleteReport(id))
      : jsonRequest<{ ok: boolean }>(`/ai/reports/${id}`, { method: 'DELETE' }),

  recognizeImage: async (file: File) => {
    if (isNativeCrazyGame()) {
      return mobileRecognizeImage(file)
    }
    const form = new FormData()
    form.append('file', file)
    return jsonRequest<{ items: RecognizedInstrument[] }>(
      '/instruments/recognize-image',
      { method: 'POST', body: form }
    )
  },
}
