import { IconCopy, IconDeviceFloppy, IconPuzzle, IconSend, IconTrash, IconUserPlus } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { del, get, getToken, post, put } from '../lib/api'

interface AllSettings {
  cpm: Record<string, number>
  notifiers: { webhook_url: string; telegram_bot_token: string; telegram_chat_id: string }
  pipeline: { default_threshold: number; retention_days: number }
  issues: { list: string[] }
}

interface AppUser { id: number; username: string; role: string }

export default function Settings() {
  const [s, setS] = useState<AllSettings | null>(null)
  const [saved, setSaved] = useState('')
  const [testResult, setTestResult] = useState('')
  const [users, setUsers] = useState<AppUser[] | null>(null)
  const [nu, setNu] = useState({ username: '', password: '', role: 'analyst' })

  useEffect(() => {
    get<AllSettings>('/settings').then(setS)
    get<AppUser[]>('/auth/users').then(setUsers).catch(() => setUsers(null)) // 403 for non-admins
  }, [])

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
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-[#2a78d6]">
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
          <h3 className="font-semibold">Pipeline</h3>
          <button onClick={() => save('pipeline')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-[#2a78d6]">
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
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-[#2a78d6]">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'issues' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-2">The AI judge classifies each post into the closest of these issues (or "other"). One per line.</p>
        <textarea rows={6} value={(s.issues?.list || []).join('\n')}
          onChange={(e) => setS({ ...s, issues: { list: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) } })}
          className="w-full border border-grid rounded-lg px-3 py-2 text-sm font-mono text-[13px]" />
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">CPM table (RM per 1000 impressions)</h3>
          <button onClick={() => save('cpm')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-[#2a78d6]">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'cpm' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-3">Drives the earned media value estimate. Adjust to your market rates.</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {Object.entries(s.cpm).map(([k, v]) => (
            <label key={k} className="text-sm capitalize">{k}
              <input type="number" step="0.5" value={v}
                onChange={(e) => setS({ ...s, cpm: { ...s.cpm, [k]: Number(e.target.value) } })}
                className="w-full border border-grid rounded-lg px-2 py-1 mt-0.5 tabular-nums" />
            </label>
          ))}
        </div>
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <h3 className="font-semibold mb-1 inline-flex items-center gap-1.5"><IconPuzzle size={16} stroke={2} />Browser extension</h3>
        <p className="text-sm text-inksec mb-3">
          Install <code>browser-extension/</code> (chrome://extensions → Developer mode → Load unpacked),
          then paste this token + your CrawlOps URL into it. Log into a platform in your browser and click
          the extension to connect that account. No cookie copying.
        </p>
        <label className="block text-sm">API token for the extension
          <div className="flex gap-2 mt-1">
            <input readOnly value={getToken() || ''}
              className="flex-1 border border-grid rounded-lg px-3 py-2 font-mono text-[12px] bg-plane" />
            <button onClick={() => navigator.clipboard.writeText(getToken() || '')}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-ink text-white text-sm active:scale-[0.98]">
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
            <button onClick={() => post('/auth/users', nu).then(() => { setNu({ username: '', password: '', role: 'analyst' }); reloadUsers() }).catch((e) => alert(String(e.message)))}
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
