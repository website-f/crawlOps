import { IconAlertTriangle, IconCheck, IconLogin2, IconSettings, IconSnowflake, IconX } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import LoginBrowser from '../components/LoginBrowser'
import { PlatformBadge } from '../components/PlatformIcon'
import { del, get, post, put } from '../lib/api'

const CONFIGURABLE: Record<string, { field: string; label: string; placeholder: string }[]> = {
  rss: [
    { field: 'feeds', label: 'RSS/Atom feed URLs (one per line)', placeholder: 'https://techcrunch.com/feed/' },
    { field: 'rsshub_routes', label: 'RSSHub routes (one per line)', placeholder: '/twitter/user/elonmusk' },
  ],
  telegram: [
    { field: 'channels', label: 'Public channel usernames (one per line)', placeholder: 'durov' },
  ],
}

function ConfigEditor({ sourceId, connector, onDone }: { sourceId: number; connector: string; onDone: () => void }) {
  const fields = CONFIGURABLE[connector]
  const [cfg, setCfg] = useState<Record<string, string>>({})
  useEffect(() => {
    get<{ config: any }>(`/sources/${sourceId}/config`).then((r) => {
      const c: Record<string, string> = {}
      fields.forEach((f) => { c[f.field] = (r.config?.[f.field] || []).join('\n') })
      setCfg(c)
    })
  }, [sourceId])

  const save = async () => {
    const config: any = {}
    fields.forEach((f) => {
      config[f.field] = (cfg[f.field] || '').split('\n').map((x) => x.trim()).filter(Boolean)
    })
    await put(`/sources/${sourceId}/config`, { config })
    onDone()
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div className="absolute inset-0 bg-ink/30" onClick={onDone} />
      <div className="relative bg-white rounded-2xl border border-grid shadow-xl w-full max-w-lg p-5">
        <h3 className="font-semibold mb-3 capitalize">Configure {connector}</h3>
        {fields.map((f) => (
          <label key={f.field} className="block text-sm mb-3">{f.label}
            <textarea rows={4} value={cfg[f.field] || ''} placeholder={f.placeholder}
              onChange={(e) => setCfg({ ...cfg, [f.field]: e.target.value })}
              className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px]" />
          </label>
        ))}
        <div className="flex gap-2 justify-end">
          <button onClick={onDone} className="px-4 py-1.5 text-sm text-inksec">Cancel</button>
          <button onClick={save} className="px-4 py-1.5 rounded-lg bg-ink text-white text-sm">Save & enable</button>
        </div>
      </div>
    </div>
  )
}

interface Source { id: number; platform: string; connector: string; tier: number; enabled: boolean; status: string; last_run_at: string | null; last_error: string }
interface Run { id: number; topic_id: number; source_id: number; started_at: string; found: number; inserted: number; error: string }
interface Proxy { id: number; url: string; tag: string; country: string; score: number; cooling: boolean; success: number; blocked: number }

const STATUS_COLOR: Record<string, string> = { ok: '#0ca30c', idle: '#898781', dormant: '#fab219', error: '#d03b3b' }

export default function Sources() {
  const [sources, setSources] = useState<Source[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [proxies, setProxies] = useState<Proxy[]>([])
  const [sessions, setSessions] = useState<any[]>([])
  const [proxyUrl, setProxyUrl] = useState('')
  const [proxyTag, setProxyTag] = useState('residential')
  const [editing, setEditing] = useState<{ id: number; connector: string } | null>(null)
  const [sessPlatform, setSessPlatform] = useState('facebook')
  const [cookieTarget, setCookieTarget] = useState<number | null>(null)
  const [cookieJson, setCookieJson] = useState('')
  const [loginPlatform, setLoginPlatform] = useState<string | null>(null)

  const reload = () => {
    get<Source[]>('/sources').then(setSources)
    get<Run[]>('/sources/runs?limit=30').then(setRuns)
    get<Proxy[]>('/sources/proxies').then(setProxies).catch(() => {})
    get('/sources/stealth-sessions').then(setSessions).catch(() => {})
  }
  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t) }, [])

  return (
    <div className="space-y-5">
      <div className="bg-white border border-grid rounded-2xl p-4">
        <div className="text-sm font-medium mb-3">Connectors</div>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {sources.map((s) => {
            return (
              <div key={s.id} className="border border-grid rounded-xl p-3">
                <div className="flex items-center gap-2">
                  <PlatformBadge platform={s.platform} size={24} />
                  <span className="font-medium text-sm">{s.connector}</span>
                  <span className="text-[10px] px-1.5 rounded-full bg-grid text-inksec">tier {s.tier}</span>
                  <span className="ml-auto inline-flex items-center gap-1 text-xs" style={{ color: STATUS_COLOR[s.status] }}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: STATUS_COLOR[s.status] }} />{s.status}
                  </span>
                </div>
                {s.last_error && <div className="text-[11px] text-[#b45309] mt-1.5 line-clamp-2">{s.last_error}</div>}
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[11px] text-muted">
                    {s.last_run_at ? `ran ${new Date(s.last_run_at).toLocaleTimeString()}` : 'never ran'}
                  </span>
                  <div className="flex items-center gap-2">
                    {CONFIGURABLE[s.connector] && (
                      <button onClick={() => setEditing({ id: s.id, connector: s.connector })}
                        className="inline-flex items-center gap-1 text-xs text-inksec hover:text-ink">
                        <IconSettings size={13} stroke={2} />configure
                      </button>
                    )}
                    <button onClick={() => post(`/sources/${s.id}/toggle`).then(reload)}
                      className={`text-xs px-2.5 py-1 rounded-lg border ${s.enabled ? 'bg-ink text-white border-ink' : 'bg-white border-grid text-inksec'}`}>
                      {s.enabled ? 'enabled' : 'disabled'}
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <div className="bg-white border border-grid rounded-2xl p-4">
          <div className="text-sm font-medium mb-2">Proxy pool <span className="text-muted font-normal">(health-scored rotation; stealth tier needs residential)</span></div>
          <div className="flex gap-2 mb-3">
            <input value={proxyUrl} onChange={(e) => setProxyUrl(e.target.value)}
              placeholder="http://user:pass@host:port" className="flex-1 border border-grid rounded-lg px-2.5 py-1.5 text-sm font-mono" />
            <select value={proxyTag} onChange={(e) => setProxyTag(e.target.value)} className="border border-grid rounded-lg px-2 text-sm">
              <option value="residential">residential</option><option value="datacenter">datacenter</option>
            </select>
            <button onClick={() => post('/sources/proxies', { url: proxyUrl, tag: proxyTag }).then(() => { setProxyUrl(''); reload() })}
              className="px-3 py-1.5 rounded-lg bg-ink text-white text-sm">Add</button>
          </div>
          <table className="w-full text-sm">
            <tbody>
              {proxies.map((p) => (
                <tr key={p.id} className="border-t border-grid/60">
                  <td className="py-1.5 font-mono text-xs truncate max-w-[10rem]">{p.url}</td>
                  <td className="text-xs text-muted">{p.tag}</td>
                  <td className="text-xs tabular-nums">
                    <span className="inline-flex items-center gap-1">
                      score {Math.round(p.score)}
                      {p.cooling && <IconSnowflake size={12} stroke={2} className="text-sky-500" />}
                    </span>
                  </td>
                  <td className="text-xs text-muted tabular-nums">
                    <span className="inline-flex items-center gap-0.5">
                      {p.success}<IconCheck size={11} stroke={2.5} className="text-[#0ca30c]" />
                      {p.blocked}<IconX size={11} stroke={2.5} className="text-[#d03b3b]" />
                    </span>
                  </td>
                  <td className="text-right"><button onClick={() => del(`/sources/proxies/${p.id}`).then(reload)} className="text-xs text-red-700">remove</button></td>
                </tr>
              ))}
              {proxies.length === 0 && <tr><td className="text-muted text-sm py-2">No proxies yet. Tier 1/2 run direct; the stealth tier stays off.</td></tr>}
            </tbody>
          </table>

          <div className="text-sm font-medium mt-4 mb-2">Stealth sessions <span className="text-muted font-normal">(one per platform account; import cookies to go live)</span></div>
          <div className="flex gap-2 mb-2 flex-wrap">
            <select value={sessPlatform} onChange={(e) => setSessPlatform(e.target.value)}
              className="border border-grid rounded-lg px-2 py-1.5 text-sm">
              {['facebook', 'instagram', 'tiktok', 'x', 'threads'].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <button onClick={() => setLoginPlatform(sessPlatform)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2a78d6] text-white text-sm active:scale-[0.98]">
              <IconLogin2 size={15} stroke={2} />Log in here
            </button>
            <button onClick={() => post('/sources/stealth-sessions', { platform: sessPlatform, label: `${sessPlatform} account` }).then(reload)}
              className="px-3 py-1.5 rounded-lg border border-grid text-sm">Empty session</button>
          </div>
          {sessions.map((s: any) => {
            const statusColor = s.status === 'needs_reauth' ? 'text-[#d03b3b]'
              : s.status === 'resting' ? 'text-[#b45309]' : 'text-muted'
            return (
              <div key={s.id} className="flex items-center gap-2 text-sm border-t border-grid/60 py-1.5">
                <span className="capitalize">{s.platform}</span>
                <span className={`text-[10px] px-1.5 rounded-full ${s.has_cookies ? 'bg-[#0ca30c]/10 text-[#006300]' : 'bg-grid text-inksec'}`}>
                  {s.has_cookies ? 'cookies set' : 'no cookies'}
                </span>
                <span className={`ml-auto text-xs ${statusColor}`}>{s.status} · {s.daily_used}/{s.daily_cap}</span>
                <button onClick={() => { setCookieTarget(s.id); setCookieJson('') }} className="text-xs text-[#2a78d6]">cookies</button>
                <button onClick={() => del(`/sources/stealth-sessions/${s.id}`).then(reload)} className="text-xs text-red-700">del</button>
              </div>
            )
          })}
          {sessions.length === 0 && <div className="text-muted text-sm">No stealth sessions yet. Add one, import its account cookies, and run the stealth profile.</div>}
        </div>

        <div className="bg-white border border-grid rounded-2xl p-4">
          <div className="text-sm font-medium mb-2">Recent fetch runs</div>
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
                      <span className="inline-flex items-center gap-1">
                        {src?.connector || r.source_id}
                        {r.error && <IconAlertTriangle size={12} stroke={2} className="text-[#d03b3b]" />}
                      </span>
                    </td>
                    <td className="text-right tabular-nums">{r.found}</td>
                    <td className="text-right tabular-nums font-medium">{r.inserted}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {editing && (
        <ConfigEditor sourceId={editing.id} connector={editing.connector}
          onDone={() => { setEditing(null); reload() }} />
      )}

      {loginPlatform && (
        <LoginBrowser platform={loginPlatform}
          onClose={() => setLoginPlatform(null)}
          onDone={() => { setLoginPlatform(null); reload() }} />
      )}

      {cookieTarget !== null && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setCookieTarget(null)} />
          <div className="relative bg-white rounded-2xl border border-grid shadow-xl w-full max-w-lg p-5">
            <h3 className="font-semibold mb-1">Import session cookies</h3>
            <p className="text-sm text-inksec mb-3">
              Paste the account's cookies as a JSON array (export with a cookie-editor extension).
              They are pushed into camofox under this session's sticky identity.
            </p>
            <textarea rows={7} value={cookieJson} onChange={(e) => setCookieJson(e.target.value)}
              placeholder='[{"name":"c_user","value":"...","domain":".facebook.com"}, ...]'
              className="w-full border border-grid rounded-lg px-3 py-2 font-mono text-[12px]" />
            <div className="flex gap-2 justify-end mt-3">
              <button onClick={() => setCookieTarget(null)} className="px-4 py-1.5 text-sm text-inksec">Cancel</button>
              <button onClick={async () => {
                try {
                  const cookies = JSON.parse(cookieJson)
                  await post(`/sources/stealth-sessions/${cookieTarget}/cookies`, { cookies })
                  setCookieTarget(null); reload()
                } catch { alert('Invalid JSON or camofox not running (start with --profile stealth)') }
              }} className="px-4 py-1.5 rounded-lg bg-ink text-white text-sm">Import</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
