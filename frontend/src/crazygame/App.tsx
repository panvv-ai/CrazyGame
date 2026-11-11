import { lazy, Suspense, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  BellRing,
  Blocks,
  Activity,
  Languages,
  LayoutDashboard,
  Orbit,
  Settings,
  Sparkles,
  Star,
} from 'lucide-react'

import { api } from './api'
import { changeLanguage, default as i18n } from './i18n'
import type { Language } from './lib'
import { OverviewPage } from './pages/Overview'
import { WatchlistPage } from './pages/Watchlist'
import { GroupsPage } from './pages/Groups'
import { HoldingsPage } from './pages/Holdings'
import { AlertsPage } from './pages/Alerts'
import { SettingsPage } from './pages/Settings'
import { Loading } from './components/ui'

const AIPage = lazy(() =>
  import('./pages/AI').then((module) => ({ default: module.AIPage }))
)

const nav = [
  { to: '/', icon: LayoutDashboard, key: 'nav.overview', end: true },
  { to: '/watchlist', icon: Star, key: 'nav.watchlist' },
  { to: '/groups', icon: Blocks, key: 'nav.groups' },
  { to: '/holdings', icon: Activity, key: 'nav.holdings' },
  { to: '/alerts', icon: BellRing, key: 'nav.alerts' },
]

function AuroraBackground() {
  return (
    <div className="aurora" aria-hidden="true">
      <div className="aurora-orb aurora-orb-a" />
      <div className="aurora-orb aurora-orb-b" />
      <div className="aurora-grid" />
      <div className="aurora-horizon" />
    </div>
  )
}

function LanguageButton({ onChanged }: { onChanged?: () => void }) {
  const { t, i18n: instance } = useTranslation()
  const next: Language = instance.language === 'zh-CN' ? 'en-US' : 'zh-CN'
  return (
    <button
      className="utility-button"
      title={t(next === 'zh-CN' ? 'settings.switchToChinese' : 'settings.switchToEnglish')}
      onClick={async () => {
        await changeLanguage(next)
        onChanged?.()
      }}
    >
      <Languages size={16} />
      <span>{next === 'zh-CN' ? t('settings.chineseShort') : 'EN'}</span>
    </button>
  )
}

export default function App() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [location.pathname])

  useEffect(() => {
    api.settings()
      .then((settings) => {
        if (settings.language !== i18n.language) {
          return changeLanguage(settings.language)
        }
      })
      .catch(() => undefined)
  }, [])

  async function syncLanguage() {
    try {
      const current = await api.settings()
      await api.updateSettings({ ...current, language: i18n.language as Language })
    } catch {
      // The visible language still switches locally.
    }
  }

  return (
    <div className="app-shell">
      <AuroraBackground />
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="brand-mark">
            <Orbit size={18} />
          </span>
          <span>
            <strong>{t('product.name')}</strong>
            <small>{t('product.tagline')}</small>
          </span>
        </NavLink>
        <nav className="desktop-nav" aria-label="primary navigation">
          {nav.map(({ to, icon: Icon, key, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={16} />
              {t(key)}
            </NavLink>
          ))}
        </nav>
        <div className="topbar-actions">
          <button
            className="utility-button ai-launch-button"
            onClick={() => navigate('/ai')}
            aria-label={t('nav.ai')}
          >
            <Sparkles size={16} />
            <span>{t('nav.ai')}</span>
          </button>
          <LanguageButton onChanged={syncLanguage} />
          <button
            className="utility-button"
            onClick={() => navigate('/settings')}
            aria-label={t('nav.settings')}
          >
            <Settings size={17} />
          </button>
        </div>
      </header>

      <main className="main-content" key={location.pathname}>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/groups" element={<GroupsPage />} />
          <Route path="/holdings" element={<HoldingsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route
            path="/ai"
            element={
              <Suspense fallback={<Loading />}>
                <AIPage />
              </Suspense>
            }
          />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <nav className="mobile-nav" aria-label="primary navigation">
        {nav.map(({ to, icon: Icon, key, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}
          >
            <Icon size={19} />
            <span>{t(key)}</span>
          </NavLink>
        ))}
      </nav>
      <footer className="app-footer">{t('product.disclaimer')}</footer>
    </div>
  )
}

