import {
  Bot,
  FileText,
  ImagePlus,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Square,
  Trash2,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { aiApi } from '../ai'
import { api } from '../api'
import { AIReportView } from '../components/AIReportView'
import { MarkdownReport } from '../components/MarkdownReport'
import {
  Badge,
  Button,
  EmptyState,
  GlassPanel,
  Loading,
  PageHeader,
} from '../components/ui'
import type {
  AIChatMessage,
  AIChatSession,
  AIInstrument,
  AIReportRecord,
  AISseEvent,
  RecognizedInstrument,
} from '../types'

type Tab = 'chat' | 'reports'

interface LocalMessage extends AIChatMessage {
  pending?: boolean
}

function candidateInstrument(item: RecognizedInstrument): AIInstrument | null {
  if (!item.instrument) return null
  return {
    symbol: item.instrument.symbol,
    name: item.instrument.name,
    market: item.instrument.market,
    asset_type: item.instrument.asset_type,
    currency: item.instrument.currency,
    quote_mode: item.instrument.quote_mode,
  }
}

export function AIPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const initialTab = params.get('tab') === 'reports' ? 'reports' : 'chat'
  const [tab, setTab] = useState<Tab>(initialTab)
  const [instruments, setInstruments] = useState<AIInstrument[]>([])
  const [activeInstrument, setActiveInstrument] = useState<AIInstrument | null>(null)
  const [sessions, setSessions] = useState<AIChatSession[]>([])
  const [sessionId, setSessionId] = useState('')
  const [messages, setMessages] = useState<LocalMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingPage, setLoadingPage] = useState(true)
  const [progress, setProgress] = useState<string[]>([])
  const [error, setError] = useState('')
  const [reports, setReports] = useState<AIReportRecord[]>([])
  const [selectedReport, setSelectedReport] = useState<AIReportRecord | null>(null)
  const [reportProgress, setReportProgress] = useState<string[]>([])
  const [reportLoading, setReportLoading] = useState(false)
  const [recognized, setRecognized] = useState<RecognizedInstrument[]>([])
  const [chatCandidates, setChatCandidates] = useState<
    NonNullable<AISseEvent['candidates']>
  >([])
  const [recognizing, setRecognizing] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const activeIdRef = useRef<number | undefined>(undefined)
  const imageInputRef = useRef<HTMLInputElement | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  const activeId = activeInstrument?.id
  activeIdRef.current = activeId
  const canReport = Boolean(activeId)
  const savedInstrumentOptions = useMemo(
    () => instruments.map((item) => ({
      id: item.id,
      label: `${item.name} · ${item.symbol}`,
    })),
    [instruments]
  )

  async function loadShell() {
    setLoadingPage(true)
    try {
      const [watchlistPayload, holdingPayload, sessionPayload] = await Promise.all([
        api.watchlistQuotes(),
        api.holdings(),
        aiApi.sessions(),
      ])
      const byIdentity = new Map<string, AIInstrument>()
      for (const item of watchlistPayload.items) {
        byIdentity.set(`${item.market}:${item.symbol}:${item.asset_type}`, {
          id: item.instrument_id,
          symbol: item.symbol,
          name: item.name,
          market: item.market,
          asset_type: item.asset_type,
          currency: item.currency,
          quote_mode: item.quote_mode,
        })
      }
      for (const item of holdingPayload.items) {
        byIdentity.set(`${item.market}:${item.symbol}:${item.asset_type}`, {
          id: item.instrument_id,
          symbol: item.symbol,
          name: item.name,
          market: item.market,
          asset_type: item.asset_type,
          currency: item.currency,
          quote_mode: item.quote_mode,
        })
      }
      const nextInstruments = [...byIdentity.values()].filter(
        (item) => item.asset_type !== 'open_end_fund'
      )
      setInstruments(nextInstruments)
      setSessions(sessionPayload.items)
      const requested = Number(params.get('instrument'))
      if (requested) {
        setActiveInstrument(
          nextInstruments.find((item) => item.id === requested) ?? null
        )
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setLoadingPage(false)
    }
  }

  useEffect(() => {
    void loadShell()
  }, [])

  useEffect(() => {
    if (tab === 'reports') {
      if (activeId) {
        void loadReports()
      } else {
        setReports([])
        setSelectedReport(null)
      }
    }
  }, [tab, activeId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, progress])

  async function loadReports() {
    try {
      const payload = await aiApi.reports(activeId)
      setReports(payload.items)
      setSelectedReport((current) => {
        if (current && payload.items.some((item) => item.id === current.id)) {
          return current
        }
        return payload.items[0] ?? null
      })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    }
  }

  async function selectSession(id: string) {
    try {
      const detail = await aiApi.session(id)
      setSessionId(id)
      setActiveInstrument(detail.active_instrument)
      setMessages(detail.messages)
      setProgress([])
      setError('')
      setChatCandidates([])
      if (tab !== 'chat') changeTab('chat')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    }
  }

  function startNewChat() {
    abortRef.current?.abort()
    setSessionId('')
    setMessages([])
    setProgress([])
    setError('')
    setChatCandidates([])
    setInput('')
    if (tab !== 'chat') changeTab('chat')
  }

  function handleEvent(event: AISseEvent, draftId: string) {
    if (event.type === 'accepted') {
      if (event.session_id) setSessionId(event.session_id)
      if (event.active_instrument) {
        const acceptedInstrument = event.active_instrument
        setActiveInstrument(acceptedInstrument)
        setInstruments((current) => {
          if (
            !acceptedInstrument.id ||
            current.some((item) => item.id === acceptedInstrument.id)
          ) {
            return current
          }
          return [...current, acceptedInstrument]
        })
      }
      setChatCandidates([])
      return
    }
    if (event.type === 'stage' && event.stage) {
      setProgress((current) => [...current, event.stage!])
      return
    }
    if (event.type === 'tool_start') {
      if (event.tool) {
        setProgress((current) => [...current, event.tool!])
      }
      return
    }
    if (event.type === 'delta' && event.content) {
      setMessages((current) =>
        current.map((message) =>
          message.id === draftId
            ? { ...message, content: message.content + event.content }
            : message
        )
      )
      return
    }
    if (event.type === 'clarification') {
      setChatCandidates(event.candidates ?? [])
      const clarification = t('ai.clarifyInstrument')
      setMessages((current) =>
        current.map((message) =>
          message.id === draftId
            ? {
                ...message,
                content: clarification,
                pending: false,
              }
            : message
        )
      )
      setProgress([])
      return
    }
    if (event.type === 'done') {
      setMessages((current) =>
        current.map((message) =>
          message.id === draftId
            ? {
                ...message,
                content: event.content ?? message.content,
                pending: false,
              }
            : message
        )
      )
      setProgress([])
      return
    }
    if (event.type === 'error') {
      const failure =
        event.code === 'ai_not_configured'
          ? t('ai.notConfigured')
          : event.code === 'ai_auth_failed'
            ? t('ai.authFailed')
            : event.code === 'ai_rate_limited'
              ? t('ai.rateLimited')
              : event.code === 'ai_unreachable' || event.code === 'ai_timeout'
                ? t('ai.unreachable')
                : event.code === 'ai_provider_error' ||
                    event.code === 'ai_invalid_response'
                  ? t('ai.configFailed')
                : t('ai.chatFailed')
      setError(failure)
      setMessages((current) =>
        current.map((message) =>
          message.id === draftId
            ? {
                ...message,
                content: failure,
                pending: false,
              }
            : message
        )
      )
    }
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return
    const controller = new AbortController()
    abortRef.current = controller
    const draftId = `draft-${Date.now()}`
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', content: text },
      { id: draftId, role: 'assistant', content: '', pending: true },
    ])
    setInput('')
    setError('')
    setProgress([])
    setLoading(true)
    try {
      await aiApi.chatStream(
        {
          message: text,
          ...(sessionId ? { session_id: sessionId } : {}),
          ...(activeId ? { instrument_id: activeId } : {}),
        },
        (event) => handleEvent(event, draftId),
        controller.signal
      )
      await aiApi.sessions().then((payload) => setSessions(payload.items))
    } catch (reason) {
      if (reason instanceof Error && reason.name === 'AbortError') {
        setMessages((current) =>
          current.map((message) =>
            message.id === draftId
              ? { ...message, content: t('ai.stopped'), pending: false }
              : message
          )
        )
        return
      }
      setError(t('ai.chatFailed'))
      setMessages((current) =>
        current.map((message) =>
          message.id === draftId && message.pending
            ? { ...message, content: t('ai.chatFailed'), pending: false }
            : message
        )
      )
    } finally {
      setLoading(false)
      setProgress([])
      abortRef.current = null
    }
  }

  async function generateReport() {
    if (!activeId || reportLoading) return
    const controller = new AbortController()
    const reportInstrumentId = activeId
    abortRef.current = controller
    setReportLoading(true)
    setReportProgress([])
    setError('')
    try {
      await aiApi.reportStream(
        activeId,
        (event) => {
          if (event.type === 'stage' && event.stage) {
            setReportProgress((current) => [...current, event.stage!])
          }
          if (event.type === 'done' && event.id) {
            aiApi.report(event.id).then((record) => {
              if (activeIdRef.current !== reportInstrumentId) return
              setSelectedReport(record)
              void loadReports()
            }).catch(() => {
              setError(t('ai.reportFailed'))
            })
          }
          if (event.type === 'error') {
            setError(
              event.code === 'ai_not_configured'
                ? t('ai.notConfigured')
                : t('ai.reportFailed')
            )
          }
        },
        controller.signal
      )
    } catch (reason) {
      if (reason instanceof Error && reason.name === 'AbortError') return
      setError(t('ai.reportFailed'))
    } finally {
      setReportLoading(false)
      abortRef.current = null
    }
  }

  async function recognize(file: File) {
    setRecognizing(true)
    setError('')
    try {
      const payload = await aiApi.recognizeImage(file)
      setRecognized(payload.items)
    } catch {
      setError(t('ai.imageFailed'))
    } finally {
      setRecognizing(false)
    }
  }

  function chooseRecognized(item: RecognizedInstrument) {
    const instrument = candidateInstrument(item)
    if (!instrument) {
      setError(t('ai.imageUnresolved'))
      return
    }
    setActiveInstrument(instrument)
    setRecognized([])
    setInput(t('ai.imagePrompt', { name: instrument.name }))
  }

  function chooseChatCandidate(candidate: NonNullable<AISseEvent['candidates']>[number]) {
    const instrument: AIInstrument = {
      symbol: candidate.symbol,
      name: candidate.name,
      market: candidate.market,
      asset_type: candidate.asset_type,
    }
    setActiveInstrument(instrument)
    setChatCandidates([])
    setInput(
      t('ai.imagePrompt', {
        name: `${instrument.name} ${instrument.symbol}`,
      })
    )
  }

  async function deleteSession(id: string) {
    if (!window.confirm(t('ai.deleteSessionConfirm'))) return
    await aiApi.deleteSession(id)
    if (id === sessionId) startNewChat()
    await aiApi.sessions().then((payload) => setSessions(payload.items))
  }

  function changeTab(next: Tab) {
    setTab(next)
    setError('')
    const nextParams = new URLSearchParams(params)
    nextParams.set('tab', next)
    setParams(nextParams, { replace: true })
  }

  function chooseInstrument(value: string) {
    const id = Number(value)
    setActiveInstrument(instruments.find((item) => item.id === id) ?? null)
  }

  if (loadingPage) return <Loading />

  return (
    <>
      <PageHeader
        eyebrow={t('ai.eyebrow')}
        title={t('ai.title')}
        subtitle={t('ai.subtitle')}
        action={
          <Button variant="secondary" onClick={startNewChat}>
            <Plus size={16} />
            {t('ai.newChat')}
          </Button>
        }
      />

      <div className="ai-toolbar">
        <div className="segmented-control ai-tabs">
          <button
            className={tab === 'chat' ? 'active' : ''}
            onClick={() => changeTab('chat')}
            disabled={loading || reportLoading}
          >
            <MessageSquare size={14} /> {t('ai.chatTab')}
          </button>
          <button
            className={tab === 'reports' ? 'active' : ''}
            onClick={() => changeTab('reports')}
            disabled={loading || reportLoading}
          >
            <FileText size={14} /> {t('ai.reportsTab')}
          </button>
        </div>
        <select
          className="input ai-instrument-select"
          value={activeId ?? ''}
          disabled={loading || reportLoading}
          onChange={(event) => chooseInstrument(event.target.value)}
        >
          <option value="">{t('ai.chooseInstrument')}</option>
          {savedInstrumentOptions.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
        {activeInstrument ? (
          <Badge tone="accent">
            {activeInstrument.name} · {activeInstrument.symbol}
          </Badge>
        ) : null}
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      {tab === 'chat' ? (
        <div className="ai-chat-layout">
          <GlassPanel className="ai-session-panel">
            <div className="section-head">
              <div>
                <p className="eyebrow">{t('ai.sessions')}</p>
                <h2>{sessions.length}</h2>
              </div>
              <Button variant="ghost" onClick={startNewChat}>
                <Plus size={15} />
              </Button>
            </div>
            <div className="ai-session-list">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className={`ai-session-row ${session.id === sessionId ? 'active' : ''}`}
                >
                  <button
                    onClick={() => void selectSession(session.id)}
                    disabled={loading || reportLoading}
                  >
                    <strong>{session.title || t('ai.untitled')}</strong>
                    <small>
                      {session.active_instrument?.name || '--'} · {session.message_count}
                    </small>
                  </button>
                  <button
                    className="icon-button danger"
                    onClick={() => void deleteSession(session.id)}
                    aria-label={t('common.delete')}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              {!sessions.length ? (
                <p className="muted-copy">{t('ai.noSessions')}</p>
              ) : null}
            </div>
          </GlassPanel>

          <GlassPanel className="ai-chat-panel">
            <div className="ai-message-list">
              {!messages.length ? (
                <EmptyState
                  title={t('ai.emptyChat')}
                  action={
                    <Button variant="secondary" onClick={() => imageInputRef.current?.click()}>
                      <ImagePlus size={15} />
                      {t('ai.uploadImage')}
                    </Button>
                  }
                />
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`ai-message ${message.role}${message.pending ? ' pending' : ''}`}
                  >
                    <span className="ai-message-role">
                      {message.role === 'assistant' ? <Bot size={15} /> : t('ai.you')}
                    </span>
                    {message.role === 'assistant' ? (
                      !message.pending && message.content ? (
                        <MarkdownReport content={message.content} />
                      ) : (
                        <div className="ai-thinking">
                          <RefreshCw size={14} />
                          {progress.length
                            ? progress.map((stage) => t(`ai.stages.${stage}`, { defaultValue: stage })).join(' · ')
                            : t('ai.thinking')}
                        </div>
                      )
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {recognized.length ? (
              <div className="ai-recognized-list">
                <p>{t('ai.imageChoose')}</p>
                {recognized.map((item) => (
                  <button
                    key={item.code}
                    onClick={() => chooseRecognized(item)}
                    disabled={!item.instrument}
                  >
                    <strong>{item.name || item.code}</strong>
                    <small>
                      {item.code} · {t(`ai.imageConfidence.${item.confidence}`)}
                    </small>
                  </button>
                ))}
              </div>
            ) : null}

            {chatCandidates.length ? (
              <div className="ai-recognized-list">
                <p>{t('ai.candidateChoose')}</p>
                {chatCandidates.map((candidate) => (
                  <button
                    key={`${candidate.market}:${candidate.symbol}:${candidate.asset_type}`}
                    onClick={() => chooseChatCandidate(candidate)}
                  >
                    <strong>{candidate.name}</strong>
                    <small>
                      {candidate.symbol} · {t(`asset.${candidate.asset_type}`)}
                    </small>
                  </button>
                ))}
              </div>
            ) : null}

            <div className="ai-composer">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={t('ai.placeholder')}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    void sendMessage()
                  }
                }}
              />
              <div className="ai-composer-actions">
                <Button
                  variant="ghost"
                  disabled={recognizing || loading}
                  onClick={() => imageInputRef.current?.click()}
                >
                  <ImagePlus size={16} />
                  {recognizing ? t('common.loading') : t('ai.uploadImage')}
                </Button>
                <input
                  ref={imageInputRef}
                  hidden
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,.gif"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (file) void recognize(file)
                    event.target.value = ''
                  }}
                />
                {loading ? (
                  <Button variant="danger" onClick={() => abortRef.current?.abort()}>
                    <Square size={14} /> {t('ai.stop')}
                  </Button>
                ) : (
                  <Button onClick={() => void sendMessage()} disabled={!input.trim()}>
                    <Send size={15} /> {t('ai.send')}
                  </Button>
                )}
              </div>
            </div>
          </GlassPanel>
        </div>
      ) : (
        <div className="ai-report-layout">
          <GlassPanel className="ai-report-history">
            <div className="section-head">
              <div>
                <p className="eyebrow">{t('ai.reportHistory')}</p>
                <h2>{reports.length}</h2>
              </div>
              <Button onClick={() => void generateReport()} disabled={!canReport || reportLoading}>
                <RefreshCw size={15} />
                {reportLoading ? t('ai.generating') : t('ai.generate')}
              </Button>
            </div>
            {reportProgress.length ? (
              <p className="muted-copy">
                {reportProgress.map((stage) => t(`ai.stages.${stage}`, { defaultValue: stage })).join(' · ')}
              </p>
            ) : null}
            <div className="ai-report-list">
              {reports.map((record) => (
                <button
                  key={record.id}
                  className={selectedReport?.id === record.id ? 'active' : ''}
                  onClick={() => setSelectedReport(record)}
                  disabled={reportLoading}
                >
                  <strong>{record.title}</strong>
                  <small>
                    {new Date(record.created_at).toLocaleString()} · {record.score}/100
                  </small>
                </button>
              ))}
              {!reports.length ? (
                <p className="muted-copy">
                  {canReport ? t('ai.noReports') : t('ai.selectForReport')}
                </p>
              ) : null}
            </div>
          </GlassPanel>
          {selectedReport ? (
            <AIReportView record={selectedReport} />
          ) : (
            <GlassPanel className="ai-report-empty">
              <EmptyState title={t('ai.noReportSelected')} />
            </GlassPanel>
          )}
        </div>
      )}
    </>
  )
}
