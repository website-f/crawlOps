import {
  IconCheck, IconPencil, IconPlugConnected, IconPlus, IconTrash, IconX,
} from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { del, fmtNum, get, post, put } from '../lib/api'

interface Provider {
  id: number; name: string; base_url: string; key_hint: string; has_key: boolean
  task_models: Record<string, string>; available_models: string[]
  priority: number; enabled: boolean; tier: string
}
interface Usage {
  by_provider: { provider: string; prompt: number; completion: number; calls: number }[]
  by_task: { task: string; prompt: number; completion: number; calls: number }[]
  daily: { day: string; provider: string; tokens: number }[]
}
const SERIES = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834']

const BLANK = { name: '', base_url: '', api_key: '', task_models: {} as Record<string, string>,
  available_models: [] as string[], priority: 100, enabled: true, tier: 'free' }

export default function AIEngine() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [tasks, setTasks] = useState<string[]>([])
  const [usage, setUsage] = useState<Usage | null>(null)
  const [editing, setEditing] = useState<any | null>(null)  // form state or null
  const [editId, setEditId] = useState<number | null>(null)
  const [tests, setTests] = useState<Record<number, any>>({})
  const [loadingModels, setLoadingModels] = useState(false)

  const reload = () => {
    get<{ providers: Provider[]; tasks: string[] }>('/ai/providers').then((d) => { setProviders(d.providers); setTasks(d.tasks) })
    get<Usage>('/ai/usage?days=7').then(setUsage).catch(() => {})
  }
  useEffect(reload, [])

  const openNew = () => { setEditId(null); setEditing({ ...BLANK }) }
  const openEdit = (p: Provider) => {
    setEditId(p.id)
    setEditing({ name: p.name, base_url: p.base_url, api_key: '', task_models: { ...p.task_models },
      available_models: p.available_models, priority: p.priority, enabled: p.enabled, tier: p.tier })
  }

  const save = async () => {
    if (editId) await put(`/ai/providers/${editId}`, editing)
    else await post('/ai/providers', editing)
    setEditing(null); setEditId(null); reload()
  }

  const fetchModels = async () => {
    setLoadingModels(true)
    try {
      const r = await post<{ models: string[] }>('/ai/providers/models',
        { base_url: editing.base_url, api_key: editing.api_key, provider_id: editId })
      setEditing((e: any) => ({ ...e, available_models: r.models }))
    } catch { /* */ }
    setLoadingModels(false)
  }

  const testProvider = async (p: Provider) => {
    const model = Object.values(p.task_models)[0]
    if (!model) { setTests((t) => ({ ...t, [p.id]: { ok: false, error: 'assign a model first' } })); return }
    setTests((t) => ({ ...t, [p.id]: 'testing' }))
    const r = await post(`/ai/providers/test`, { base_url: p.base_url, model, provider_id: p.id })
    setTests((t) => ({ ...t, [p.id]: r }))
  }

  const dailyRows = useMemo(() => {
    if (!usage) return []
    const by: Record<string, any> = {}
    for (const r of usage.daily) { by[r.day] = by[r.day] || { day: r.day.slice(5) }; by[r.day][r.provider] = r.tokens }
    return Object.values(by)
  }, [usage])
  const provNames = useMemo(() => [...new Set(usage?.daily.map((d) => d.provider) || [])], [usage])

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="mr-auto">
          <h2 className="font-semibold text-lg">AI Engine</h2>
          <p className="text-sm text-inksec">Your own provider rotation. Keys are encrypted in the database. Free tiers (low priority number) are tried first; a rate-limited provider cools down 5 min and the next takes over.</p>
        </div>
        <button onClick={openNew} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-ink text-white text-sm active:scale-[0.98]">
          <IconPlus size={16} stroke={2} />Add provider
        </button>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {providers.map((p) => {
          const t = tests[p.id]
          return (
            <div key={p.id} className="bg-white border border-grid rounded-2xl p-4">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${p.enabled ? 'bg-[#0ca30c]' : 'bg-muted'}`} />
                <span className="font-semibold">{p.name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${p.tier === 'free' ? 'bg-[#0ca30c]/10 text-[#006300]' : 'bg-grid text-inksec'}`}>{p.tier}</span>
                <span className="ml-auto text-xs text-muted">#{p.priority}</span>
              </div>
              <div className="text-[11px] text-muted mt-1 truncate">{p.base_url}</div>
              <div className="text-xs mt-2">
                {p.has_key
                  ? <span className="text-[#006300]">key set ({p.key_hint})</span>
                  : <span className="text-[#b45309]">no key</span>}
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(p.task_models).map(([task, m]) => (
                  <span key={task} className="text-[10px] px-1.5 py-0.5 rounded bg-grid/60 text-inksec">{task}: {m}</span>
                ))}
                {!Object.keys(p.task_models).length && <span className="text-[11px] text-muted">no tasks assigned</span>}
              </div>
              <div className="flex items-center gap-2 mt-3">
                <button onClick={() => testProvider(p)} disabled={t === 'testing'}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-ink text-white text-xs active:scale-[0.98]">
                  <IconPlugConnected size={13} stroke={2} />{t === 'testing' ? 'Testing' : 'Test'}
                </button>
                <button onClick={() => openEdit(p)} className="inline-flex items-center gap-1 text-xs text-inksec hover:text-ink"><IconPencil size={13} stroke={2} />Edit</button>
                <button onClick={() => del(`/ai/providers/${p.id}`).then(reload)} className="inline-flex items-center gap-1 text-xs text-red-700"><IconTrash size={13} stroke={2} />Delete</button>
              </div>
              {t && t !== 'testing' && (
                <div className={`text-xs mt-2 ${t.ok ? 'text-[#006300]' : 'text-[#d03b3b]'}`}>
                  {t.ok ? `✓ ${t.latency_ms}ms · ${t.served_model}` : `✗ ${(t.error || '').slice(0, 80)}`}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {usage && (
        <>
          <div className="bg-white border border-grid rounded-2xl p-4">
            <div className="text-sm font-medium mb-2">Tokens per day by provider (7d)</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={dailyRows} barCategoryGap="25%">
                <CartesianGrid stroke="#e1e0d9" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#898781' }} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#898781' }} tickFormatter={(v) => fmtNum(v)} axisLine={false} tickLine={false} width={44} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {provNames.map((pf, i) => <Bar key={pf} dataKey={pf} stackId="t" fill={SERIES[i % SERIES.length]} stroke="#fcfcfb" strokeWidth={1} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="grid lg:grid-cols-2 gap-5">
            <UsageTable title="By provider (7d)" rows={usage.by_provider.map((r) => ({ name: r.provider, ...r }))} />
            <UsageTable title="By task (7d)" rows={usage.by_task.map((r) => ({ name: r.task, ...r }))} />
          </div>
        </>
      )}

      {editing && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setEditing(null)} />
          <div className="relative bg-white rounded-2xl border border-grid shadow-xl w-full max-w-lg p-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center mb-3">
              <h3 className="font-semibold">{editId ? 'Edit provider' : 'Add provider'}</h3>
              <button onClick={() => setEditing(null)} className="ml-auto p-1 rounded-lg hover:bg-plane"><IconX size={16} stroke={2} /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">Name<input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className="w-full border border-grid rounded-lg px-2 py-1.5 mt-0.5" /></label>
              <label className="text-sm">Tier
                <select value={editing.tier} onChange={(e) => setEditing({ ...editing, tier: e.target.value })} className="w-full border border-grid rounded-lg px-2 py-1.5 mt-0.5">
                  <option value="free">free</option><option value="paid">paid</option>
                </select>
              </label>
            </div>
            <label className="text-sm block mt-3">Base URL (OpenAI-compatible /v1)
              <input value={editing.base_url} onChange={(e) => setEditing({ ...editing, base_url: e.target.value })} placeholder="https://api.groq.com/openai/v1" className="w-full border border-grid rounded-lg px-2 py-1.5 mt-0.5 font-mono text-[12px]" /></label>
            <label className="text-sm block mt-3">API key {editId && <span className="text-muted text-xs">(leave blank to keep existing)</span>}
              <input type="password" value={editing.api_key} onChange={(e) => setEditing({ ...editing, api_key: e.target.value })} placeholder="sk-..." className="w-full border border-grid rounded-lg px-2 py-1.5 mt-0.5 font-mono text-[12px]" /></label>
            <div className="flex gap-3 mt-3">
              <label className="text-sm">Priority<input type="number" value={editing.priority} onChange={(e) => setEditing({ ...editing, priority: Number(e.target.value) })} className="w-20 border border-grid rounded-lg px-2 py-1 ml-2" /></label>
              <label className="text-sm flex items-center gap-1.5"><input type="checkbox" checked={editing.enabled} onChange={(e) => setEditing({ ...editing, enabled: e.target.checked })} /> enabled</label>
              <button onClick={fetchModels} className="ml-auto text-sm text-[#2a78d6]">{loadingModels ? 'Loading…' : 'Fetch models'}</button>
            </div>

            <div className="mt-3">
              <div className="text-sm font-medium mb-1">Assign a model per task</div>
              <p className="text-[11px] text-muted mb-2">Only tasks with a model are served by this provider. Fetch models above, or type a model id.</p>
              {tasks.map((task) => (
                <div key={task} className="flex items-center gap-2 mb-1.5">
                  <span className="w-16 text-sm capitalize">{task}</span>
                  <input list={`models-${task}`} value={editing.task_models[task] || ''}
                    onChange={(e) => setEditing({ ...editing, task_models: { ...editing.task_models, [task]: e.target.value } })}
                    placeholder="model id (blank = skip)"
                    className="flex-1 border border-grid rounded-lg px-2 py-1 text-[12px] font-mono" />
                  <datalist id={`models-${task}`}>
                    {editing.available_models.map((m: string) => <option key={m} value={m} />)}
                  </datalist>
                </div>
              ))}
            </div>

            <div className="flex gap-2 justify-end mt-4">
              <button onClick={() => setEditing(null)} className="px-4 py-1.5 text-sm text-inksec">Cancel</button>
              <button onClick={save} className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-ink text-white text-sm">
                <IconCheck size={14} stroke={2} />Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function UsageTable({ title, rows }: { title: string; rows: { name: string; prompt: number; completion: number; calls: number }[] }) {
  return (
    <div className="bg-white border border-grid rounded-2xl p-4">
      <div className="text-sm font-medium mb-2">{title}</div>
      <table className="w-full text-sm">
        <thead><tr className="text-xs text-muted text-left"><th className="font-normal pb-1">name</th><th className="font-normal text-right">calls</th><th className="font-normal text-right">prompt</th><th className="font-normal text-right">completion</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-t border-grid/60">
              <td className="py-1.5 capitalize">{r.name}</td>
              <td className="text-right tabular-nums">{r.calls}</td>
              <td className="text-right tabular-nums">{fmtNum(r.prompt)}</td>
              <td className="text-right tabular-nums">{fmtNum(r.completion)}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td className="text-muted py-2" colSpan={4}>No AI calls yet.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
