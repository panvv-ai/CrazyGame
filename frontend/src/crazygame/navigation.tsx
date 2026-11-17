import {
  Activity,
  BellRing,
  Blocks,
  LayoutDashboard,
  Star,
  type LucideIcon,
} from 'lucide-react'

export interface NavigationItem {
  path: string
  icon: LucideIcon
  key: string
  end?: boolean
}

export const primaryNavigation: NavigationItem[] = [
  { path: '/', icon: LayoutDashboard, key: 'nav.overview', end: true },
  { path: '/watchlist', icon: Star, key: 'nav.watchlist' },
  { path: '/groups', icon: Blocks, key: 'nav.groups' },
  { path: '/holdings', icon: Activity, key: 'nav.holdings' },
  { path: '/alerts', icon: BellRing, key: 'nav.alerts' },
]
