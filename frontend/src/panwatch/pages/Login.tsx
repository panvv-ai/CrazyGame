import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowRight, Eye, EyeOff, Languages, Orbit } from 'lucide-react'

import { api, setToken } from '../api'
import { Button, GlassPanel, Input } from '../components/ui'
import { changeLanguage } from '../i18n'

export function LoginPage({
  initialized,
  onAuthenticated,
}: {
  initialized: boolean
  onAuthenticated: () => void
}) {
  const { t, i18n } = useTranslation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const result = initialized
        ? await api.login(username.trim(), password)
        : await api.setup(username.trim(), password)
      setToken(result.token)
      onAuthenticated()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-aurora" aria-hidden="true" />
      <button
        className="auth-language"
        onClick={() => changeLanguage(i18n.language === 'zh-CN' ? 'en-US' : 'zh-CN')}
        aria-label={t('settings.language')}
      >
        <Languages size={16} />
        {i18n.language === 'zh-CN' ? 'EN' : 'ZH'}
      </button>
      <GlassPanel className="auth-card">
        <div className="auth-mark">
          <Orbit size={24} />
        </div>
        <p className="eyebrow">{t('product.tagline')}</p>
        <h1>{t(initialized ? 'auth.loginTitle' : 'auth.setupTitle')}</h1>
        <p className="auth-subtitle">{t('auth.subtitle')}</p>
        <form onSubmit={submit}>
          <label className="field">
            <span>{t('auth.username')}</span>
            <Input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label className="field">
            <span>{t('auth.password')}</span>
            <span className="input-with-action">
              <Input
                type={visible ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={initialized ? 'current-password' : 'new-password'}
                minLength={8}
                required
              />
              <button
                type="button"
                className="field-icon"
                onClick={() => setVisible((value) => !value)}
                aria-label={visible ? 'hide password' : 'show password'}
              >
                {visible ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </span>
            <small>{t('auth.passwordHint')}</small>
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <Button className="auth-submit" type="submit" disabled={submitting}>
            {submitting ? t('common.loading') : t(initialized ? 'auth.login' : 'auth.setup')}
            <ArrowRight size={17} />
          </Button>
        </form>
      </GlassPanel>
      <p className="auth-note">{t('product.disclaimer')}</p>
    </main>
  )
}

