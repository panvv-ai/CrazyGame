import { lazy, Suspense, useEffect, useRef } from 'react'
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

const mobileNav = [
  { to: '/', icon: LayoutDashboard, key: 'nav.overview', end: true },
  { to: '/watchlist', icon: Star, key: 'nav.watchlist' },
  { to: '/ai', icon: Sparkles, key: 'nav.ai' },
  { to: '/holdings', icon: Activity, key: 'nav.holdings' },
  { to: '/alerts', icon: BellRing, key: 'nav.alerts' },
]

function AuroraBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const context = canvas.getContext('2d')
    if (!context) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const root = document.documentElement
    let frame = 0
    let width = 0
    let height = 0
    let dpr = 1

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = Math.max(1, Math.round(rect.width * dpr))
      height = Math.max(1, Math.round(rect.height * dpr))
      canvas.width = width
      canvas.height = height
    }

    const draw = (time = 0) => {
      const styles = getComputedStyle(root)
      const colors = [
        styles.getPropertyValue('--color-glow-blue').trim(),
        styles.getPropertyValue('--color-glow-cyan').trim(),
        styles.getPropertyValue('--color-glow-violet').trim(),
        styles.getPropertyValue('--color-glow-white').trim(),
      ]
      const scroll = window.scrollY || 0
      const slowTime = reduceMotion.matches ? 0 : time * 0.000055
      const drift = reduceMotion.matches ? 0 : Math.min(scroll * 0.06, 120) * dpr

      context.clearRect(0, 0, width, height)
      context.globalCompositeOperation = 'screen'
      const blobs = [
        [width * (0.28 + Math.sin(slowTime) * 0.04), height * 0.18 + drift, 0.31, colors[0]],
        [width * (0.72 + Math.cos(slowTime * 1.15) * 0.035), height * 0.27 + drift * 0.75, 0.24, colors[2]],
        [width * (0.52 + Math.sin(slowTime * 0.8 + 1.8) * 0.06), height * 0.12 + drift * 0.5, 0.18, colors[1]],
        [width * (0.5 + Math.cos(slowTime * 0.5) * 0.05), height * 0.08 + drift * 0.35, 0.12, colors[3]],
      ] as const

      for (const [x, y, scale, color] of blobs) {
        const radius = Math.max(width, height) * scale
        const gradient = context.createRadialGradient(x, y, 0, x, y, radius)
        gradient.addColorStop(0, color)
        gradient.addColorStop(1, 'transparent')
        context.fillStyle = gradient
        context.beginPath()
        context.arc(x, y, radius, 0, Math.PI * 2)
        context.fill()
      }
      context.globalCompositeOperation = 'source-over'
    }

    const animate = (time: number) => {
      draw(time)
      if (!reduceMotion.matches) frame = requestAnimationFrame(animate)
    }
    const onScroll = () => {
      root.style.setProperty('--scroll-shift', String(Math.min(window.scrollY || 0, 900)))
      root.style.setProperty(
        '--surface-glint',
        String(22 + Math.min((window.scrollY || 0) * 0.025, 30))
      )
      if (reduceMotion.matches) draw()
    }
    const onMotionChange = () => {
      cancelAnimationFrame(frame)
      if (reduceMotion.matches) {
        draw()
      } else {
        frame = requestAnimationFrame(animate)
      }
    }

    resize()
    onScroll()
    draw()
    if (!reduceMotion.matches) frame = requestAnimationFrame(animate)
    window.addEventListener('resize', resize)
    window.addEventListener('scroll', onScroll, { passive: true })
    reduceMotion.addEventListener('change', onMotionChange)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      window.removeEventListener('scroll', onScroll)
      reduceMotion.removeEventListener('change', onMotionChange)
    }
  }, [])

  return (
    <div className="aurora" aria-hidden="true">
      <canvas ref={canvasRef} className="aurora-canvas" />
      <div className="aurora-haze" />
      <div className="aurora-grid" />
      <div className="aurora-horizon" />
      <div className="aurora-noise" />
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
          <span className="market-status">
            <i />
            {t('product.observing')}
          </span>
          <button
            className="ai-button"
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
        {mobileNav.map(({ to, icon: Icon, key, end }) => (
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

