import { IconAlertTriangle, IconRefresh, IconSearch, IconShieldLock, IconWorldWww, IconX } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { get, post, put } from '../lib/api'

interface Finding {
  id: number; source_url: string; source_host: string; source_type: string
  title: string; text: string; summary: string; entities: { type: string; value: string }[]
  threat_level: string | null; relevance: number | null
  first_seen: string | null; last_seen: string | null; last_scan: string | null
}
interface Query {
  id: number; query_text: string; query_hash: string; status: string; summary: string
  finding_count: number; error: string | null; last_run_at: string | null; run_count: number
  findings?: Finding[]
}

const THREAT: Record<string, string> = {
  critical: 'bg-[#d03b3b] text-white', high: 'bg-[#e8743b] text-white',
  medium: 'bg-[#fab219] text-[#3d2c00]', low: 'bg-grid text-inksec',
}

function timeAgo(iso: string | null): string {
  if (!iso) return '—'
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

export default function DarkWeb() {
  const [avail, setAvail] = useState<{ available: boolean; detail: any } | null>(null)
  const [q, setQ] = useState('')
  const [queries, setQueries] = useState<Query[]>([])
  const [active, setActive] = useState<Query | null>(null)
  const [running, setRunning] = useState(false)
  const [seeds, setSeeds] = useState('')
  const [showSeeds, setShowSeeds] = useState(false)
  const poll = useRef<any>(null)

  const loadQueries = () => get<Query[]>('/research/queries').then(setQueries).catch(() => {})
  useEffect(() => {
    get('/research/status').then(setAvail).catch(() => setAvail({ available: false, detail: null }))
    loadQueries()
    get<{ seeds: string[] }>('/research/seeds').then((r) => setSeeds((r.seeds || []).join('\n'))).catch(() => {})
    return () => clearInterval(poll.current)
  }, [])

  const openQuery = (id: number) => get<Query>(`/research/queries/${id}`).then(setActive)

  const run = async (force = false) => {
    if (!q.trim()) return
    setRunning(true)
    try {
      const r = await post<any>('/research/run', { query: q, max_sites: 5, max_steps: 8, force })
      if (r.cached && r.id) { await openQuery(r.id); setRunning(false); loadQueries(); return }
      // poll the query row until it leaves 'running'
      clearInterval(poll.current)
      poll.current = setInterval(async () => {
        await loadQueries()
        const row = (await get<Query[]>('/research/queries')).find((x) => x.query_hash === r.query_hash)
        if (row && row.status !== 'running') {
          clearInterval(poll.current); setRunning(false); openQuery(row.id)
        }
      }, 5000)
    } catch { setRunning(false) }
  }

  const saveSeeds = async () => {
    const list = seeds.split('\n').map((s) => s.trim()).filter(Boolean)
    await put('/research/seeds', { seeds: list })
    setShowSeeds(false)
  }

  return (
    <div className="space-y-5 max-w-5xl">
      <div>
        <div className="flex items-center gap-2">
          <IconShieldLock size={20} stroke={2} className="text-[#7c3aed]" />
          <h1 className="text-lg font-bold">Dark Web Research</h1>
          {avail && (
            <span className={`text-[11px] px-2 py-0.5 rounded-full ${avail.available ? 'bg-[#0ca30c]/10 text-[#006300]' : 'bg-[#d03b3b]/10 text-[#8c1c1c]'}`}>
              {avail.available ? 'Tor tier online' : 'tier offline'}
            </span>
          )}
        </div>
        <p className="text-sm text-muted mt-1">
          An AI agent (browser-use) researches <b>.onion</b> sites over Tor for a topic, then files
          findings into a permanent warehouse — so deleting a topic never loses the intel, and
          re-researching reuses what's already harvested. Passive observation only.
        </p>
      </div>

      {avail && !avail.available && (
        <div className="bg-[#fef2f2] border border-[#fecaca] rounded-xl p-3 text-sm text-[#991b1b]">
          The dark-web tier is off. Start it on the server with{' '}
          <code className="font-mono bg-white/60 px-1 rounded">docker compose --profile darkweb up -d</code>.
          You can still browse previously harvested findings below.
        </div>
      )}

      <div className="bg-white border border-grid rounded-2xl p-4">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex-1 flex items-center gap-2 border border-grid rounded-xl px-3">
            <IconSearch size={16} stroke={2} className="text-muted shrink-0" />
            <input value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && run(false)}
              placeholder="e.g. leaked credentials Malaysian banks, or a brand / domain / email"
              className="flex-1 py-2.5 text-sm outline-none bg-transparent" />
            {q && <button onClick={() => setQ('')} className="text-muted hover:text-ink"><IconX size={15} /></button>}
          </div>
          <button onClick={() => run(false)} disabled={running || !q.trim()}
            className="px-5 py-2.5 rounded-xl bg-ink text-white text-sm font-medium disabled:opacity-40 active:scale-[0.98]">
            {running ? 'Researching…' : 'Research'}
          </button>
          <button onClick={() => run(true)} disabled={running || !q.trim()} title="Ignore cache, re-crawl now"
            className="px-3 py-2.5 rounded-xl border border-grid text-sm text-inksec disabled:opacity-40">
            <IconRefresh size={15} stroke={2} />
          </button>
          <button onClick={() => setShowSeeds((s) => !s)}
            className="px-3 py-2.5 rounded-xl border border-grid text-sm text-inksec">Seeds</button>
        </div>
        {running && <div className="text-[12px] text-muted mt-2">Agent is browsing over Tor — this takes a few minutes per run.</div>}
        {showSeeds && (
          <div className="mt-3 border-t border-grid pt-3">
            <div className="text-[12px] font-medium mb-1">Seed .onion URLs (one per line)</div>
            <p className="text-[11px] text-muted mb-2">Always researched in addition to Ahmia discovery — your curated forums/leak sites.</p>
            <textarea rows={4} value={seeds} onChange={(e) => setSeeds(e.target.value)}
              placeholder="http://examplexxxx.onion/"
              className="w-full border border-grid rounded-lg px-3 py-2 font-mono text-[12px]" />
            <div className="flex justify-end mt-2"><button onClick={saveSeeds} className="px-4 py-1.5 rounded-lg bg-ink text-white text-sm">Save seeds</button></div>
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-[260px_1fr] gap-5">
        {/* query history (the warehouse cache) */}
        <div className="bg-white border border-grid rounded-2xl p-3 h-fit">
          <div className="text-xs font-semibold text-inksec mb-2 px-1">Researched queries</div>
          {queries.length === 0 && <div className="text-muted text-sm px-1 py-4">No research yet.</div>}
          {queries.map((qq) => (
            <button key={qq.id} onClick={() => openQuery(qq.id)}
              className={`w-full text-left px-2 py-2 rounded-lg mb-1 ${active?.id === qq.id ? 'bg-plane' : 'hover:bg-plane'}`}>
              <div className="text-[13px] font-medium truncate">{qq.query_text}</div>
              <div className="text-[11px] text-muted flex items-center gap-1.5">
                <span className={qq.status === 'running' ? 'text-[#b45309]' : qq.status === 'error' ? 'text-[#d03b3b]' : ''}>{qq.status}</span>
                · {qq.finding_count} findings · {timeAgo(qq.last_run_at)}
              </div>
            </button>
          ))}
        </div>

        {/* findings for the selected query */}
        <div className="min-w-0">
          {!active && <div className="text-muted text-sm py-16 text-center">Run a query or pick one on the left.</div>}
          {active && (
            <div className="space-y-3">
              <div className="bg-white border border-grid rounded-2xl p-4">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">{active.query_text}</h2>
                  <span className="ml-auto text-[11px] text-muted">run #{active.run_count} · {timeAgo(active.last_run_at)}</span>
                </div>
                {active.error && <div className="text-[12px] text-[#d03b3b] mt-1">{active.error}</div>}
                {active.summary && <p className="text-sm text-ink mt-2 whitespace-pre-wrap leading-snug">{active.summary}</p>}
              </div>
              {(active.findings || []).map((f) => (
                <div key={f.id} className="bg-white border border-grid rounded-2xl p-4">
                  <div className="flex items-center gap-2 flex-wrap">
                    <IconWorldWww size={15} stroke={2} className="text-muted" />
                    <span className="font-mono text-[12px] text-inksec truncate max-w-[60%]">{f.source_host || f.source_url}</span>
                    {f.threat_level && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold uppercase ${THREAT[f.threat_level] || 'bg-grid'}`}>{f.threat_level}</span>
                    )}
                    {f.relevance != null && <span className="text-[11px] text-muted">rel {f.relevance}</span>}
                    <span className="ml-auto text-[11px] text-muted" title={`first seen ${timeAgo(f.first_seen)}`}>seen {timeAgo(f.last_seen)}</span>
                  </div>
                  {f.title && <div className="font-medium text-[14px] mt-1.5">{f.title}</div>}
                  <p className="text-[13px] text-ink mt-1 whitespace-pre-wrap leading-snug line-clamp-6">{f.text}</p>
                  {f.entities?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {f.entities.slice(0, 12).map((e, i) => (
                        <span key={i} className="text-[11px] px-1.5 py-0.5 rounded bg-plane border border-grid font-mono">
                          <span className="text-muted">{e.type}:</span> {e.value}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {active.status === 'done' && (active.findings || []).length === 0 && (
                <div className="text-muted text-sm py-10 text-center flex flex-col items-center gap-2">
                  <IconAlertTriangle size={20} className="text-muted" />
                  No findings for this query in the sources checked.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
