export interface NativeHttpResult {
  status: number
  body: string
}

export interface NativeAiEvent {
  type: 'delta' | 'done' | 'error'
  content?: string
  code?: string
}

export interface CrazyGameNativeBridge {
  readState(): string
  writeState(value: string): boolean
  request(
    id: string,
    method: string,
    url: string,
    headersJson: string,
    body: string
  ): void
  cancelRequest(id: string): void
  streamAi(
    id: string,
    messagesJson: string,
    vision: boolean,
    configJson: string
  ): void
  notify(title: string, body: string): void
  sendNotification(channelJson: string, title: string, body: string): string
  requestNotificationPermission(): void
  scheduleAlerts(enabled: boolean, intervalMinutes: number): void
  exportState(value: string, password: string): string
  importState(value: string, password: string): string
}

declare global {
  interface Window {
    CrazyGameNative?: CrazyGameNativeBridge
    __crazygameNativeResolve?: (
      id: string,
      resultJson: string
    ) => void
    __crazygameNativeAiEvent?: (id: string, eventJson: string) => void
  }
}

interface PendingRequest {
  resolve: (value: NativeHttpResult) => void
  reject: (reason: Error) => void
}

const pending = new Map<string, PendingRequest>()
const pendingAi = new Map<
  string,
  {
    onEvent: (event: NativeAiEvent) => void
    reject: (reason: Error) => void
  }
>()

export function nativeBridge() {
  return window.CrazyGameNative
}

export function isNativeCrazyGame() {
  return Boolean(nativeBridge())
}

if (typeof window !== 'undefined') {
  window.__crazygameNativeResolve = (id, resultJson) => {
    const request = pending.get(id)
    if (!request) return
    pending.delete(id)
    try {
      const parsed = JSON.parse(resultJson) as {
        status?: number
        body?: string
        error?: string
      }
      if (parsed.error) request.reject(new Error(parsed.error))
      else
        request.resolve({
          status: Number(parsed.status) || 0,
          body: typeof parsed.body === 'string' ? parsed.body : '',
        })
    } catch (error) {
      request.reject(error instanceof Error ? error : new Error('native_response_invalid'))
    }
  }

  window.__crazygameNativeAiEvent = (id, eventJson) => {
    const request = pendingAi.get(id)
    if (!request) return
    try {
      const event = JSON.parse(eventJson) as NativeAiEvent
      request.onEvent(event)
      if (event.type === 'done' || event.type === 'error') pendingAi.delete(id)
    } catch {
      pendingAi.delete(id)
      request.reject(new Error('native_ai_event_invalid'))
    }
  }
}

export function nativeHttpRequest(
  method: string,
  url: string,
  headers: Record<string, string> = {},
  body = ''
): Promise<NativeHttpResult> {
  const bridge = nativeBridge()
  if (!bridge) return Promise.reject(new Error('native_bridge_unavailable'))
  const id = `http-${Date.now()}-${Math.random().toString(36).slice(2)}`
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    try {
      bridge.request(id, method, url, JSON.stringify(headers), body)
    } catch (error) {
      pending.delete(id)
      reject(error instanceof Error ? error : new Error('native_request_failed'))
    }
  })
}

export function cancelNativeRequest(id: string) {
  nativeBridge()?.cancelRequest(id)
  pending.delete(id)
  pendingAi.delete(id)
}

export function nativeAiStream(
  messages: Array<Record<string, unknown>>,
  onEvent: (event: NativeAiEvent) => void,
  signal?: AbortSignal,
  config?: object,
  vision = false
): Promise<void> {
  const bridge = nativeBridge()
  if (!bridge) return Promise.reject(new Error('native_bridge_unavailable'))
  const id = `ai-${Date.now()}-${Math.random().toString(36).slice(2)}`
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      resolve()
    }
    const fail = (error: Error) => {
      if (settled) return
      settled = true
      pendingAi.delete(id)
      reject(error)
    }
    pendingAi.set(id, {
      onEvent: (event) => {
        onEvent(event)
        if (event.type === 'done') finish()
        if (event.type === 'error') fail(new Error(event.code || 'ai_stream_failed'))
      },
      reject: fail,
    })
    signal?.addEventListener(
      'abort',
      () => {
        bridge.cancelRequest(id)
        const error = new Error('aborted')
        error.name = 'AbortError'
        fail(error)
      },
      { once: true }
    )
    bridge.streamAi(
      id,
      JSON.stringify(messages),
      vision,
      JSON.stringify(config ?? {})
    )
  })
}
