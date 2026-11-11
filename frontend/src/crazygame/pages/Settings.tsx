import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, FlaskConical, Plus, ShieldAlert, Sparkles, Trash2 } from 'lucide-react'

import { api } from '../api'
import {
  Badge,
  Button,
  Field,
  GlassPanel,
  Input,
  Loading,
  PageHeader,
  Select,
} from '../components/ui'
import { changeLanguage } from '../i18n'
import type { Language } from '../lib'
import type { AppSettings, NotifyChannel } from '../types'

const emptySettings: AppSettings = {
  language: 'zh-CN',
  ai: { base_url: '', api_key: '', model: '', vision_model: '' },
  news: { enabled: true, provider: 'eastmoney', api_key: '' },
  daily_review_channel_ids: [],
  daily_review_enabled: true,
}

export function SettingsPage() {
  const { t, i18n } = useTranslation()
  const [settings, setSettings] = useState<AppSettings>(emptySettings)
  const [channels, setChannels] = useState<NotifyChannel[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [channelType, setChannelType] = useState<'feishu' | 'aliyun_sms'>('feishu')
  const [channelName, setChannelName] = useState('')
  const [channelConfig, setChannelConfig] = useState<Record<string, string>>({})
  const [channelSaving, setChannelSaving] = useState(false)
  const [testingDraftChannel, setTestingDraftChannel] = useState(false)
  const [testingChannelId, setTestingChannelId] = useState<number | null>(null)
  const [capabilities, setCapabilities] = useState<{
    json: boolean
    tools: boolean
    stream: boolean
    vision: boolean
    ok: boolean
  } | null>(null)
  const [testingCapabilities, setTestingCapabilities] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [settingsPayload, channelPayload] = await Promise.all([
        api.settings(),
        api.channels(),
      ])
      setSettings(settingsPayload)
      setChannels(channelPayload.items)
      if (settingsPayload.language !== i18n.language) {
        await changeLanguage(settingsPayload.language)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function selectLanguage(language: Language) {
    await changeLanguage(language)
    setSettings((current) => ({ ...current, language }))
  }

  async function saveSettings() {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = await api.updateSettings(settings)
      setSettings(saved)
      setMessage(t('settings.saved'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setSaving(false)
    }
  }

  function setConfigField(key: string, value: string) {
    setChannelConfig((current) => ({ ...current, [key]: value }))
  }

  function hasRequiredChannelConfig() {
    if (channelType === 'feishu') {
      return Boolean(channelConfig.webhook_url?.trim())
    }
    return Boolean(
      channelConfig.access_key_id?.trim() &&
      channelConfig.access_key_secret?.trim() &&
      channelConfig.sign_name?.trim() &&
      channelConfig.template_code_zh?.trim() &&
      channelConfig.phone_numbers?.trim()
    )
  }

  async function addChannel() {
    setError('')
    setMessage('')
    if (!channelName.trim() || !hasRequiredChannelConfig()) {
      setError(t('settings.channelRequired'))
      return
    }
    setChannelSaving(true)
    try {
      await api.createChannel({
        name: channelName.trim(),
        type: channelType,
        config: channelConfig,
        enabled: true,
      })
      setChannelName('')
      setChannelConfig({})
      setMessage(t('settings.channelCreated'))
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setChannelSaving(false)
    }
  }

  async function testDraftChannel() {
    setError('')
    setMessage('')
    if (!hasRequiredChannelConfig()) {
      setError(t('settings.channelRequired'))
      return
    }
    setTestingDraftChannel(true)
    try {
      await api.testChannelConfig({ type: channelType, config: channelConfig })
      setMessage(t('settings.testSuccess'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setTestingDraftChannel(false)
    }
  }

  async function testCapabilities() {
    setTestingCapabilities(true)
    setError('')
    setMessage('')
    try {
      setCapabilities(await api.testAICapabilities(settings.ai))
    } catch (reason) {
      const code = reason instanceof Error ? reason.message : ''
      setError(
        code === 'ai_not_configured'
          ? t('ai.notConfigured')
          : code === 'ai_auth_failed'
          ? t('ai.authFailed')
          : code === 'ai_rate_limited'
            ? t('ai.rateLimited')
            : code === 'ai_unreachable' || code === 'ai_timeout'
              ? t('ai.unreachable')
              : code === 'ai_provider_error' ||
                  code === 'ai_invalid_response' ||
                  code === 'ai_config_failed'
                ? t('ai.configFailed')
              : reason instanceof Error
                ? reason.message
                : t('common.unknownError')
      )
    } finally {
      setTestingCapabilities(false)
    }
  }

  async function testChannel(channel: NotifyChannel) {
    setError('')
    setMessage('')
    setTestingChannelId(channel.id)
    try {
      await api.testChannel(channel.id)
      setMessage(t('settings.testSuccess'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setTestingChannelId(null)
    }
  }

  async function removeChannel(channel: NotifyChannel) {
    await api.removeChannel(channel.id)
    await load()
  }

  if (loading) return <Loading />

  return (
    <>
      <PageHeader
        eyebrow={t('settings.eyebrow')}
        title={t('settings.title')}
        subtitle={t('settings.subtitle')}
        action={
          <Button onClick={saveSettings} disabled={saving}>
            <Check size={15} />
            {saving ? t('common.loading') : t('settings.savePreferences')}
          </Button>
        }
      />
      {message ? <p className="form-success"><Check size={15} />{message}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      <div className="settings-layout">
        <GlassPanel className="settings-card language-card reveal">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('settings.language')}</p>
              <h2>{t('settings.displayLanguage')}</h2>
            </div>
          </div>
          <div className="language-choice">
            <button
              className={settings.language === 'zh-CN' ? 'active' : ''}
              onClick={() => selectLanguage('zh-CN')}
            >
              {t('settings.chinese')}
              <small>{t('settings.simplified')}</small>
            </button>
            <button
              className={settings.language === 'en-US' ? 'active' : ''}
              onClick={() => selectLanguage('en-US')}
            >
              {t('settings.english')}
              <small>US</small>
            </button>
          </div>
        </GlassPanel>

        <GlassPanel className="settings-card ai-settings-card reveal reveal-delay-1">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('settings.ai')}</p>
              <h2>{t('settings.diagnosisModel')}</h2>
            </div>
            {capabilities ? (
              <Badge tone={capabilities.ok ? 'success' : 'warn'}>
                <i className="status-dot" />
                {t(capabilities.ok ? 'settings.connected' : 'settings.connectionIssue')}
              </Badge>
            ) : null}
          </div>
          <div className="stack-form">
            <Field label={t('settings.baseUrl')}>
              <Input
                value={settings.ai.base_url}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    ai: { ...current.ai, base_url: event.target.value },
                  }))
                }
                placeholder="https://api.example.com/v1"
              />
            </Field>
            <Field label={t('settings.apiKey')}>
              <Input
                type="password"
                value={settings.ai.api_key}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    ai: { ...current.ai, api_key: event.target.value },
                  }))
                }
                placeholder="sk-…"
              />
            </Field>
            <Field label={t('settings.model')}>
              <Input
                value={settings.ai.model}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    ai: { ...current.ai, model: event.target.value },
                  }))
                }
              />
            </Field>
            <Field label={t('settings.visionModel')}>
              <Input
                value={settings.ai.vision_model}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    ai: { ...current.ai, vision_model: event.target.value },
                  }))
                }
              />
            </Field>
            <div className="capability-check">
              <Button
                variant="secondary"
                onClick={() => void testCapabilities()}
                disabled={testingCapabilities}
              >
                <Sparkles size={15} />
                {testingCapabilities ? t('common.loading') : t('settings.testCapabilities')}
              </Button>
              {capabilities ? (
                <div className="capability-results">
                  {([
                    ['json', 'settings.capabilityJson'],
                    ['tools', 'settings.capabilityTools'],
                    ['stream', 'settings.capabilityStream'],
                    ['vision', 'settings.capabilityVision'],
                  ] as const).map(([key, label]) => (
                    <Badge key={key} tone={capabilities[key] ? 'success' : 'warn'}>
                      {t(label)} {capabilities[key] ? '✓' : '×'}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </GlassPanel>

        <GlassPanel className="settings-card reveal">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('settings.newsIntel')}</p>
              <h2>{t('settings.researchSources')}</h2>
            </div>
          </div>
          <div className="stack-form">
            <label className="check-row">
              <input
                type="checkbox"
                checked={settings.news.enabled}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    news: { ...current.news, enabled: event.target.checked },
                  }))
                }
              />
              {t('settings.enableNews')}
            </label>
            <Field label={t('settings.newsProvider')}>
              <Select
                value={settings.news.provider}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    news: {
                      ...current.news,
                      provider: event.target.value as 'eastmoney' | 'tavily' | 'bocha',
                    },
                  }))
                }
              >
                <option value="eastmoney">{t('settings.providerEastmoney')}</option>
                <option value="tavily">{t('settings.providerTavily')}</option>
                <option value="bocha">{t('settings.providerBocha')}</option>
              </Select>
            </Field>
            {settings.news.provider !== 'eastmoney' ? (
              <Field label={t('settings.newsApiKey')}>
                <Input
                  type="password"
                  value={settings.news.api_key}
                  onChange={(event) =>
                    setSettings((current) => ({
                      ...current,
                      news: { ...current.news, api_key: event.target.value },
                    }))
                  }
                />
              </Field>
            ) : null}
          </div>
        </GlassPanel>

        <GlassPanel className="settings-card reveal reveal-delay-2">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('settings.dailyReview')}</p>
              <h2>{t('settings.reviewSchedule')}</h2>
            </div>
          </div>
          <label className="check-row">
            <input
              type="checkbox"
              checked={settings.daily_review_enabled}
              onChange={(event) =>
                setSettings((current) => ({
                  ...current,
                  daily_review_enabled: event.target.checked,
                }))
              }
            />
            {t('settings.enableReview')}
          </label>
          <p className="muted-copy">15:20 · Asia/Shanghai · Mon–Fri</p>
          <div className="channel-checks">
            {channels.map((channel) => (
              <label key={channel.id} className="check-row">
                <input
                  type="checkbox"
                  checked={settings.daily_review_channel_ids.includes(channel.id)}
                  onChange={(event) =>
                    setSettings((current) => ({
                      ...current,
                      daily_review_channel_ids: event.target.checked
                        ? [...current.daily_review_channel_ids, channel.id]
                        : current.daily_review_channel_ids.filter((id) => id !== channel.id),
                    }))
                  }
                />
                {channel.name}
              </label>
            ))}
          </div>
        </GlassPanel>

        <GlassPanel className="settings-card settings-wide notification-settings reveal">
          <div className="section-head">
            <div>
              <p className="eyebrow">{t('settings.notificationsEyebrow')}</p>
              <h2>{t('settings.notificationChannels')}</h2>
            </div>
            <Badge>{channels.length}</Badge>
          </div>
          <div className="channel-list">
            {channels.map((channel) => (
              <div className="channel-row" key={channel.id}>
                <span className="channel-icon">{channel.type === 'feishu' ? 'FS' : 'SMS'}</span>
                <div>
                  <strong>{channel.name}</strong>
                  <small>{channel.type === 'feishu' ? 'Feishu bot' : 'Aliyun SMS'}</small>
                </div>
                <Badge tone={channel.enabled ? 'success' : 'neutral'}>
                  {channel.enabled ? 'ON' : 'OFF'}
                </Badge>
                <button
                  className="text-action channel-test"
                  onClick={() => void testChannel(channel)}
                  disabled={testingChannelId === channel.id}
                >
                  <FlaskConical size={15} />
                  {testingChannelId === channel.id ? t('common.loading') : t('common.test')}
                </button>
                <button className="icon-button danger" onClick={() => removeChannel(channel)} title={t('common.delete')}>
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
            {!channels.length ? (
              <p className="muted-copy">{t('settings.noChannels')}</p>
            ) : null}
          </div>
          <div className="channel-builder">
            <div className="channel-builder-head">
              <div>
                <p className="eyebrow">{t('settings.newChannel')}</p>
                <h3>{t('settings.channelConfig')}</h3>
              </div>
              <p>{t('settings.channelConfigHint')}</p>
            </div>
            <div className="form-grid">
              <Field label={t('settings.channelName')}>
                <Input value={channelName} onChange={(event) => setChannelName(event.target.value)} />
              </Field>
              <Field label={t('settings.channelType')}>
                <Select
                  value={channelType}
                  onChange={(event) => {
                    setChannelType(event.target.value as 'feishu' | 'aliyun_sms')
                    setChannelConfig({})
                  }}
                >
                  <option value="feishu">Feishu</option>
                  <option value="aliyun_sms">Aliyun SMS</option>
                </Select>
              </Field>
              {channelType === 'feishu' ? (
                <>
                  <Field label={t('settings.webhook')}>
                    <Input value={channelConfig.webhook_url ?? ''} onChange={(event) => setConfigField('webhook_url', event.target.value)} />
                  </Field>
                  <Field label={t('settings.webhookSecret')}>
                    <Input type="password" value={channelConfig.secret ?? ''} onChange={(event) => setConfigField('secret', event.target.value)} />
                  </Field>
                </>
              ) : (
                <>
                  <Field label={t('settings.accessKeyId')}>
                    <Input value={channelConfig.access_key_id ?? ''} onChange={(event) => setConfigField('access_key_id', event.target.value)} />
                  </Field>
                  <Field label={t('settings.accessKeySecret')}>
                    <Input type="password" value={channelConfig.access_key_secret ?? ''} onChange={(event) => setConfigField('access_key_secret', event.target.value)} />
                  </Field>
                  <Field label={t('settings.smsSign')}>
                    <Input value={channelConfig.sign_name ?? ''} onChange={(event) => setConfigField('sign_name', event.target.value)} />
                  </Field>
                  <Field label={t('settings.smsTemplateZh')}>
                    <Input value={channelConfig.template_code_zh ?? ''} onChange={(event) => setConfigField('template_code_zh', event.target.value)} />
                  </Field>
                  <Field label={t('settings.smsTemplateEn')}>
                    <Input value={channelConfig.template_code_en ?? ''} onChange={(event) => setConfigField('template_code_en', event.target.value)} />
                  </Field>
                  <Field label={t('settings.phoneNumbers')}>
                    <Input value={channelConfig.phone_numbers ?? ''} onChange={(event) => setConfigField('phone_numbers', event.target.value)} />
                  </Field>
                </>
              )}
            </div>
            <div className="channel-builder-actions">
              <Button
                variant="secondary"
                onClick={() => void testDraftChannel()}
                disabled={testingDraftChannel || channelSaving}
              >
                <FlaskConical size={15} />
                {testingDraftChannel ? t('common.loading') : t('settings.testConfig')}
              </Button>
              <Button
                onClick={() => void addChannel()}
                disabled={channelSaving || testingDraftChannel}
              >
                <Plus size={15} />
                {channelSaving ? t('common.loading') : t('settings.saveChannel')}
              </Button>
            </div>
          </div>
        </GlassPanel>

        <GlassPanel className="data-boundary settings-wide reveal">
          <div className="boundary-icon"><ShieldAlert size={20} /></div>
          <div>
            <h3>{t('settings.dataBoundary')}</h3>
            <p>{t('settings.dataBoundaryText')}</p>
          </div>
        </GlassPanel>
      </div>

    </>
  )
}

