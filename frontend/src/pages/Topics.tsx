import { IconPencil, IconPlayerPlay, IconSparkles, IconTrash } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { del, get, post, put } from '../lib/api'
import { FEED_TABS } from '../lib/platform'

interface Topic {
  id: number; name: string; query: string; criteria: string; threshold: number
  langs: string[]; platforms: string[]; schedule_minutes: number; active: boolean
  last_run_at: string | null
}

const EMPTY = { name: '', query: '', criteria: '', threshold: 55, langs: [], platforms: [], schedule_minutes: 30, active: true }

export default function Topics() {
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
    <div className="grid lg:grid-cols-2 gap-6">
      <div className="bg-white border border-grid rounded-2xl p-5">
        <h2 className="font-semibold text-lg mb-3">{editing ? `Edit topic #${editing}` : 'New topic'}</h2>

        <div className="flex gap-2 mb-4">
          <input value={brief} onChange={(e) => setBrief(e.target.value)}
            placeholder='Describe it plainly: "monitor Proton Malaysia EV launches vs BYD"'
            className="flex-1 border border-grid rounded-xl px-3 py-2 text-sm" />
          <button onClick={buildWithAI} disabled={building}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#4a3aa7] text-white text-sm
                       disabled:opacity-50 active:scale-[0.98] whitespace-nowrap">
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
          <span className="text-sm text-inksec">Platforms (none = all)</span>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {FEED_TABS.filter((t) => t !== 'all').map((pf) => {
              const on = form.platforms.includes(pf)
              return (
                <button key={pf} onClick={() => setForm({
                  ...form, platforms: on ? form.platforms.filter((x: string) => x !== pf) : [...form.platforms, pf],
                })}
                  className={`px-2.5 py-1 rounded-full text-xs border ${on ? 'bg-ink text-white border-ink' : 'bg-white border-grid text-inksec'}`}>
                  {pf}
                </button>
              )
            })}
          </div>
        </div>

        {err && <div className="text-red-700 text-sm mb-3">{err}</div>}
        <div className="flex gap-2">
          <button onClick={save} className="px-5 py-2 rounded-xl bg-ink text-white text-sm">{editing ? 'Save' : 'Create & start crawling'}</button>
          {editing && <button onClick={() => { setEditing(null); setForm(EMPTY) }} className="px-4 py-2 text-sm text-inksec">Cancel</button>}
        </div>
      </div>

      <div className="space-y-3">
        {topics.map((t) => (
          <div key={t.id} className="bg-white border border-grid rounded-2xl p-4">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${t.active ? 'bg-[#0ca30c]' : 'bg-muted'}`} />
              <span className="font-semibold">{t.name}</span>
              <span className="text-xs text-muted ml-auto">
                every {t.schedule_minutes}m · last run {t.last_run_at ? new Date(t.last_run_at).toLocaleTimeString() : 'never'}
              </span>
            </div>
            {t.query && <code className="block text-xs bg-plane rounded-lg px-2 py-1.5 mt-2 text-inksec">{t.query}</code>}
            {t.criteria && <p className="text-xs text-inksec mt-1.5 line-clamp-2">{t.criteria}</p>}
            <div className="flex gap-4 mt-2.5 text-xs font-medium">
              <button onClick={() => post(`/topics/${t.id}/run-now`).then(reload)}
                className="inline-flex items-center gap-1 text-[#2a78d6] active:scale-[0.97]">
                <IconPlayerPlay size={13} stroke={2} />Run now
              </button>
              <button onClick={() => { setEditing(t.id); setForm({ ...t }) }}
                className="inline-flex items-center gap-1 text-inksec active:scale-[0.97]">
                <IconPencil size={13} stroke={2} />Edit
              </button>
              <button onClick={() => del(`/topics/${t.id}`).then(reload)}
                className="inline-flex items-center gap-1 text-red-700 active:scale-[0.97]">
                <IconTrash size={13} stroke={2} />Delete
              </button>
            </div>
          </div>
        ))}
        {topics.length === 0 && <div className="text-muted text-sm p-6 text-center bg-white rounded-2xl border border-grid">No topics yet. Create one to start crawling.</div>}
      </div>
    </div>
  )
}
