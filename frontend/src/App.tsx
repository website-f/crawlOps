import {
  IconAntenna, IconBell, IconChartBar, IconCpu, IconMap2, IconMenu2, IconPlug,
  IconSettings, IconTargetArrow, IconUserOff, IconX,
} from '@tabler/icons-react'
import { useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import AIEngine from './pages/AIEngine'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import Feed from './pages/Feed'
import MapView from './pages/MapView'
import SettingsPage from './pages/Settings'
import Sources from './pages/Sources'
import Suppression from './pages/Suppression'
import Topics from './pages/Topics'

const NAV = [
  { to: '/', label: 'Feed', Icon: IconAntenna },
  { to: '/topics', label: 'Topics', Icon: IconTargetArrow },
  { to: '/analytics', label: 'Analytics', Icon: IconChartBar },
  { to: '/map', label: 'Map', Icon: IconMap2 },
  { to: '/alerts', label: 'Alerts', Icon: IconBell },
  { to: '/sources', label: 'Sources', Icon: IconPlug },
  { to: '/ai', label: 'AI Engine', Icon: IconCpu },
  { to: '/suppression', label: 'Suppression', Icon: IconUserOff },
  { to: '/settings', label: 'Settings', Icon: IconSettings },
]

function Brand() {
  return (
    <div className="flex items-center gap-2">
      <span className="w-7 h-7 rounded-lg bg-ink grid place-items-center">
        <IconAntenna size={16} color="#fcfcfb" stroke={2} />
      </span>
      <span className="font-bold text-[17px] tracking-tight">
        Crawl<span className="text-[#2a78d6]">Ops</span>
      </span>
    </div>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="p-2 space-y-0.5">
      {NAV.map(({ to, label, Icon }) => (
        <NavLink key={to} to={to} end={to === '/'} onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm font-medium transition
             ${isActive ? 'bg-ink text-white' : 'text-inksec hover:bg-plane'}`}>
          <Icon size={17} stroke={2} className="shrink-0" />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

export default function App() {
  const [drawer, setDrawer] = useState(false)
  const location = useLocation()
  const current = NAV.find((n) => n.to === location.pathname)?.label ?? 'Feed'

  return (
    <div className="min-h-[100dvh] bg-plane text-ink lg:flex">
      {/* desktop sidebar */}
      <aside className="hidden lg:flex w-52 shrink-0 border-r border-grid bg-white flex-col
                        sticky top-0 h-[100dvh]">
        <div className="px-4 py-4 border-b border-grid"><Brand /></div>
        <NavItems />
      </aside>

      {/* mobile top bar */}
      <header className="lg:hidden sticky top-0 z-40 flex items-center gap-3 px-4 h-14
                         bg-white border-b border-grid">
        <button onClick={() => setDrawer(true)} aria-label="Open menu"
          className="p-1.5 -ml-1.5 rounded-lg hover:bg-plane active:scale-[0.96]">
          <IconMenu2 size={20} stroke={2} />
        </button>
        <Brand />
        <span className="ml-auto text-sm text-inksec">{current}</span>
      </header>

      {/* mobile drawer */}
      {drawer && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 w-64 bg-white shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-4 border-b border-grid">
              <Brand />
              <button onClick={() => setDrawer(false)} aria-label="Close menu"
                className="p-1.5 rounded-lg hover:bg-plane">
                <IconX size={18} stroke={2} />
              </button>
            </div>
            <NavItems onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      )}

      <main className="flex-1 min-w-0 p-4 lg:p-6 max-w-[1500px] w-full mx-auto lg:mx-0">
        <Routes>
          <Route path="/" element={<Feed />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/ai" element={<AIEngine />} />
          <Route path="/suppression" element={<Suppression />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}
