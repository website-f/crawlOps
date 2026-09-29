import {
  IconAntenna, IconBell, IconBolt, IconChartArcs, IconCpu, IconFileText,
  IconHeartRateMonitor, IconHelp, IconLayoutDashboard, IconLogout, IconMap2,
  IconMenu2, IconMoodSmile, IconPlanet, IconPlug, IconScale, IconSettings,
  IconSparkles, IconTable, IconTargetArrow, IconUserOff, IconUsersGroup,
  IconUsers, IconX,
} from '@tabler/icons-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { clearToken, get, getToken } from './lib/api'
import Login from './pages/Login'

// pages load on demand so three.js / leaflet / recharts stay out of the first paint
const AIEngine = lazy(() => import('./pages/AIEngine'))
const Alerts = lazy(() => import('./pages/Alerts'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Audience = lazy(() => import('./pages/Audience'))
const Competitors = lazy(() => import('./pages/Competitors'))
const DataExplorer = lazy(() => import('./pages/DataExplorer'))
const Feed = lazy(() => import('./pages/Feed'))
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
      { to: '/topics', label: 'Topics', Icon: IconTargetArrow },
      { to: '/map', label: 'Geography', Icon: IconMap2 },
    ],
  },
  {
    label: 'Analyze',
    items: [
      { to: '/analytics', label: 'Overview', Icon: IconLayoutDashboard },
      { to: '/analytics/health', label: 'Brand Health', Icon: IconHeartRateMonitor },
      { to: '/analytics/sentiment', label: 'Sentiment & Emotions', Icon: IconMoodSmile },
      { to: '/analytics/trends', label: 'Trends', Icon: IconChartArcs },
      { to: '/analytics/influencers', label: 'Influencers', Icon: IconUsersGroup },
      { to: '/audience', label: 'Audience & Issues', Icon: IconUsers },
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

function Brand() {
  return (
    <div className="flex items-center gap-2">
      <span className="w-7 h-7 rounded-lg bg-ink grid place-items-center">
        <IconAntenna size={16} color="#fcfcfb" stroke={2} />
      </span>
      <span className="font-bold text-[17px] tracking-tight">Crawl<span className="text-[#2a78d6]">Ops</span></span>
    </div>
  )
}

function NavItems({ onNavigate, onLogout }: { onNavigate?: () => void; onLogout: () => void }) {
  return (
    <nav className="p-2 flex flex-col h-full overflow-y-auto">
      {GROUPS.map((g) => (
        <div key={g.label} className="mb-1">
          <div className="px-3 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">{g.label}</div>
          {g.items.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} end={to === '/' || to === '/analytics'} onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-1.5 rounded-xl text-[13px] font-medium transition
                 ${isActive ? 'bg-ink text-white' : 'text-inksec hover:bg-plane'}`}>
              <Icon size={16} stroke={2} className="shrink-0" />{label}
            </NavLink>
          ))}
        </div>
      ))}
      <button onClick={onLogout}
        className="mt-auto flex items-center gap-2.5 px-3 py-2 rounded-xl text-[13px] font-medium text-inksec hover:bg-plane">
        <IconLogout size={16} stroke={2} />Sign out
      </button>
    </nav>
  )
}

function Shell() {
  const [drawer, setDrawer] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const current = ALL_ITEMS.find((n) => n.to === location.pathname)?.label ?? 'CrawlOps'
  const logout = () => { clearToken(); navigate('/login') }

  return (
    <div className="min-h-[100dvh] bg-plane text-ink lg:flex">
      <aside className="hidden lg:flex w-56 shrink-0 border-r border-grid bg-white flex-col sticky top-0 h-[100dvh]">
        <div className="px-4 py-4 border-b border-grid"><Brand /></div>
        <NavItems onLogout={logout} />
      </aside>

      <header className="lg:hidden sticky top-0 z-40 flex items-center gap-3 px-4 h-14 bg-white border-b border-grid">
        <button onClick={() => setDrawer(true)} aria-label="Open menu" className="p-1.5 -ml-1.5 rounded-lg hover:bg-plane active:scale-[0.96]">
          <IconMenu2 size={20} stroke={2} />
        </button>
        <Brand />
        <span className="ml-auto text-sm text-inksec truncate max-w-[45%]">{current}</span>
      </header>

      {drawer && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-64 bg-white shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-4 border-b border-grid">
              <Brand />
              <button onClick={() => setDrawer(false)} aria-label="Close menu" className="p-1.5 rounded-lg hover:bg-plane"><IconX size={18} stroke={2} /></button>
            </div>
            <div className="flex-1 overflow-hidden"><NavItems onNavigate={() => setDrawer(false)} onLogout={logout} /></div>
          </div>
        </div>
      )}

      <main className="flex-1 min-w-0 p-4 lg:p-6 max-w-[1500px] w-full mx-auto lg:mx-0">
        <Suspense fallback={<div className="py-20 grid place-items-center text-muted">Loading…</div>}>
        <Routes>
          <Route path="/" element={<Feed />} />
          <Route path="/search" element={<Search />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/analytics" element={<Analytics view="overview" />} />
          <Route path="/analytics/health" element={<Analytics view="health" />} />
          <Route path="/analytics/sentiment" element={<Analytics view="sentiment" />} />
          <Route path="/analytics/trends" element={<Analytics view="trends" />} />
          <Route path="/analytics/influencers" element={<Analytics view="influencers" />} />
          <Route path="/competitors" element={<Competitors />} />
          <Route path="/audience" element={<Audience />} />
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

  if (authed === null) return <div className="min-h-[100dvh] grid place-items-center text-muted">Loading…</div>

  return (
    <Routes>
      <Route path="/login" element={<Login onAuthed={() => setAuthed(true)} />} />
      <Route path="*" element={authed ? <Shell /> : <Login onAuthed={() => setAuthed(true)} />} />
    </Routes>
  )
}
