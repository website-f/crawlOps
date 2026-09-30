import {
  IconAlertTriangle, IconCheck, IconInfoCircle, IconKey, IconLogin2, IconPlugConnected,
  IconRss, IconSnowflake, IconUserCheck, IconUserOff, IconWorld, IconX,
} from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import LoginBrowser from '../components/LoginBrowser'
import { PlatformBadge } from '../components/PlatformIcon'
import { useDialog } from '../components/ui/overlays'
import { del, get, post, put } from '../lib/api'
import { BRAND } from '../lib/platform'

interface CredField {
  key: string; type: 'secret' | 'text' | 'list'; label: string; required?: boolean
  help?: string; placeholder?: string; set: boolean; hint?: string; value?: string | string[] | null
}

/** Connect dialog — fields come from the backend spec, so adding a connector never
 *  means editing this file. Secrets are write-only: stored encrypted, shown masked. */
function ConnectDialog({ source, onDone }: { source: Source; onDone: () => void }) {
  const [fields, setFields] = useState<CredField[]>([])
  const [vals, setVals] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    get<{ fields: CredField[] }>(`/sources/${source.id}/credentials`).then((r) => {
      setFields(r.fields)
      const v: Record<string, string> = {}
      r.fields.forEach((f) => {
        if (f.type === 'list') v[f.key] = Array.isArray(f.value) ? f.value.join('\n') : ''
        else if (f.type === 'text') v[f.key] = typeof f.value === 'string' ? f.value : ''
        else v[f.key] = ''                       // secrets always start blank
      })
      setVals(v)
    }).catch((e) => setErr(String(e)))
  }, [source.id])

  const save = async () => {
    setBusy(true); setErr('')
    try {
      await put(`/sources/${source.id}/credentials`, { values: vals })
      onDone()
    } catch (e: any) { setErr(e?.message || 'Could not save'); setBusy(false) }
  }

  const disconnect = async () => {
    setBusy(true)
    try { await del(`/sources/${source.id}/credentials`); onDone() }
    catch (e: any) { setErr(e?.message || 'Could not disconnect'); setBusy(false) }
  }

  const anyStored = fields.some((f) => f.set)
  return (
    <div className="fixed inset-0 z-[100] grid place-items-center p-4">
      <div className="absolute inset-0 bg-ink/45 backdrop-blur-[2px] animate-[fade_.15s_ease-out]" onClick={onDone} />
      <div className="relative bg-surface rounded-2xl border border-grid shadow-float w-full max-w-lg p-5 max-h-[85vh] overflow-y-auto animate-[pop_.16s_cubic-bezier(.16,1,.3,1)]">
        <div className="flex items-center gap-2 mb-1">
          <PlatformBadge platform={source.platform} size={22} />
          <h3 className="font-semibold capitalize">Connect {source.connector}</h3>
        </div>
        <p className="text-[13px] text-inksec mb-4">
          Stored in the database, encrypted — not in a config file. Leave a key blank to keep the stored one.
        </p>
        {fields.map((f) => (
          <label key={f.key} className="block text-sm mb-3">
            <span className="font-medium">{f.label}</span>
            {f.required && <span className="text-danger"> *</span>}
            {f.type === 'secret' && f.set && (
              <span className="ml-2 text-[11px] px-1.5 py-0.5 rounded-full bg-positive/10 text-positive">
                stored {f.hint}
              </span>
            )}
            {f.type === 'list' ? (
              <textarea rows={4} value={vals[f.key] || ''} placeholder={f.placeholder}
                onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}
                className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px] focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
            ) : (
              <input type={f.type === 'secret' ? 'password' : 'text'} value={vals[f.key] || ''}
                placeholder={f.type === 'secret' && f.set ? '•••••• (unchanged)' : f.placeholder}
                autoComplete="off"
                onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}
                className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px] focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
            )}
            {f.help && <span className="block text-[11px] text-muted mt-1">{f.help}</span>}
          </label>
        ))}
        {err && <div className="text-[12px] text-danger mb-2">{err}</div>}
        <div className="flex gap-2 justify-end items-center">
          {anyStored && (
            <button onClick={disconnect} disabled={busy}
              className="mr-auto text-xs text-danger hover:underline">Disconnect</button>
          )}
          <button onClick={onDone} className="px-4 py-1.5 text-sm text-inksec hover:bg-plane rounded-lg transition">Cancel</button>
          <button onClick={save} disabled={busy}
            className="px-4 py-1.5 rounded-lg bg-accent text-white text-sm font-medium disabled:opacity-50 hover:brightness-110 transition">
            {busy ? 'Saving…' : 'Connect'}
          </button>
        </div>
      </div>
    </div>
  )
}

interface AccountState { connected: boolean; state: 'none' | 'ready' | 'needs_reauth' | 'resting'; label?: string; detail: string }
interface Source {
  id: number; platform: string; connector: string; tier: number; enabled: boolean
  status: string; last_run_at: string | null; last_error: string
  needs_credentials: boolean; missing: string[]; configured: boolean
  method: string; blurb: string
  account?: AccountState
}
interface Run { id: number; topic_id: number; source_id: number; started_at: string; found: number; inserted: number; error: string }
interface Proxy { id: number; url: string; tag: string; country: string; score: number; cooling: boolean; success: number; blocked: number }
interface Session { id: number; platform: string; label: string; status: string; has_cookies: boolean; daily_used: number; daily_cap: number; last_used_at: string | null }

const METHOD_BADGE: Record<string, { label: string; cls: string }> = {
  login: { label: 'Login', cls: 'bg-accent/10 text-accent-ink' },
  api: { label: 'API key', cls: 'bg-accent/10 text-accent-ink' },
  watchlist: { label: 'Watchlist · free', cls: 'bg-positive/10 text-positive' },
  config: { label: 'Setup', cls: 'bg-[#fab219]/15 text-[#7a5200]' },
  keyless: { label: 'Keyless', cls: 'bg-grid text-inksec' },
}
const STATUS_COLOR: Record<string, string> = { ok: '#0ca30c', idle: '#898781', dormant: '#fab219', error: '#d03b3b' }

// social platforms get one combined multi-method card; everything else is a compact row
const SOCIAL = ['facebook', 'instagram', 'tiktok', 'x', 'threads', 'youtube']
const LOGIN_PLATFORMS = ['facebook', 'instagram', 'tiktok', 'x', 'threads']

type Tone = 'ok' | 'warn' | 'off'
function loginState(s?: Session): 'none' | 'ready' | 'needs_reauth' | 'resting' {
  if (!s || !s.has_cookies) return 'none'
  if (s.status === 'needs_reauth') return 'needs_reauth'
  if (s.status === 'resting') return 'resting'
  return 'ready'
}

function MethodRow({ Icon, title, desc, tone, stateLabel, actionLabel, onAction, enabled, onToggle }: {
  Icon: any; title: string; desc: string; tone: Tone; stateLabel: string
  actionLabel: string; onAction: () => void; enabled?: boolean; onToggle?: () => void
}) {
  const chip = tone === 'ok' ? 'bg-positive/10 text-positive'
    : tone === 'warn' ? 'bg-[#fab219]/15 text-[#7a5200]' : 'bg-grid text-inksec'
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-grid bg-plane/50 px-2.5 py-2">
      <span className="w-8 h-8 rounded-lg bg-surface border border-grid grid place-items-center shrink-0 text-inksec"><Icon size={16} stroke={2} /></span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[13px] font-semibold text-ink">{title}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${chip}`}>{stateLabel}</span>
        </div>
        <div className="text-[11px] text-muted leading-snug line-clamp-1">{desc}</div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {onToggle && (
          <button onClick={onToggle} title={enabled ? 'Crawling on' : 'Crawling off'}
            className={`text-[10px] px-2 py-1 rounded-lg border transition ${enabled ? 'bg-ink text-white border-ink' : 'bg-surface border-grid text-muted hover:text-ink'}`}>
            {enabled ? 'on' : 'off'}
          </button>
        )}
        <button onClick={onAction}
          className="text-[12px] font-medium px-2.5 py-1.5 rounded-lg border border-accent/40 text-accent-ink bg-accent/5 hover:bg-accent/10 transition active:scale-[0.97] whitespace-nowrap">
          {actionLabel}
        </button>
      </div>
    </div>
  )
}

function PlatformCard({ platform, rows, session, onLogin, onConnect, onToggle }: {
  platform: string; rows: Source[]; session?: Session
  onLogin: (p: string) => void; onConnect: (s: Source) => void; onToggle: (id: number) => void
}) {
  const apiSource = rows.find((s) => s.method === 'api')
  const watchSource = rows.find((s) => s.method === 'watchlist')
  const loginSource = rows.find((s) => !!s.account)   // *_stealth row (fb/ig/tiktok/x)
  const canLogin = LOGIN_PLATFORMS.includes(platform)
  const ls = loginState(session)

  const methods = [canLogin && 'Login', apiSource && 'API', watchSource && 'Watchlist'].filter(Boolean).join(' · ')
  const connected = ls === 'ready' || !!apiSource?.configured || !!watchSource?.configured
  const anyEnabled = rows.some((s) => s.enabled)

  return (
    <div className="bg-surface border border-grid rounded-2xl p-4 flex flex-col gap-3 shadow-card">
      <div className="flex items-center gap-2.5">
        <PlatformBadge platform={platform} size={30} />
        <div className="min-w-0">
          <div className="font-semibold text-[15px] capitalize leading-tight">{BRAND[platform]?.label || platform}</div>
          <div className="text-[11px] text-muted">{methods || 'no methods'}</div>
        </div>
        <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-medium"
          style={{ color: connected && anyEnabled ? '#0a7d0a' : '#898781' }}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: connected && anyEnabled ? '#0ca30c' : '#c9c7bf' }} />
          {connected ? (anyEnabled ? 'active' : 'paused') : 'not set up'}
        </span>
      </div>

      <div className="space-y-2">
        {canLogin && (
          <MethodRow Icon={IconLogin2} title="Log in"
            desc="Opens a real browser on the crawler's IP; captures the session."
            tone={ls === 'ready' ? 'ok' : ls === 'none' ? 'off' : 'warn'}
            stateLabel={ls === 'ready' ? 'connected' : ls === 'needs_reauth' ? 're-login needed' : ls === 'resting' ? 'daily cap' : 'not connected'}
            actionLabel={ls === 'none' ? 'Log in' : 'Reconnect'} onAction={() => onLogin(platform)}
            enabled={loginSource?.enabled} onToggle={loginSource ? () => onToggle(loginSource.id) : undefined} />
        )}
        {apiSource && (
          <MethodRow Icon={IconKey} title="API key" desc={apiSource.blurb}
            tone={apiSource.configured ? 'ok' : 'off'}
            stateLabel={apiSource.configured ? 'connected' : 'no key'}
            actionLabel={apiSource.configured ? 'Edit key' : 'Add API key'} onAction={() => onConnect(apiSource)}
            enabled={apiSource.enabled} onToggle={() => onToggle(apiSource.id)} />
        )}
        {watchSource && (
          <MethodRow Icon={IconRss} title="Watchlist" desc={watchSource.blurb}
            tone={watchSource.configured ? 'ok' : 'off'}
            stateLabel={watchSource.configured ? 'following' : 'free · add accounts'}
            actionLabel={watchSource.configured ? 'Edit accounts' : 'Add watchlist'} onAction={() => onConnect(watchSource)}
            enabled={watchSource.enabled} onToggle={() => onToggle(watchSource.id)} />
        )}
      </div>
    </div>
  )
}

export default function Sources() {
  const dialog = useDialog()
  const [sources, setSources] = useState<Source[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [proxies, setProxies] = useState<Proxy[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [proxyUrl, setProxyUrl] = useState('')
  const [proxyTag, setProxyTag] = useState('residential')
  const [connecting, setConnecting] = useState<Source | null>(null)
  const [sessPlatform, setSessPlatform] = useState('facebook')
  const [cookieTarget, setCookieTarget] = useState<number | null>(null)
  const [cookieJson, setCookieJson] = useState('')
  const [loginPlatform, setLoginPlatform] = useState<string | null>(null)
  const [showSessions, setShowSessions] = useState(false)

  const reload = () => {
    get<Source[]>('/sources').then(setSources)
    get<Run[]>('/sources/runs?limit=30').then(setRuns)
    get<Proxy[]>('/sources/proxies').then(setProxies).catch(() => {})
    get<Session[]>('/sources/stealth-sessions').then(setSessions).catch(() => {})
  }
  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t) }, [])

  const toggle = (id: number) => post(`/sources/${id}/toggle`).then(reload)
  const bestSession = (p: string) => sessions.filter((s) => s.platform === p)
    .sort((a, b) => (b.has_cookies ? 1 : 0) - (a.has_cookies ? 1 : 0))[0]

  const socialRows = SOCIAL.map((p) => ({ platform: p, rows: sources.filter((s) => s.platform === p) }))
    .filter((g) => g.rows.length > 0 || LOGIN_PLATFORMS.includes(g.platform))
  const otherSources = sources.filter((s) => !SOCIAL.includes(s.platform))
    .sort((a, b) => (a.needs_credentials === b.needs_credentials ? a.platform.localeCompare(b.platform) : a.needs_credentials ? -1 : 1))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold tracking-tight">Sources</h1>
        <p className="text-[13px] text-inksec mt-0.5 max-w-2xl">
          Each social network has up to three ways to connect — pick any or combine them for richer coverage.
          Keyless news, community and research sources need nothing. Pause a topic's non-stop crawling with the
          <b className="text-ink"> Auto-run</b> toggle on <b className="text-ink">Topics</b>.
        </p>
        <div className="flex flex-wrap gap-3 mt-3 text-[12px]">
          <span className="inline-flex items-center gap-1.5 text-inksec"><IconLogin2 size={14} stroke={2} className="text-accent" /> <b className="text-ink">Log in</b> — real window, auto-captured session</span>
          <span className="inline-flex items-center gap-1.5 text-inksec"><IconKey size={14} stroke={2} className="text-accent" /> <b className="text-ink">API key</b> — official token</span>
          <span className="inline-flex items-center gap-1.5 text-inksec"><IconRss size={14} stroke={2} className="text-positive" /> <b className="text-ink">Watchlist</b> — free, follow public accounts</span>
        </div>
      </div>

      {/* --- Social networks: one combined card per platform --- */}
      <section>
        <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted mb-2.5">Social networks</div>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3.5">
          {socialRows.map((g) => (
            <PlatformCard key={g.platform} platform={g.platform} rows={g.rows} session={bestSession(g.platform)}
              onLogin={setLoginPlatform} onConnect={setConnecting} onToggle={toggle} />
          ))}
        </div>
      </section>

      {/* --- Everything else: compact rows --- */}
      <section>
        <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.09em] text-muted mb-2.5">
          <IconWorld size={13} stroke={2} /> News, communities &amp; research
        </div>
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-2.5">
          {otherSources.map((s) => {
            const badge = METHOD_BADGE[s.method] || METHOD_BADGE.keyless
            return (
              <div key={s.id} className="flex items-center gap-2.5 border border-grid rounded-xl bg-surface px-3 py-2.5 shadow-card">
                <PlatformBadge platform={s.platform} size={22} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[13px] font-medium truncate">{s.connector}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${badge.cls}`}>{badge.label}</span>
                  </div>
                  <div className="text-[11px] text-muted truncate">
                    {s.needs_credentials && !s.configured && s.missing?.length ? `needs: ${s.missing.join(', ')}` : s.blurb}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {s.needs_credentials && (
                    <button onClick={() => setConnecting(s)} title="Configure"
                      className="p-1.5 rounded-lg border border-grid text-inksec hover:text-accent-ink hover:border-accent/40 transition">
                      <IconPlugConnected size={15} stroke={2} />
                    </button>
                  )}
                  <button onClick={() => toggle(s.id)}
                    className={`text-[10px] px-2 py-1 rounded-lg border transition ${s.enabled ? 'bg-ink text-white border-ink' : 'bg-surface border-grid text-muted hover:text-ink'}`}>
                    {s.enabled ? 'on' : 'off'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* --- Proxy pool + runs --- */}
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="bg-surface border border-grid rounded-2xl p-4 shadow-card">
          <div className="text-sm font-semibold mb-0.5">Proxy pool</div>
          <div className="text-[11px] text-muted mb-3">Health-scored rotation; the login tier needs residential IPs.</div>
          <div className="flex gap-2 mb-3">
            <input value={proxyUrl} onChange={(e) => setProxyUrl(e.target.value)}
              placeholder="http://user:pass@host:port" className="flex-1 border border-grid rounded-lg px-2.5 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
            <select value={proxyTag} onChange={(e) => setProxyTag(e.target.value)} className="border border-grid rounded-lg px-2 text-sm bg-white">
              <option value="residential">residential</option><option value="datacenter">datacenter</option>
            </select>
            <button onClick={() => post('/sources/proxies', { url: proxyUrl, tag: proxyTag }).then(() => { setProxyUrl(''); reload() })}
              className="px-3 py-1.5 rounded-lg bg-ink text-white text-sm hover:brightness-110 transition">Add</button>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {proxies.map((p) => (
                <tr key={p.id} className="border-t border-grid/60">
                  <td className="py-1.5 font-mono text-xs truncate max-w-[10rem]">{p.url}</td>
                  <td className="text-xs text-muted">{p.tag}</td>
                  <td className="text-xs tabular-nums">
                    <span className="inline-flex items-center gap-1">score {Math.round(p.score)}
                      {p.cooling && <IconSnowflake size={12} stroke={2} className="text-accent" />}</span>
                  </td>
                  <td className="text-xs text-muted tabular-nums">
                    <span className="inline-flex items-center gap-0.5">{p.success}<IconCheck size={11} stroke={2.5} className="text-positive" />
                      {p.blocked}<IconX size={11} stroke={2.5} className="text-danger" /></span>
                  </td>
                  <td className="text-right"><button onClick={() => del(`/sources/proxies/${p.id}`).then(reload)} className="text-xs text-danger hover:underline">remove</button></td>
                </tr>
              ))}
              {proxies.length === 0 && <tr><td className="text-muted text-sm py-2">No proxies yet. Tier 1/2 run direct; the login tier stays off until you add residential IPs.</td></tr>}
            </tbody>
          </table>

          <button onClick={() => setShowSessions((v) => !v)}
            className="mt-4 text-[12px] font-medium text-inksec hover:text-ink transition">
            {showSessions ? '▾' : '▸'} Advanced · stealth sessions ({sessions.length})
          </button>
          {showSessions && (
            <div className="mt-2">
              <div className="text-[11px] text-muted mb-2">Logging in above creates these automatically. Cookie paste is a fallback for headless setups.</div>
              <div className="flex gap-2 mb-2 flex-wrap">
                <select value={sessPlatform} onChange={(e) => setSessPlatform(e.target.value)} className="border border-grid rounded-lg px-2 py-1.5 text-sm bg-white">
                  {LOGIN_PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <button onClick={() => post('/sources/stealth-sessions', { platform: sessPlatform, label: `${sessPlatform} account` }).then(reload)}
                  className="px-3 py-1.5 rounded-lg border border-grid text-sm hover:bg-plane transition">Empty session</button>
              </div>
              {sessions.map((s) => {
                const sc = s.status === 'needs_reauth' ? 'text-danger' : s.status === 'resting' ? 'text-[#b45309]' : 'text-muted'
                return (
                  <div key={s.id} className="flex items-center gap-2 text-sm border-t border-grid/60 py-1.5">
                    <span className="capitalize">{s.platform}</span>
                    <span className={`text-[10px] px-1.5 rounded-full ${s.has_cookies ? 'bg-positive/10 text-positive' : 'bg-grid text-inksec'}`}>{s.has_cookies ? 'cookies set' : 'no cookies'}</span>
                    <span className={`ml-auto text-xs ${sc}`}>{s.status} · {s.daily_used}/{s.daily_cap}</span>
                    <button onClick={() => { setCookieTarget(s.id); setCookieJson('') }} className="text-xs text-accent hover:underline">cookies</button>
                    <button onClick={() => del(`/sources/stealth-sessions/${s.id}`).then(reload)} className="text-xs text-danger hover:underline">del</button>
                  </div>
                )
              })}
              {sessions.length === 0 && <div className="text-muted text-sm">No sessions yet.</div>}
            </div>
          )}
        </div>

        <div className="bg-surface border border-grid rounded-2xl p-4 shadow-card">
          <div className="text-sm font-semibold mb-2">Recent fetch runs</div>
          <table className="w-full text-sm">
            <thead><tr className="text-xs text-muted text-left">
              <th className="font-normal">when</th><th className="font-normal">source</th>
              <th className="font-normal text-right">found</th><th className="font-normal text-right">new</th>
            </tr></thead>
            <tbody>
              {runs.map((r) => {
                const src = sources.find((s) => s.id === r.source_id)
                return (
                  <tr key={r.id} className="border-t border-grid/60">
                    <td className="py-1 text-xs text-muted">{new Date(r.started_at).toLocaleTimeString()}</td>
                    <td className="text-xs">
                      <span className="inline-flex items-center gap-1">{src?.connector || r.source_id}
                        {r.error && <IconAlertTriangle size={12} stroke={2} className="text-danger" />}</span>
                    </td>
                    <td className="text-right tabular-nums">{r.found}</td>
                    <td className="text-right tabular-nums font-medium">{r.inserted}</td>
                  </tr>
                )
              })}
              {runs.length === 0 && <tr><td colSpan={4} className="text-muted text-sm py-2">No runs yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {connecting && <ConnectDialog source={connecting} onDone={() => { setConnecting(null); reload() }} />}

      {loginPlatform && (
        <LoginBrowser platform={loginPlatform}
          onClose={() => setLoginPlatform(null)}
          onDone={() => { setLoginPlatform(null); reload() }} />
      )}

      {cookieTarget !== null && (
        <div className="fixed inset-0 z-[100] grid place-items-center p-4">
          <div className="absolute inset-0 bg-ink/45 backdrop-blur-[2px] animate-[fade_.15s_ease-out]" onClick={() => setCookieTarget(null)} />
          <div className="relative bg-surface rounded-2xl border border-grid shadow-float w-full max-w-lg p-5 animate-[pop_.16s_cubic-bezier(.16,1,.3,1)]">
            <h3 className="font-semibold mb-1">Import session cookies</h3>
            <p className="text-sm text-inksec mb-3">
              Paste the account's cookies as a JSON array (export with a cookie-editor extension).
              They are pushed into camofox under this session's sticky identity.
            </p>
            <textarea rows={7} value={cookieJson} onChange={(e) => setCookieJson(e.target.value)}
              placeholder='[{"name":"c_user","value":"...","domain":".facebook.com"}, ...]'
              className="w-full border border-grid rounded-lg px-3 py-2 font-mono text-[12px] focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
            <div className="flex gap-2 justify-end mt-3">
              <button onClick={() => setCookieTarget(null)} className="px-4 py-1.5 text-sm text-inksec hover:bg-plane rounded-lg transition">Cancel</button>
              <button onClick={async () => {
                try {
                  const cookies = JSON.parse(cookieJson)
                  await post(`/sources/stealth-sessions/${cookieTarget}/cookies`, { cookies })
                  setCookieTarget(null); reload(); dialog.toast('Cookies imported', 'success')
                } catch { dialog.toast('Invalid JSON, or camofox is not running (start with --profile stealth)', 'error') }
              }} className="px-4 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:brightness-110 transition">Import</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
