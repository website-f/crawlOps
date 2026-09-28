import { IconCheck } from '@tabler/icons-react'
import { PlatformIcon } from './PlatformIcon'

// Semicircle gauge for a 0-100 score. color adapts to the value band.
export function Gauge({ value, label, sublabel, band }: {
  value: number; label: string; sublabel?: string
  band?: (v: number) => string
}) {
  const v = Math.max(0, Math.min(100, value))
  const color = band ? band(v) : v >= 65 ? '#0ca30c' : v >= 50 ? '#eda100' : '#d03b3b'
  const r = 52
  const circ = Math.PI * r // half circle
  const dash = (v / 100) * circ
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 140 78" className="w-40 h-[88px]">
        <path d="M 18 70 A 52 52 0 0 1 122 70" fill="none" stroke="#e1e0d9" strokeWidth="12" strokeLinecap="round" />
        <path d="M 18 70 A 52 52 0 0 1 122 70" fill="none" stroke={color} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`} style={{ transition: 'stroke-dasharray 0.6s ease' }} />
        <text x="70" y="58" textAnchor="middle" className="fill-ink" style={{ fontSize: 26, fontWeight: 700 }}>{Math.round(v)}</text>
      </svg>
      <div className="text-sm font-semibold -mt-1" style={{ color }}>{label}</div>
      {sublabel && <div className="text-xs text-muted">{sublabel}</div>}
    </div>
  )
}

export function Sparkline({ data, color = '#2a78d6' }: { data: number[]; color?: string }) {
  if (!data.length) return null
  const w = 120, h = 28, max = Math.max(...data, 1), min = Math.min(...data, 0)
  const range = max - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1 || 1)) * w},${h - ((v - min) / range) * h}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-7" preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="bg-white border border-grid rounded-2xl p-4">
      <div className="text-xs text-inksec">{label}</div>
      <div className="text-2xl font-semibold text-ink mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-muted mt-0.5">{hint}</div>}
    </div>
  )
}

export function Panel({ title, right, children, className = '' }: {
  title: string; right?: React.ReactNode; children: React.ReactNode; className?: string
}) {
  return (
    <div className={`bg-white border border-grid rounded-2xl p-4 ${className}`}>
      <div className="flex items-center mb-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </div>
  )
}

// Multi-select facet panel with live counts and cross-filter highlighting.
export function FacetPanel({ title, options, selected, onToggle, icon }: {
  title: string
  options: { value: string; count: number; label?: string }[]
  selected: string[]
  onToggle: (v: string) => void
  icon?: (v: string) => React.ReactNode
}) {
  if (!options.length) return null
  const max = Math.max(...options.map((o) => o.count), 1)
  return (
    <div className="border-b border-grid/70 pb-3 mb-3 last:border-0">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted mb-1.5">{title}</div>
      <div className="space-y-0.5">
        {options.slice(0, 12).map((o) => {
          const on = selected.includes(o.value)
          return (
            <button key={o.value} onClick={() => onToggle(o.value)}
              className={`relative w-full flex items-center gap-2 px-2 py-1 rounded-lg text-[13px] transition
                ${on ? 'bg-ink text-white' : 'hover:bg-plane text-inksec'}`}>
              <span className={`w-3.5 h-3.5 rounded border grid place-items-center shrink-0
                ${on ? 'bg-white border-white' : 'border-grid'}`}>
                {on && <IconCheck size={11} stroke={3} className="text-ink" />}
              </span>
              {icon && <span className="shrink-0">{icon(o.value)}</span>}
              <span className="truncate flex-1 text-left capitalize">{o.label || o.value}</span>
              <span className={`tabular-nums text-[11px] ${on ? 'text-white/80' : 'text-muted'}`}>{o.count}</span>
              {!on && (
                <span className="absolute left-0 bottom-0 h-0.5 rounded-full bg-grid"
                  style={{ width: `${(o.count / max) * 100}%` }} />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export const platformIconFor = (v: string) => <PlatformIcon platform={v} size={13} />
