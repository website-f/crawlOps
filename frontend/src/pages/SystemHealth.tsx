import {
  IconAlertTriangle, IconBolt, IconChartBar, IconCheck, IconPlugConnected,
  IconRepeat, IconSnowflake, IconWorld, IconX,
} from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { PlatformBadge } from '../components/PlatformIcon'
import { fmtNum, get } from '../lib/api'

interface Connector {
  id: number; platform: string; connector: string; tier: number
  enabled: boolean; status: string; cooling: boolean
  runs: number; errors: number; success_rate: number | null
  found: number; inserted: number
  p50_latency_s: number; p95_latency_s: number
  last_run_at: string | null; last_error: string | null
}
interface Proxy { id: number; url: string; tag: string; score: number; cooling: boolean; success: number; blocked: number }
interface AiUsage { provider: string; task: string; calls: number; prompt_tokens: number; completion_tokens: number }
interface Health {
  summary: {
    window_hours: number; sources_total: number; sources_enabled: number
    sources_cooling: number; sources_error: number; runs: number
    run_success_rate: number | null; enrichment_pending: number
    proxies_active: number; proxies_total: number
  }
  connectors: Connector[]
  backlog: Record<string, number>
  throughput: { posts_1h: number; posts_24h: number; total_posts: number }
  proxies: Proxy[]
  ai_usage: AiUsage[]
}

const STATUS_COLOR: Record<string, string> = { ok: '#0ca30c', idle: '#898781', dormant: '#fab219', error: '#d03b3b' }

function rateColor(r: number | null): string {
  if (r == null) return '#898781'
  if (r >= 90) return '#0ca30c'
  if (r >= 60) return '#fab219'
  return '#d03b3b'
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="bg-white border border-grid rounded-2xl p-4">
      <div className="text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div className="text-2xl font-bold mt-1 tabular-nums" style={{ color: tone }}>{value}</div>
      {sub && <div className="text-[11px] text-muted mt-0.5">{sub}</div>}
    </div>
  )
}

const BACKLOG_TONE: Record<string, string> = {
  done: '#0ca30c', pending: '#fab219', failed_llm: '#d03b3b', unknown: '#898781',
}

export default function SystemHealth() {
  const [data, setData] = useState<Health | null>(null)
  const [err, setErr] = useState('')
  const [tick, setTick] = useState(0)

  const reload = () => get<Health>('/system/crawl?hours=24').then((d) => { setData(d); setErr('') }).catch((e) => setErr(String(e)))
  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t) }, [])
  useEffect(() => { if (tick) reload() }, [tick])

  if (err) return <div className="text-sm text-[#d03b3b]">Failed to load crawl health: {err}</div>
  if (!data) return <div className="py-20 grid place-items-center text-muted">Loading…</div>

  const s = data.summary
  const backlogTotal = Object.values(data.backlog).reduce((a, b) => a + b, 0) || 1

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <IconBolt size={20} stroke={2} className="text-[#2a78d6]" />
        <h1 className="text-lg font-bold">Crawl Ops</h1>
        <span className="text-xs text-muted">last {s.window_hours}h · live</span>
        <button onClick={() => setTick((t) => t + 1)}
          className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-grid text-sm hover:bg-plane">
          <IconRepeat size={14} stroke={2} />Refresh
        </button>
      </div>

      {/* headline KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Kpi label="Run success" value={s.run_success_rate == null ? '—' : `${s.run_success_rate}%`}
          sub={`${s.runs} runs`} tone={rateColor(s.run_success_rate)} />
        <Kpi label="Sources live" value={`${s.sources_enabled}/${s.sources_total}`}
          sub={s.sources_error ? `${s.sources_error} in error` : 'all healthy'}
          tone={s.sources_error ? '#d03b3b' : undefined} />
        <Kpi label="Cooling" value={String(s.sources_cooling)} sub="circuit-broken"
          tone={s.sources_cooling ? '#fab219' : undefined} />
        <Kpi label="Enrich backlog" value={fmtNum(s.enrichment_pending)} sub="awaiting AI judge"
          tone={s.enrichment_pending > 500 ? '#fab219' : undefined} />
        <Kpi label="Throughput" value={fmtNum(data.throughput.posts_1h)} sub={`${fmtNum(data.throughput.posts_24h)} in 24h`} />
        <Kpi label="Proxies" value={`${s.proxies_active}/${s.proxies_total}`} sub="active in pool" />
      </div>

      {/* enrichment backlog bar */}
      <div className="bg-white border border-grid rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <IconChartBar size={16} stroke={2} className="text-inksec" />
          <span className="text-sm font-medium">Enrichment pipeline</span>
          <span className="ml-auto text-xs text-muted">{fmtNum(data.throughput.total_posts)} posts total</span>
        </div>
        <div className="flex h-3 rounded-full overflow-hidden bg-plane">
          {Object.entries(data.backlog).map(([k, v]) => (
            <div key={k} title={`${k}: ${v}`} style={{ width: `${(100 * v) / backlogTotal}%`, background: BACKLOG_TONE[k] || '#c9c7c1' }} />
          ))}
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
          {Object.entries(data.backlog).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
            <span key={k} className="inline-flex items-center gap-1.5 text-xs text-inksec">
              <span className="w-2 h-2 rounded-full" style={{ background: BACKLOG_TONE[k] || '#c9c7c1' }} />
              {k.replace('_', ' ')} <span className="tabular-nums font-medium">{fmtNum(v)}</span>
            </span>
          ))}
        </div>
      </div>

      {/* per-connector reliability */}
      <div className="bg-white border border-grid rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <IconPlugConnected size={16} stroke={2} className="text-inksec" />
          <span className="text-sm font-medium">Connector reliability</span>
          <span className="ml-auto text-xs text-muted">sorted by worst success rate</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead>
              <tr className="text-[11px] text-muted text-left border-b border-grid">
                <th className="font-normal py-1.5">connector</th>
                <th className="font-normal text-right">success</th>
                <th className="font-normal text-right">runs</th>
                <th className="font-normal text-right">found</th>
                <th className="font-normal text-right">new</th>
                <th className="font-normal text-right">p50</th>
                <th className="font-normal text-right">p95</th>
                <th className="font-normal">state</th>
              </tr>
            </thead>
            <tbody>
              {data.connectors.map((c) => (
                <tr key={c.id} className="border-b border-grid/50 align-top">
                  <td className="py-1.5">
                    <div className="flex items-center gap-2">
                      <PlatformBadge platform={c.platform} size={20} />
                      <span className="font-medium">{c.connector}</span>
                      <span className="text-[10px] px-1.5 rounded-full bg-grid text-inksec">t{c.tier}</span>
                    </div>
                    {c.last_error && <div className="text-[11px] text-[#b45309] mt-1 line-clamp-1 max-w-[22rem]">{c.last_error}</div>}
                  </td>
                  <td className="text-right tabular-nums font-medium" style={{ color: rateColor(c.success_rate) }}>
                    {c.success_rate == null ? '—' : `${c.success_rate}%`}
                  </td>
                  <td className="text-right tabular-nums text-inksec">{c.runs}{c.errors > 0 && <span className="text-[#d03b3b]"> ·{c.errors}✗</span>}</td>
                  <td className="text-right tabular-nums text-inksec">{fmtNum(c.found)}</td>
                  <td className="text-right tabular-nums font-medium">{fmtNum(c.inserted)}</td>
                  <td className="text-right tabular-nums text-muted">{c.p50_latency_s ? `${c.p50_latency_s}s` : '—'}</td>
                  <td className="text-right tabular-nums text-muted">{c.p95_latency_s ? `${c.p95_latency_s}s` : '—'}</td>
                  <td>
                    <span className="inline-flex items-center gap-1 text-xs" style={{ color: STATUS_COLOR[c.status] || '#898781' }}>
                      {c.cooling
                        ? <><IconSnowflake size={13} stroke={2} className="text-sky-500" /><span className="text-sky-600">cooling</span></>
                        : <><span className="w-1.5 h-1.5 rounded-full" style={{ background: STATUS_COLOR[c.status] || '#898781' }} />{c.enabled ? c.status : 'off'}</>}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* proxy pool */}
        <div className="bg-white border border-grid rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <IconWorld size={16} stroke={2} className="text-inksec" />
            <span className="text-sm font-medium">Proxy pool health</span>
          </div>
          {data.proxies.length === 0 ? (
            <div className="text-sm text-muted">No proxies configured — connectors fetch direct from this host's IP. Add residential proxies in Sources to spread load and dodge rate limits.</div>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {data.proxies.map((p) => (
                  <tr key={p.id} className="border-t border-grid/60">
                    <td className="py-1.5 font-mono text-xs truncate max-w-[11rem]">{p.url}</td>
                    <td className="text-xs text-muted">{p.tag}</td>
                    <td className="text-xs tabular-nums">
                      <span className="inline-flex items-center gap-1">score {Math.round(p.score)}
                        {p.cooling && <IconSnowflake size={12} stroke={2} className="text-sky-500" />}</span>
                    </td>
                    <td className="text-xs text-muted tabular-nums text-right">
                      <span className="inline-flex items-center gap-0.5">
                        {p.success}<IconCheck size={11} stroke={2.5} className="text-[#0ca30c]" />
                        {p.blocked}<IconX size={11} stroke={2.5} className="text-[#d03b3b]" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* AI usage */}
        <div className="bg-white border border-grid rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <IconBolt size={16} stroke={2} className="text-inksec" />
            <span className="text-sm font-medium">AI usage <span className="text-muted font-normal">(last {s.window_hours}h)</span></span>
          </div>
          {data.ai_usage.length === 0 ? (
            <div className="text-sm text-muted">No AI calls in this window. Enrichment stays <b>pending</b> until a provider is enabled in AI Engine.</div>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="text-[11px] text-muted text-left">
                <th className="font-normal">provider</th><th className="font-normal">task</th>
                <th className="font-normal text-right">calls</th><th className="font-normal text-right">tokens</th>
              </tr></thead>
              <tbody>
                {data.ai_usage.sort((a, b) => b.calls - a.calls).map((u, i) => (
                  <tr key={i} className="border-t border-grid/60">
                    <td className="py-1.5">{u.provider}</td>
                    <td className="text-xs text-muted">{u.task}</td>
                    <td className="text-right tabular-nums">{fmtNum(u.calls)}</td>
                    <td className="text-right tabular-nums text-muted">{fmtNum(u.prompt_tokens + u.completion_tokens)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {s.enrichment_pending > 0 && data.ai_usage.length === 0 && (
        <div className="flex items-start gap-2 bg-[#fef3c7] border border-[#fcd34d] rounded-xl p-3 text-sm text-[#92400e]">
          <IconAlertTriangle size={16} stroke={2} className="mt-0.5 shrink-0" />
          <span><b>{fmtNum(s.enrichment_pending)} posts</b> are crawled but unenriched, and no AI provider is serving the <code>judge</code> task.
            Sentiment, emotion, topics, stance and issues stay empty until you enable a provider in <b>AI Engine</b>.</span>
        </div>
      )}
    </div>
  )
}
