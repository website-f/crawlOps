import {
  IconAntenna, IconBell, IconBolt, IconChartArcs, IconCpu, IconFileText,
  IconHeartRateMonitor, IconHelp, IconLayoutDashboard, IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarRightCollapse, IconLogout, IconMap2,
  IconMenu2, IconMoodSmile, IconPlanet, IconPlug, IconScale, IconSettings,
  IconSparkles, IconTable, IconTargetArrow, IconUserOff, IconUsersGroup,
  IconUsers, IconShieldLock, IconX,
} from '@tabler/icons-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { clearToken, get, getToken } from './lib/api'
import Login from './pages/Login'

// pages load on demand so three.js / leaflet / recharts stay out of the first paint
const AIEngine = lazy(() => import('./pages/AIEngine'))
const Alerts = lazy(() => import('./pages/Alerts'))
const Authors = lazy(() => import('./pages/Authors'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Audience = lazy(() => import('./pages/Audience'))
const Competitors = lazy(() => import('./pages/Competitors'))
const Dashboards = lazy(() => import('./pages/Dashboards'))
const DataExplorer = lazy(() => import('./pages/DataExplorer'))
const Feed = lazy(() => import('./pages/Feed'))
const DarkWeb = lazy(() => import('./pages/DarkWeb'))
const Galaxy = lazy(() => import('./pages/Galaxy'))
const MapView = lazy(() => import('./pages/MapView'))
const Search = lazy(() => import('./pages/Search'))
const SettingsPage = lazy(() => import('./pages/Settings'))
const Sources = lazy(() => import('./pages/Sources'))
const SystemHealth = lazy(() => import('./pages/SystemHealth'))
const Suppression = lazy(() => import('./pages/Suppression'))
const Topics = lazy(() => import('./pages/Topics'))
const Tutorial = lazy(() => import('./pages/Tutorial'))

const GROUPS: { label: string; items: { to: string; label: string; Icon: any }[] }[] = [
  {
    label: 'Listen',
    items: [
      { to: '/', label: 'Feed', Icon: IconAntenna },
      { to: '/search', label: 'Semantic Search', Icon: IconSparkles },
      { to: '/darkweb', label: 'Dark Web', Icon: IconShieldLock },
      { to: '/topics', label: 'Topics', Icon: IconTargetArrow },
      { to: '/map', label: 'Geography', Icon: IconMap2 },
    ],
  },
  {
    label: 'Analyze',
    items: [
      { to: '/analytics', label: 'Overview', Icon: IconLayoutDashboard },
      { to: '/dashboards', label: 'Dashboards', Icon: IconLayoutDashboard },
      { to: '/analytics/health', label: 'Brand Health', Icon: IconHeartRateMonitor },
      { to: '/analytics/sentiment', label: 'Sentiment & Emotions', Icon: IconMoodSmile },
      { to: '/analytics/trends', label: 'Trends', Icon: IconChartArcs },
      { to: '/analytics/influencers', label: 'Influencers', Icon: IconUsersGroup },
      { to: '/audience', label: 'Audience & Issues', Icon: IconUsers },
      { to: '/authors', label: 'Author Intel', Icon: IconUsersGroup },
      { to: '/galaxy', label: 'Galaxy', Icon: IconPlanet },
      { to: '/analytics/brief', label: 'Daily Brief', Icon: IconFileText },
      { to: '/competitors', label: 'Competitors', Icon: IconScale },
      { to: '/explore', label: 'Data Explorer', Icon: IconTable },
    ],
  },
  {
    label: 'Act',
    items: [
      { to: '/alerts', label: 'Alerts', Icon: IconBell },
      { to: '/suppression', label: 'Suppression', Icon: IconUserOff },
    ],
  },
  {
    label: 'Configure',
    items: [
      { to: '/sources', label: 'Sources', Icon: IconPlug },
      { to: '/system', label: 'Crawl Ops', Icon: IconBolt },
      { to: '/ai', label: 'AI Engine', Icon: IconCpu },
      { to: '/settings', label: 'Settings', Icon: IconSettings },
      { to: '/tutorial', label: 'Tutorial', Icon: IconHelp },
    ],
  },
]
const ALL_ITEMS = GROUPS.flatMap((g) => g.items)

function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="w-8 h-8 rounded-xl bg-ink grid place-items-center shadow-raise shrink-0">
        <IconAntenna size={17} color="#fcfcfb" stroke={2} />
      </span>
      {!collapsed && <span className="font-bold text-[17px] tracking-tight leading-none">Crawl<span className="text-accent">Ops</span></span>}
    </div>
  )
}

function NavItems({ onNavigate, onLogout, collapsed = false }: { onNavigate?: () => void; onLogout: () => void; collapsed?: boolean }) {
  return (
    <nav className="px-2.5 py-2 flex flex-col h-full overflow-y-auto">
      {GROUPS.map((g, gi) => (
        <div key={g.label} className="mb-0.5">
          {collapsed
            ? (gi > 0 && <div className="mx-2 my-2 border-t border-grid" />)
            : <div className="px-3 pt-4 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.09em] text-muted">{g.label}</div>}
          {g.items.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} end={to === '/' || to === '/analytics'} onClick={onNavigate}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `group relative flex items-center rounded-lg text-[13px] transition-colors
                 ${collapsed ? 'justify-center py-2.5' : 'gap-2.5 px-3 py-2'}
                 ${isActive
                   ? 'bg-accent/10 text-accent-ink font-semibold'
                   : 'text-inksec font-medium hover:bg-plane hover:text-ink'}`}>
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[3px] rounded-r-full bg-accent" />}
                  <Icon size={collapsed ? 19 : 16.5} stroke={2} className={`shrink-0 ${isActive ? '' : 'text-muted group-hover:text-inksec'}`} />
                  {!collapsed && <span className="truncate">{label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </div>
      ))}
      <button onClick={onLogout} title={collapsed ? 'Sign out' : undefined}
        className={`mt-3 mb-1 flex items-center rounded-lg text-[13px] font-medium text-inksec hover:bg-danger/5 hover:text-danger transition-colors
          ${collapsed ? 'justify-center py-2.5' : 'gap-2.5 px-3 py-2'}`}>
        <IconLogout size={collapsed ? 19 : 16.5} stroke={2} />{!collapsed && 'Sign out'}
      </button>
    </nav>
  )
}

function Shell() {
  const [drawer, setDrawer] = useState(false)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('crawlops.sidebar') === '1')
  const toggleCollapse = () => setCollapsed((c) => { localStorage.setItem('crawlops.sidebar', c ? '0' : '1'); return !c })
  const location = useLocation()
  const navigate = useNavigate()
  const current = ALL_ITEMS.find((n) => n.to === location.pathname)?.label ?? 'CrawlOps'
  const logout = () => { clearToken(); navigate('/login') }

  return (
    <div className="min-h-[100dvh] bg-plane text-ink lg:flex">
      <aside className={`hidden lg:flex shrink-0 border-r border-grid bg-surface flex-col sticky top-0 h-[100dvh] transition-[width] duration-200 ${collapsed ? 'w-16' : 'w-60'}`}>
        <div className={`h-16 flex items-center border-b border-grid ${collapsed ? 'justify-center' : 'px-4 justify-between'}`}>
          {collapsed ? (
            <button onClick={toggleCollapse} title="Expand sidebar" className="p-1.5 rounded-lg hover:bg-plane transition active:scale-95">
              <IconLayoutSidebarRightCollapse size={20} stroke={2} className="text-inksec" />
            </button>
          ) : (
            <>
              <Brand />
              <button onClick={toggleCollapse} title="Collapse sidebar" className="p-1.5 rounded-lg hover:bg-plane transition active:scale-95 text-muted hover:text-ink">
                <IconLayoutSidebarLeftCollapse size={19} stroke={2} />
              </button>
            </>
          )}
        </div>
        <NavItems onLogout={logout} collapsed={collapsed} />
      </aside>

      <header className="lg:hidden sticky top-0 z-40 flex items-center gap-3 px-4 h-14 bg-surface/90 backdrop-blur border-b border-grid">
        <button onClick={() => setDrawer(true)} aria-label="Open menu" className="p-1.5 -ml-1.5 rounded-lg hover:bg-plane active:scale-[0.96] transition">
          <IconMenu2 size={20} stroke={2} />
        </button>
        <Brand />
        <span className="ml-auto text-[13px] font-medium text-inksec truncate max-w-[45%]">{current}</span>
      </header>

      {drawer && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-ink/40 backdrop-blur-[2px] animate-[fade_.15s_ease-out]" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-[17rem] max-w-[82vw] bg-surface shadow-float flex flex-col animate-[drawerin_.22s_cubic-bezier(.16,1,.3,1)]">
            <div className="flex items-center justify-between px-4 h-16 border-b border-grid">
              <Brand />
              <button onClick={() => setDrawer(false)} aria-label="Close menu" className="p-1.5 rounded-lg hover:bg-plane transition"><IconX size={18} stroke={2} /></button>
            </div>
            <div className="flex-1 overflow-hidden"><NavItems onNavigate={() => setDrawer(false)} onLogout={logout} /></div>
          </div>
        </div>
      )}

      <main className="flex-1 min-w-0 p-4 sm:p-5 lg:p-7 max-w-[1500px] w-full mx-auto lg:mx-0">
        <Suspense fallback={
          <div className="py-24 grid place-items-center">
            <span className="w-7 h-7 rounded-full border-2 border-grid border-t-accent animate-spin" />
          </div>
        }>
        <Routes>
          <Route path="/" element={<Feed />} />
          <Route path="/search" element={<Search />} />
          <Route path="/darkweb" element={<DarkWeb />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/analytics" element={<Analytics view="overview" />} />
          <Route path="/analytics/health" element={<Analytics view="health" />} />
          <Route path="/analytics/sentiment" element={<Analytics view="sentiment" />} />
          <Route path="/analytics/trends" element={<Analytics view="trends" />} />
          <Route path="/analytics/influencers" element={<Analytics view="influencers" />} />
          <Route path="/competitors" element={<Competitors />} />
          <Route path="/dashboards" element={<Dashboards />} />
          <Route path="/audience" element={<Audience />} />
          <Route path="/authors" element={<Authors />} />
          <Route path="/explore" element={<DataExplorer />} />
          <Route path="/galaxy" element={<Galaxy />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/system" element={<SystemHealth />} />
          <Route path="/ai" element={<AIEngine />} />
          <Route path="/suppression" element={<Suppression />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/tutorial" element={<Tutorial />} />
        </Routes>
        </Suspense>
      </main>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (!getToken()) { setAuthed(false); return }
    get('/auth/me').then(() => setAuthed(true)).catch(() => setAuthed(false))
  }, [])

  useEffect(() => {
    if (authed === false && location.pathname !== '/login') navigate('/login')
    if (authed === true && location.pathname === '/login') navigate('/')
  }, [authed, location.pathname])

  if (authed === null) return (
    <div className="min-h-[100dvh] grid place-items-center bg-plane">
      <span className="w-7 h-7 rounded-full border-2 border-grid border-t-accent animate-spin" />
    </div>
  )

  return (
    <Routes>
      <Route path="/login" element={<Login onAuthed={() => setAuthed(true)} />} />
      <Route path="*" element={authed ? <Shell /> : <Login onAuthed={() => setAuthed(true)} />} />
    </Routes>
  )
}
