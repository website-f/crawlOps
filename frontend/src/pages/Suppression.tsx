import { IconUserOff } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { PlatformBadge } from '../components/PlatformIcon'
import { del, get, post } from '../lib/api'
import { FEED_TABS } from '../lib/platform'

interface Sup { id: number; platform: string; author_key: string; mode: string; reason: string; created_at: string }

export default function Suppression() {
  const [items, setItems] = useState<Sup[]>([])
  const [form, setForm] = useState({ platform: 'facebook', author_key: '', mode: 'hide', reason: '' })

  const reload = () => get<Sup[]>('/suppression').then(setItems)
  useEffect(() => { reload() }, [])

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="text-lg font-bold tracking-tight">Suppression</h1>
        <p className="text-[13px] text-inksec mt-0.5">
          Internal shadowban: <b>hide</b> removes an author's posts from feeds and analytics, while
          <b> watch</b> keeps them visible but excludes them from every metric. Both are reversible
          and only affect CrawlOps, never the actual platform.
        </p>
      </div>

      <div className="bg-white border border-grid rounded-2xl shadow-card p-4 flex flex-wrap gap-2 items-center">
        <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}
          className="border border-grid rounded-xl px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition">
          {FEED_TABS.filter((t) => t !== 'all').map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input value={form.author_key} onChange={(e) => setForm({ ...form, author_key: e.target.value })}
          placeholder="author key / handle" className="flex-1 min-w-40 border border-grid rounded-xl px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition" />
        <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}
          className="border border-grid rounded-xl px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition">
          <option value="hide">hide</option><option value="watch">watch</option>
        </select>
        <input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}
          placeholder="reason" className="flex-1 min-w-32 border border-grid rounded-xl px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition" />
        <button onClick={() => post('/suppression', form).then(reload)}
          className="px-4 py-1.5 rounded-xl bg-ink text-white text-sm hover:brightness-110 active:scale-[0.99] transition">Suppress</button>
      </div>

      <div className="bg-white border border-grid rounded-2xl shadow-card divide-y divide-grid/60">
        {items.map((s) => {
          return (
            <div key={s.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <PlatformBadge platform={s.platform} size={24} />
              <span className="font-medium">{s.author_key}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold
                ${s.mode === 'hide' ? 'bg-danger/10 text-danger' : 'bg-warn/10 text-warn'}`}>
                {s.mode}
              </span>
              <span className="text-xs text-muted truncate flex-1">{s.reason}</span>
              <button onClick={() => del(`/suppression/${s.id}`).then(reload)} className="text-xs text-inksec hover:text-ink">unsuppress</button>
            </div>
          )
        })}
        {items.length === 0 && (
          <div className="text-center p-10">
            <IconUserOff size={28} stroke={1.5} className="mx-auto text-muted" />
            <div className="text-muted text-sm mt-2">Nobody suppressed. Use the mute or watch buttons on any post.</div>
          </div>
        )}
      </div>
    </div>
  )
}
