import { IconCopy, IconDeviceFloppy, IconDownload, IconPuzzle, IconSend, IconTrash, IconUserPlus, IconX } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { MultiSelect, TagInput } from '../components/ui/controls'
import { useDialog } from '../components/ui/overlays'
import { del, download, get, getToken, post, put } from '../lib/api'
import { BRAND, FEED_TABS } from '../lib/platform'

const PLATFORM_OPTS = FEED_TABS.filter((t) => t !== 'all').map((p) => ({ value: p, label: BRAND[p]?.label || p, color: BRAND[p]?.color }))

interface AllSettings {
  cpm: Record<string, number>
  notifiers: { webhook_url: string; telegram_bot_token: string; telegram_chat_id: string }
  pipeline: { default_threshold: number; retention_days: number }
  issues: { list: string[] }
  digest: { enabled: boolean; frequency: string; hour: number; topic_id: number | null; include_brief: boolean }
}

interface AppUser { id: number; username: string; role: string }

export default function Settings() {
  const dialog = useDialog()
  const [s, setS] = useState<AllSettings | null>(null)
  const [saved, setSaved] = useState('')
  const [testResult, setTestResult] = useState('')
  const [users, setUsers] = useState<AppUser[] | null>(null)
  const [nu, setNu] = useState({ username: '', password: '', role: 'analyst' })
  const [sc, setSc] = useState<any>(null)
  const [recomputing, setRecomputing] = useState('')
  const [topicsList, setTopicsList] = useState<{ id: number; name: string }[]>([])
  const [digestResult, setDigestResult] = useState('')

  useEffect(() => {
    get<AllSettings>('/settings').then(setS)
    get('/scoring').then(setSc).catch(() => {})
    get('/topics').then(setTopicsList).catch(() => {})
    get<AppUser[]>('/auth/users').then(setUsers).catch(() => setUsers(null)) // 403 for non-admins
  }, [])

  const sendDigestNow = async () => {
    setDigestResult('sending')
    const r = await post<{ ok: boolean }>('/settings/digest/send')
    setDigestResult(r.ok ? 'Sent — check your channel.' : 'No channel delivered (configure alert channels first).')
  }

  const saveScoring = async () => {
    if (!sc) return
    await put('/scoring', { value: sc })
    setSaved('scoring'); setTimeout(() => setSaved(''), 1500)
  }
  const recompute = async () => {
    if (!sc) return
    setRecomputing('running')
    try {
      await put('/scoring', { value: sc })                 // apply current weights first
      const r = await post<{ recomputed: number }>('/scoring/recompute')
      setRecomputing(`Re-scored ${r.recomputed} posts.`)
    } catch { setRecomputing('failed') }
  }

  const reloadUsers = () => get<AppUser[]>('/auth/users').then(setUsers).catch(() => {})

  const save = async (key: keyof AllSettings) => {
    if (!s) return
    await put(`/settings/${key}`, { value: s[key] })
    setSaved(key); setTimeout(() => setSaved(''), 1500)
  }

  const testNotifiers = async () => {
    setTestResult('testing')
    const r = await post<{ ok: boolean; results: any }>('/settings/notifiers/test')
    setTestResult(r.ok ? 'Sent. Check your channel.' : 'No channel delivered (configure and save first).')
  }

  if (!s) return <div className="text-muted p-10">Loading</div>

  return (
    <div className="max-w-3xl space-y-5">
      <h2 className="font-semibold text-lg">Settings</h2>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">Alert channels</h3>
          <button onClick={() => save('notifiers')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-ink transition">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'notifiers' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-3">Where alerts are delivered. Both are optional.</p>
        <label className="block text-sm mb-2">Webhook URL
          <input value={s.notifiers.webhook_url}
            onChange={(e) => setS({ ...s, notifiers: { ...s.notifiers, webhook_url: e.target.value } })}
            placeholder="https://hooks.example.com/crawlops"
            className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px]" />
        </label>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="block text-sm">Telegram bot token
            <input value={s.notifiers.telegram_bot_token}
              onChange={(e) => setS({ ...s, notifiers: { ...s.notifiers, telegram_bot_token: e.target.value } })}
              placeholder="123456:ABC..."
              className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px]" />
          </label>
          <label className="block text-sm">Telegram chat ID
            <input value={s.notifiers.telegram_chat_id}
              onChange={(e) => setS({ ...s, notifiers: { ...s.notifiers, telegram_chat_id: e.target.value } })}
              placeholder="-1001234567890"
              className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px]" />
          </label>
        </div>
        <div className="flex items-center gap-3 mt-3">
          <button onClick={testNotifiers}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ink text-white text-sm active:scale-[0.98]">
            <IconSend size={14} stroke={2} />Send test
          </button>
          {testResult && testResult !== 'testing' && <span className="text-sm text-inksec">{testResult}</span>}
          {testResult === 'testing' && <span className="text-sm text-muted">testing</span>}
        </div>
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">Scheduled digest</h3>
          <label className="ml-3 inline-flex items-center gap-1.5 text-sm text-inksec">
            <input type="checkbox" checked={s.digest?.enabled || false}
              onChange={(e) => setS({ ...s, digest: { ...s.digest, enabled: e.target.checked } })} /> enabled
          </label>
          <button onClick={() => save('digest')} className="ml-auto inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-ink transition">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'digest' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-3">A recurring summary (volume, sentiment, trending, top voices, highest-impact mentions, and the AI brief) sent to your alert channels above.</p>
        <div className="flex flex-wrap gap-4 items-end text-sm">
          <label>Frequency
            <select value={s.digest?.frequency || 'daily'} onChange={(e) => setS({ ...s, digest: { ...s.digest, frequency: e.target.value } })}
              className="border border-grid rounded-lg px-2 py-1 ml-2"><option value="daily">Daily</option><option value="weekly">Weekly (Mon)</option></select>
          </label>
          <label>Hour (UTC)
            <input type="number" min={0} max={23} value={s.digest?.hour ?? 8}
              onChange={(e) => setS({ ...s, digest: { ...s.digest, hour: Number(e.target.value) } })}
              className="border border-grid rounded-lg px-2 py-1 w-16 ml-2" />
          </label>
          <label>Topic
            <select value={s.digest?.topic_id ?? ''} onChange={(e) => setS({ ...s, digest: { ...s.digest, topic_id: e.target.value ? Number(e.target.value) : null } })}
              className="border border-grid rounded-lg px-2 py-1 ml-2"><option value="">All topics</option>{topicsList.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
          </label>
          <label className="inline-flex items-center gap-1.5"><input type="checkbox" checked={s.digest?.include_brief ?? true}
            onChange={(e) => setS({ ...s, digest: { ...s.digest, include_brief: e.target.checked } })} /> include AI brief</label>
          <button onClick={sendDigestNow} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ink text-white text-sm active:scale-[0.98]">
            <IconSend size={14} stroke={2} />Send now
          </button>
          {digestResult && <span className="text-sm text-inksec">{digestResult === 'sending' ? 'sending…' : digestResult}</span>}
        </div>
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">Pipeline</h3>
          <button onClick={() => save('pipeline')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-ink transition">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'pipeline' ? 'Saved' : 'Save'}
          </button>
        </div>
        <div className="flex flex-wrap gap-5 mt-2 text-sm">
          <label>Default relevance threshold
            <input type="number" value={s.pipeline.default_threshold}
              onChange={(e) => setS({ ...s, pipeline: { ...s.pipeline, default_threshold: Number(e.target.value) } })}
              className="border border-grid rounded-lg px-2 py-1 w-20 ml-2" />
          </label>
          <label>Retention (days)
            <input type="number" value={s.pipeline.retention_days}
              onChange={(e) => setS({ ...s, pipeline: { ...s.pipeline, retention_days: Number(e.target.value) } })}
              className="border border-grid rounded-lg px-2 py-1 w-20 ml-2" />
          </label>
        </div>
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">Issue list (Audience &amp; Issues)</h3>
          <button onClick={() => save('issues')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-ink transition">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'issues' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-2">The AI judge classifies each post into the closest of these issues (or "other"). Type an issue and press Enter.</p>
        <TagInput value={s.issues?.list || []} onChange={(list) => setS({ ...s, issues: { list } })}
          placeholder="Add an issue…"
          suggestions={['economy', 'cost of living', 'jobs', 'healthcare', 'education', 'security', 'corruption', 'environment', 'infrastructure', 'housing']} />
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">CPM table (RM per 1000 impressions)</h3>
          <button onClick={() => save('cpm')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-ink transition">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'cpm' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-3">Drives the earned media value estimate. Adjust to your market rates, and add or remove platforms as needed.</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {Object.entries(s.cpm).map(([k, v]) => (
            <div key={k} className="flex items-center gap-1.5 border border-grid rounded-xl px-2.5 py-1.5 bg-plane/40">
              {BRAND[k]?.color && <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: BRAND[k].color }} />}
              <span className="text-[13px] capitalize truncate flex-1">{BRAND[k]?.label || k}</span>
              <input type="number" step="0.5" value={v}
                onChange={(e) => setS({ ...s, cpm: { ...s.cpm, [k]: Number(e.target.value) } })}
                className="w-16 border border-grid rounded-lg px-2 py-1 tabular-nums text-sm text-right focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
              <button onClick={() => { const { [k]: _drop, ...rest } = s.cpm; setS({ ...s, cpm: rest }) }}
                className="text-muted hover:text-danger shrink-0" title="remove"><IconX size={13} stroke={2} /></button>
            </div>
          ))}
        </div>
        <div className="mt-3 max-w-xs">
          <div className="text-[11px] text-muted mb-1">Add a platform</div>
          <MultiSelect options={PLATFORM_OPTS.filter((o) => !(o.value in s.cpm))} value={[]} placeholder="Pick platform…"
            onChange={(vals) => { const add: Record<string, number> = {}; vals.forEach((v) => { add[v] = 10 }); setS({ ...s, cpm: { ...s.cpm, ...add } }) }} />
        </div>
      </section>

      {sc && (
        <section className="bg-white border border-grid rounded-2xl p-5">
          <div className="flex items-center mb-1">
            <h3 className="font-semibold">Custom impact scoring</h3>
            <label className="ml-3 inline-flex items-center gap-1.5 text-sm text-inksec">
              <input type="checkbox" checked={sc.enabled} onChange={(e) => setSc({ ...sc, enabled: e.target.checked })} /> enabled
            </label>
            <button onClick={saveScoring} className="ml-auto inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-ink transition">
              <IconDeviceFloppy size={15} stroke={2} />{saved === 'scoring' ? 'Saved' : 'Save'}
            </button>
          </div>
          <p className="text-sm text-inksec mb-3">Your own value framework (beyond AVE). Impact = base(relevance, reach, engagement) × source/sentiment/verified/keyword multipliers. Sort the feed by <b>Impact</b>.</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            {(['w_relevance', 'w_reach', 'w_engagement', 'verified_bonus', 'keyword_factor'] as const).map((k) => (
              <label key={k} className="capitalize">{k.replace('w_', 'weight ').replace('_', ' ')}
                <input type="number" step="0.1" value={sc[k]} onChange={(e) => setSc({ ...sc, [k]: Number(e.target.value) })}
                  className="w-full border border-grid rounded-lg px-2 py-1 mt-0.5 tabular-nums" />
              </label>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm mt-3">
            {(['pos', 'neu', 'neg'] as const).map((k) => (
              <label key={k}>sentiment {k}
                <input type="number" step="0.1" value={sc.sentiment?.[k] ?? 1}
                  onChange={(e) => setSc({ ...sc, sentiment: { ...sc.sentiment, [k]: Number(e.target.value) } })}
                  className="w-full border border-grid rounded-lg px-2 py-1 mt-0.5 tabular-nums" />
              </label>
            ))}
          </div>
          <div className="grid sm:grid-cols-2 gap-4 mt-3 text-sm">
            <div>
              <div className="mb-1">Source priority <span className="text-muted font-normal">— boost specific platforms</span></div>
              <MultiSelect options={PLATFORM_OPTS} value={Object.keys(sc.platform_priority || {})} placeholder="Pick platforms to weight…"
                onChange={(keys) => { const next: any = {}; keys.forEach((k) => { next[k] = sc.platform_priority?.[k] ?? 1.5 }); setSc({ ...sc, platform_priority: next }) }} />
              <div className="space-y-1.5 mt-2">
                {Object.entries(sc.platform_priority || {}).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 text-[13px]">
                    {BRAND[k]?.color && <span className="w-2.5 h-2.5 rounded-full" style={{ background: BRAND[k].color }} />}
                    <span className="capitalize flex-1">{BRAND[k]?.label || k}</span>
                    <span className="text-muted text-[11px]">×</span>
                    <input type="number" step="0.1" value={v as number}
                      onChange={(e) => setSc({ ...sc, platform_priority: { ...sc.platform_priority, [k]: Number(e.target.value) } })}
                      className="w-16 border border-grid rounded-lg px-2 py-1 tabular-nums text-right focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
                  </div>
                ))}
                {Object.keys(sc.platform_priority || {}).length === 0 && <div className="text-muted text-[12px]">No boosts — every platform weighted 1.0.</div>}
              </div>
            </div>
            <div>
              <div className="mb-1">Priority keywords <span className="text-muted font-normal">— spokespeople, product names</span></div>
              <TagInput value={sc.keyword_terms || []} onChange={(keyword_terms) => setSc({ ...sc, keyword_terms })} placeholder="Add a keyword…" />
            </div>
          </div>
          <div className="flex items-center gap-3 mt-3">
            <button onClick={recompute} disabled={recomputing === 'running'}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ink text-white text-sm disabled:opacity-50 active:scale-[0.98]">
              {recomputing === 'running' ? 'Re-scoring…' : 'Save + recompute all'}
            </button>
            {recomputing && recomputing !== 'running' && <span className="text-sm text-inksec">{recomputing}</span>}
            <span className="text-[11px] text-muted">New posts score automatically; recompute applies weight changes to existing posts (no AI).</span>
          </div>
        </section>
      )}

      <section className="bg-white border border-grid rounded-2xl p-5">
        <h3 className="font-semibold mb-1 inline-flex items-center gap-1.5"><IconPuzzle size={16} stroke={2} />Browser extension</h3>
        <p className="text-sm text-inksec mb-4">
          The one-click way to connect Facebook / Instagram / TikTok / X / Threads: log in normally in your own
          browser, then push that session to CrawlOps. It captures the secure cookies a copy-paste can't.
        </p>

        <div className="grid sm:grid-cols-[auto_1fr] gap-x-4 gap-y-3 mb-4">
          {[
            ['1', <>Download the extension and unzip it somewhere permanent.</>],
            ['2', <>Open <code className="text-[12px] px-1 py-0.5 rounded bg-plane border border-grid">chrome://extensions</code>, turn on <b>Developer mode</b>, click <b>Load unpacked</b>, and pick the unzipped folder.</>],
            ['3', <>Open the extension's Settings, paste your CrawlOps URL and the API token below.</>],
            ['4', <>Log into a platform, then click the extension → <b>Send session to CrawlOps</b>.</>],
          ].map(([n, txt]) => (
            <div key={n as string} className="contents">
              <span className="w-6 h-6 rounded-full bg-accent/10 text-accent-ink grid place-items-center text-[12px] font-semibold shrink-0">{n as string}</span>
              <span className="text-[13px] text-inksec self-center leading-snug">{txt as React.ReactNode}</span>
            </div>
          ))}
        </div>

        <button onClick={() => download('/sources/extension.zip', 'crawlops-connector.zip')}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-accent text-white text-sm font-medium hover:brightness-110 active:scale-[0.99] transition">
          <IconDownload size={16} stroke={2} />Download extension (.zip)
        </button>

        <label className="block text-sm mt-4">API token for the extension
          <div className="flex gap-2 mt-1">
            <input readOnly value={getToken() || ''}
              className="flex-1 border border-grid rounded-lg px-3 py-2 font-mono text-[12px] bg-plane" />
            <button onClick={() => { navigator.clipboard.writeText(getToken() || ''); dialog.toast('Token copied', 'success') }}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-ink text-white text-sm active:scale-[0.98] hover:brightness-110 transition">
              <IconCopy size={14} stroke={2} />Copy
            </button>
          </div>
        </label>
        <p className="text-[11px] text-muted mt-1.5">Token rotates when you sign out and back in; re-paste it into the extension if it stops working.</p>
      </section>

      {users && (
        <section className="bg-white border border-grid rounded-2xl p-5">
          <h3 className="font-semibold mb-1">Users</h3>
          <p className="text-sm text-inksec mb-3">Admins manage access. Roles: admin, analyst, viewer.</p>
          <div className="flex flex-wrap gap-2 mb-3">
            <input value={nu.username} onChange={(e) => setNu({ ...nu, username: e.target.value })}
              placeholder="username" className="border border-grid rounded-lg px-3 py-1.5 text-sm" />
            <input type="password" value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })}
              placeholder="password" className="border border-grid rounded-lg px-3 py-1.5 text-sm" />
            <select value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}
              className="border border-grid rounded-lg px-2 py-1.5 text-sm">
              <option value="admin">admin</option><option value="analyst">analyst</option><option value="viewer">viewer</option>
            </select>
            <button onClick={() => post('/auth/users', nu).then(() => { setNu({ username: '', password: '', role: 'analyst' }); reloadUsers(); dialog.toast('User added', 'success') }).catch((e) => dialog.toast(String(e.message), 'error'))}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-ink text-white text-sm active:scale-[0.98]">
              <IconUserPlus size={14} stroke={2} />Add user
            </button>
          </div>
          <div className="divide-y divide-grid/60">
            {users.map((u) => (
              <div key={u.id} className="flex items-center gap-3 py-2 text-sm">
                <span className="font-medium">{u.username}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-grid text-inksec">{u.role}</span>
                <button onClick={() => del(`/auth/users/${u.id}`).then(reloadUsers)}
                  className="ml-auto text-inksec hover:text-red-700"><IconTrash size={14} stroke={2} /></button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
