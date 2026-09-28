import { IconBell, IconBellRinging, IconTrash } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { del, get, post } from '../lib/api'

interface Topic { id: number; name: string }
interface Rule { id: number; topic_id: number; kind: string; config: any; notify: any; active: boolean }
interface Event { id: number; rule_id: number; fired_at: string; payload: any }

const KIND_LABEL: Record<string, string> = { spike: 'Volume spike', neg_sentiment: 'Negative sentiment surge' }

export default function Alerts() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [rules, setRules] = useState<Rule[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [form, setForm] = useState({ topic_id: 0, kind: 'spike', neg_pct: 40, cooldown_hours: 6 })

  const reload = () => {
    get<Rule[]>('/alerts/rules').then(setRules)
    get<Event[]>('/alerts/events?limit=40').then(setEvents)
  }
  useEffect(() => {
    get<Topic[]>('/topics').then((t) => { setTopics(t); if (t[0]) setForm((f) => ({ ...f, topic_id: t[0].id })) })
    reload()
  }, [])

  const create = async () => {
    if (!form.topic_id) return
    const config = form.kind === 'neg_sentiment'
      ? { neg_pct: form.neg_pct, window_hours: 24, min_volume: 10, cooldown_hours: form.cooldown_hours }
      : { cooldown_hours: form.cooldown_hours }
    await post('/alerts/rules', { topic_id: form.topic_id, kind: form.kind, config, notify: {} })
    reload()
  }

  const topicName = (id: number) => topics.find((t) => t.id === id)?.name ?? `topic ${id}`

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <div className="space-y-5">
        <div className="bg-white border border-grid rounded-2xl p-5">
          <h2 className="font-semibold text-lg mb-1">Alert rules</h2>
          <p className="text-sm text-inksec mb-4">
            Delivery uses the channels set in Settings. Spike detection uses an EWMA baseline plus MAD residuals; negative-sentiment fires when the negative share crosses your threshold.
          </p>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <select value={form.topic_id} onChange={(e) => setForm({ ...form, topic_id: Number(e.target.value) })}
              className="border border-grid rounded-lg px-2 py-1.5 text-sm">
              {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}
              className="border border-grid rounded-lg px-2 py-1.5 text-sm">
              <option value="spike">Volume spike</option>
              <option value="neg_sentiment">Negative sentiment</option>
            </select>
            {form.kind === 'neg_sentiment' && (
              <label className="text-sm inline-flex items-center gap-1">neg %
                <input type="number" value={form.neg_pct} onChange={(e) => setForm({ ...form, neg_pct: Number(e.target.value) })}
                  className="border border-grid rounded-lg px-2 py-1 w-16" />
              </label>
            )}
            <button onClick={create}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-ink text-white text-sm active:scale-[0.98]">
              <IconBell size={15} stroke={2} />Add rule
            </button>
          </div>

          <div className="divide-y divide-grid/60">
            {rules.map((r) => (
              <div key={r.id} className="flex items-center gap-3 py-2.5 text-sm">
                <span className={`w-2 h-2 rounded-full ${r.active ? 'bg-[#0ca30c]' : 'bg-muted'}`} />
                <span className="font-medium">{KIND_LABEL[r.kind] || r.kind}</span>
                <span className="text-inksec">on {topicName(r.topic_id)}</span>
                {r.kind === 'neg_sentiment' && <span className="text-xs text-muted">&ge;{r.config?.neg_pct ?? 40}%</span>}
                <button onClick={() => del(`/alerts/rules/${r.id}`).then(reload)}
                  className="ml-auto text-inksec hover:text-red-700"><IconTrash size={15} stroke={2} /></button>
              </div>
            ))}
            {rules.length === 0 && <div className="text-muted text-sm py-3">No rules yet.</div>}
          </div>
        </div>
      </div>

      <div className="bg-white border border-grid rounded-2xl p-5">
        <h2 className="font-semibold text-lg mb-3">Recent alerts</h2>
        <div className="space-y-3">
          {events.map((e) => (
            <div key={e.id} className="flex gap-3 p-3 rounded-xl bg-plane/60 border border-grid">
              <IconBellRinging size={18} stroke={1.8} className="text-[#d03b3b] shrink-0 mt-0.5" />
              <div className="min-w-0">
                <div className="font-medium text-sm">{e.payload?.title || 'Alert'}</div>
                <div className="text-sm text-inksec">{e.payload?.body}</div>
                <div className="text-xs text-muted mt-0.5">{new Date(e.fired_at).toLocaleString()}</div>
              </div>
            </div>
          ))}
          {events.length === 0 && (
            <div className="text-center py-12">
              <IconBell size={28} stroke={1.5} className="mx-auto text-muted" />
              <div className="text-muted text-sm mt-2">No alerts fired yet.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
