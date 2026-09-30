import { IconPencil, IconPlayerPlay, IconSparkles, IconTrash } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { MultiSelect } from '../components/ui/controls'
import { useDialog } from '../components/ui/overlays'
import { del, get, post, put } from '../lib/api'
import { BRAND, FEED_TABS } from '../lib/platform'

const PLATFORM_OPTS = FEED_TABS.filter((t) => t !== 'all').map((p) => ({ value: p, label: BRAND[p]?.label || p, color: BRAND[p]?.color }))

interface Topic {
  id: number; name: string; query: string; criteria: string; threshold: number
  langs: string[]; platforms: string[]; schedule_minutes: number; active: boolean
  run_once: boolean; last_run_at: string | null
}

const EMPTY = { name: '', query: '', criteria: '', threshold: 55, langs: [], platforms: [], schedule_minutes: 30, active: true }

export default function Topics() {
  const dialog = useDialog()
  const [topics, setTopics] = useState<Topic[]>([])
  const [form, setForm] = useState<any>(EMPTY)
  const [editing, setEditing] = useState<number | null>(null)
  const [brief, setBrief] = useState('')
  const [building, setBuilding] = useState(false)
  const [err, setErr] = useState('')

  const reload = () => get<Topic[]>('/topics').then(setTopics)
  useEffect(() => { reload() }, [])

  const save = async () => {
    setErr('')
    try {
      if (editing) await put(`/topics/${editing}`, form)
      else await post('/topics', form)
      setForm(EMPTY); setEditing(null); reload()
    } catch (e: any) { setErr(String(e.message || e)) }
  }

  const buildWithAI = async () => {
    if (!brief.trim()) return
    setBuilding(true); setErr('')
    try {
      const r = await post<{ query: string; criteria: string; note: string }>('/topics/build-query', { brief })
      setForm({ ...form, query: r.query, criteria: r.criteria, name: form.name || brief.slice(0, 60) })
    } catch (e: any) { setErr(String(e.message || e)) }
    setBuilding(false)
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-bold tracking-tight">Topics</h1>
        <p className="text-[13px] text-inksec">Define what to listen for. Each topic crawls on its own schedule — pause any with its Auto-run toggle.</p>
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
      <div className="bg-surface border border-grid rounded-2xl p-5 shadow-card lg:sticky lg:top-4 self-start">
        <h2 className="font-semibold text-[15px] mb-3">{editing ? `Edit topic #${editing}` : 'New topic'}</h2>

        <div className="flex gap-2 mb-4">
          <input value={brief} onChange={(e) => setBrief(e.target.value)}
            placeholder='Describe it plainly: "monitor Proton Malaysia EV launches vs BYD"'
            className="flex-1 border border-grid rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition" />
          <button onClick={buildWithAI} disabled={building}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent text-white text-sm
                       disabled:opacity-50 hover:brightness-110 active:scale-[0.98] whitespace-nowrap transition">
            <IconSparkles size={15} stroke={2} />
            {building ? 'Building' : 'AI build'}
          </button>
        </div>

        {['name', 'query', 'criteria'].map((k) => (
          <label key={k} className="block mb-3 text-sm">
            <span className="text-inksec capitalize">{k === 'criteria' ? 'Judge criteria (natural language)' : k === 'query' ? 'Boolean query' : 'Name'}</span>
            {k === 'criteria' ? (
              <textarea value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} rows={3}
                placeholder="Only posts genuinely about X; exclude job ads and merch spam."
                className="w-full border border-grid rounded-xl px-3 py-2 mt-1" />
            ) : (
              <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                placeholder={k === 'query' ? '(proton OR "proton e.mas") AND (ev OR electric) NOT (wallpaper)' : ''}
                className="w-full border border-grid rounded-xl px-3 py-2 mt-1 font-mono text-[13px]" />
            )}
          </label>
        ))}

        <div className="flex gap-4 mb-3 text-sm">
          <label>Threshold <input type="number" value={form.threshold}
            onChange={(e) => setForm({ ...form, threshold: Number(e.target.value) })}
            className="border border-grid rounded-lg px-2 py-1 w-16 ml-1" /></label>
          <label>Every <input type="number" value={form.schedule_minutes}
            onChange={(e) => setForm({ ...form, schedule_minutes: Number(e.target.value) })}
            className="border border-grid rounded-lg px-2 py-1 w-16 mx-1" />min</label>
        </div>

        <div className="mb-4">
          <span className="text-sm text-inksec">Platforms <span className="text-muted">(none = all)</span></span>
          <div className="mt-1.5">
            <MultiSelect options={PLATFORM_OPTS} value={form.platforms} placeholder="All platforms"
              onChange={(platforms) => setForm({ ...form, platforms })} />
          </div>
        </div>

        {err && <div className="text-danger text-sm mb-3">{err}</div>}
        <div className="flex gap-2">
          <button onClick={save} className="px-5 py-2 rounded-xl bg-ink text-white text-sm font-medium hover:brightness-110 active:scale-[0.99] transition">{editing ? 'Save' : 'Create & start crawling'}</button>
          {editing && <button onClick={() => { setEditing(null); setForm(EMPTY) }} className="px-4 py-2 text-sm text-inksec hover:bg-plane rounded-xl transition">Cancel</button>}
        </div>
      </div>

      <div className="space-y-3">
        {topics.map((t) => (
          <div key={t.id} className="bg-surface border border-grid rounded-2xl p-4 shadow-card">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${t.active ? 'bg-positive' : 'bg-muted'}`}
                title={t.active ? 'auto-runs on schedule' : 'paused'} />
              <span className="font-semibold">{t.name}</span>
              {t.run_once && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent-ink">queued</span>}
              <span className="text-xs text-muted ml-auto">
                {t.active ? `every ${t.schedule_minutes}m` : 'manual'} · last {t.last_run_at ? new Date(t.last_run_at).toLocaleTimeString() : 'never'}
              </span>
            </div>
            {t.query && <code className="block text-xs bg-plane rounded-lg px-2 py-1.5 mt-2 text-inksec">{t.query}</code>}
            {t.criteria && <p className="text-xs text-inksec mt-1.5 line-clamp-2">{t.criteria}</p>}
            <div className="flex flex-wrap gap-x-4 gap-y-2 mt-2.5 text-xs font-medium items-center">
              <button onClick={() => post(`/topics/${t.id}/run-now`).then(reload)}
                className="inline-flex items-center gap-1 text-accent hover:text-accent-ink active:scale-[0.97] transition">
                <IconPlayerPlay size={13} stroke={2} />Run now
              </button>
              {/* auto-run toggle: paused topics only crawl on Run now, so they stop filling storage */}
              <button onClick={() => post(`/topics/${t.id}/toggle-active`).then(reload)}
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border active:scale-[0.97] transition
                  ${t.active ? 'border-positive/40 text-positive bg-positive/5' : 'border-grid text-muted hover:text-ink'}`}>
                <span className={`w-2 h-2 rounded-full ${t.active ? 'bg-positive' : 'bg-muted'}`} />
                Auto-run {t.active ? 'on' : 'off'}
              </button>
              <button onClick={() => { setEditing(t.id); setForm({ ...t }) }}
                className="inline-flex items-center gap-1 text-inksec active:scale-[0.97]">
                <IconPencil size={13} stroke={2} />Edit
              </button>
              <button onClick={async () => {
                if (!(await dialog.confirm({ title: 'Clear fetched results', message: `Remove every fetched post and cached media for "${t.name}". The topic itself stays and will keep crawling.`, confirmText: 'Clear results' }))) return
                const r = await post<{ deleted: number }>('/posts/delete', { topic_id: t.id })
                dialog.toast(`Cleared ${r.deleted} posts`, 'success'); reload()
              }} className="inline-flex items-center gap-1 text-[#b45309] active:scale-[0.97]">
                <IconTrash size={13} stroke={2} />Clear results
              </button>
              <button onClick={async () => {
                if (!(await dialog.confirm({ title: 'Delete topic', message: `"${t.name}" and all of its data — posts, media, clusters and alerts — will be permanently removed. This cannot be undone.`, variant: 'danger', confirmText: 'Delete topic' }))) return
                await del(`/topics/${t.id}`); reload(); dialog.toast('Topic deleted')
              }} className="inline-flex items-center gap-1 text-danger active:scale-[0.97]">
                <IconTrash size={13} stroke={2} />Delete topic
              </button>
            </div>
          </div>
        ))}
        {topics.length === 0 && <div className="text-muted text-sm p-6 text-center bg-surface rounded-2xl border border-grid">No topics yet. Create one to start crawling.</div>}
      </div>
      </div>
    </div>
  )
}
