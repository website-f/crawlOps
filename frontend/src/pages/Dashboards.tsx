import { IconArrowBigDown, IconArrowBigUp, IconDeviceFloppy, IconLayoutDashboard, IconPlus, IconTrash, IconX } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { PlatformIcon } from '../components/PlatformIcon'
import { useDialog } from '../components/ui/overlays'
import { del, fmtNum, get, post, put } from '../lib/api'
import { SENTIMENT } from '../lib/platform'

interface Widget { id: string; type: string; title: string }
interface Dash { id: number; name: string; widgets: Widget[] }

const CATALOG: { type: string; title: string }[] = [
  { type: 'kpi', title: 'Key numbers' },
  { type: 'sentiment', title: 'Sentiment split' },
  { type: 'volume', title: 'Volume trend' },
  { type: 'platforms', title: 'Top sources' },
  { type: 'trending', title: 'Trending now' },
  { type: 'authors', title: 'Top voices' },
  { type: 'domains', title: 'Top domains' },
]

export default function Dashboards() {
  const dialog = useDialog()
  const [dashes, setDashes] = useState<Dash[]>([])
  const [cur, setCur] = useState<Dash | null>(null)
  const [topics, setTopics] = useState<{ id: number; name: string }[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [days, setDays] = useState(30)
  const [ov, setOv] = useState<any>(null)
  const [trend, setTrend] = useState<any[]>([])
  const [authors, setAuthors] = useState<any[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [dirty, setDirty] = useState(false)

  const loadDashes = () => get<Dash[]>('/dashboards').then((d) => { setDashes(d); if (!cur && d[0]) setCur(d[0]) })
  useEffect(() => { loadDashes(); get('/topics').then(setTopics).catch(() => {}) }, [])

  // shared data for all widgets on the current scope
  useEffect(() => {
    const qs = `${topicId ? `topic_id=${topicId}&` : ''}days=${days}`
    get(`/analytics/overview?${qs}`).then(setOv).catch(() => setOv(null))
    get(`/analytics/trending?hours=${days * 24}${topicId ? `&topic_id=${topicId}` : ''}`).then((d: any) => setTrend(d.trending || [])).catch(() => setTrend([]))
    get(`/authors/top?limit=8${topicId ? `&topic_id=${topicId}` : ''}`).then(setAuthors).catch(() => setAuthors([]))
  }, [topicId, days])

  const newDash = async () => {
    const name = await dialog.prompt({ title: 'New dashboard', label: 'Name', placeholder: 'e.g. Brand health' }); if (!name) return
    const d = await post<Dash>('/dashboards', { name, widgets: CATALOG.slice(0, 4).map((w, i) => ({ id: `w${i}${Date.now()}`, ...w })) })
    await loadDashes(); setCur(d); setDirty(false); dialog.toast('Dashboard created', 'success')
  }
  const saveDash = async () => {
    if (!cur) return
    await put(`/dashboards/${cur.id}`, { name: cur.name, widgets: cur.widgets })
    setDirty(false); loadDashes()
  }
  const removeDash = async () => {
    if (!cur) return
    if (!(await dialog.confirm({ title: 'Delete dashboard', message: `"${cur.name}" and its layout will be removed.`, variant: 'danger', confirmText: 'Delete' }))) return
    await del(`/dashboards/${cur.id}`); setCur(null); loadDashes(); dialog.toast('Dashboard deleted')
  }
  const addWidget = (w: { type: string; title: string }) => {
    if (!cur) return
    setCur({ ...cur, widgets: [...cur.widgets, { id: `w${Date.now()}`, ...w }] }); setDirty(true); setAddOpen(false)
  }
  const removeWidget = (id: string) => { if (cur) { setCur({ ...cur, widgets: cur.widgets.filter((w) => w.id !== id) }); setDirty(true) } }
  const move = (i: number, dir: -1 | 1) => {
    if (!cur) return
    const ws = [...cur.widgets]; const j = i + dir
    if (j < 0 || j >= ws.length) return
    ;[ws[i], ws[j]] = [ws[j], ws[i]]; setCur({ ...cur, widgets: ws }); setDirty(true)
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold tracking-tight">Dashboards</h1>
        <p className="text-[13px] text-inksec mt-0.5">Build your own view — pick a topic and range to scope every widget at once.</p>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <IconLayoutDashboard size={20} stroke={2} className="text-accent" />
        <select value={cur?.id ?? ''} onChange={(e) => setCur(dashes.find((d) => d.id === Number(e.target.value)) || null)}
          className="border border-grid rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition">
          <option value="">Select dashboard…</option>
          {dashes.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <button onClick={newDash} className="inline-flex items-center gap-1 px-3 py-2 rounded-xl text-sm border border-grid bg-white hover:bg-plane transition"><IconPlus size={15} stroke={2} />New</button>
        {cur && (
          <>
            <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
              className="border border-grid rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition">
              <option value="">All topics</option>{topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="border border-grid rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition">
              <option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option>
            </select>
            <div className="relative">
              <button onClick={() => setAddOpen((o) => !o)} className="inline-flex items-center gap-1 px-3 py-2 rounded-xl text-sm border border-grid bg-white hover:bg-plane transition"><IconPlus size={15} stroke={2} />Widget</button>
              {addOpen && (
                <div className="absolute z-30 mt-1 w-48 bg-white border border-grid rounded-xl shadow-float p-1">
                  {CATALOG.map((w) => <button key={w.type} onClick={() => addWidget(w)} className="w-full text-left px-3 py-1.5 rounded-lg text-sm hover:bg-plane">{w.title}</button>)}
                </div>
              )}
            </div>
            <button onClick={saveDash} disabled={!dirty}
              className={`ml-auto inline-flex items-center gap-1 px-3 py-2 rounded-xl text-sm transition ${dirty ? 'bg-ink text-white hover:brightness-110 active:scale-[0.99]' : 'border border-grid bg-white text-muted'}`}>
              <IconDeviceFloppy size={15} stroke={2} />{dirty ? 'Save' : 'Saved'}
            </button>
            <button onClick={removeDash} className="inline-flex items-center gap-1 px-3 py-2 rounded-xl text-sm border border-grid bg-white text-danger hover:bg-danger/5 transition"><IconTrash size={15} stroke={2} /></button>
          </>
        )}
      </div>

      {!cur && (
        <div className="text-center py-20 bg-white rounded-2xl border border-grid shadow-card text-muted">
          <IconLayoutDashboard size={32} stroke={1.5} className="mx-auto" />
          <div className="mt-3 font-medium text-ink">Build your own dashboard</div>
          <p className="text-sm mt-1">Create one, then add widgets. Pick a topic + time range to scope every widget at once.</p>
        </div>
      )}

      {cur && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cur.widgets.map((w, i) => (
            <div key={w.id} className="bg-white border border-grid rounded-2xl shadow-card p-4">
              <div className="flex items-center gap-1 mb-2">
                <span className="text-sm font-semibold">{w.title}</span>
                <div className="ml-auto flex items-center gap-0.5 text-muted">
                  <button onClick={() => move(i, -1)} className="p-0.5 hover:text-ink"><IconArrowBigUp size={14} stroke={2} /></button>
                  <button onClick={() => move(i, 1)} className="p-0.5 hover:text-ink"><IconArrowBigDown size={14} stroke={2} /></button>
                  <button onClick={() => removeWidget(w.id)} className="p-0.5 hover:text-danger"><IconX size={14} stroke={2} /></button>
                </div>
              </div>
              <WidgetBody type={w.type} ov={ov} trend={trend} authors={authors} />
            </div>
          ))}
          {cur.widgets.length === 0 && <div className="text-muted text-sm col-span-full text-center py-10">Empty — click “Widget” to add one.</div>}
        </div>
      )}
    </div>
  )
}

function WidgetBody({ type, ov, trend, authors }: { type: string; ov: any; trend: any[]; authors: any[] }) {
  if (type === 'trending') {
    return trend.length ? (
      <div className="flex flex-wrap gap-1.5">
        {trend.slice(0, 12).map((t) => <span key={t.term} className="text-[12px] px-2 py-0.5 rounded-full border border-grid">{t.term} <span className="text-muted">{t.velocity}×</span></span>)}
      </div>
    ) : <Empty />
  }
  if (type === 'authors') {
    return authors.length ? (
      <div className="space-y-1">
        {authors.slice(0, 8).map((a, i) => (
          <div key={i} className="flex items-center gap-2 text-sm"><PlatformIcon platform={a.platform} size={14} />
            <span className="truncate flex-1">{a.author_name || a.author_handle}</span>
            <span className="tabular-nums text-muted text-xs">{fmtNum(a.posts)}</span></div>
        ))}
      </div>
    ) : <Empty />
  }
  if (!ov) return <Empty />
  if (type === 'kpi') {
    return (
      <div className="flex gap-5">
        <Kpi label="mentions" value={fmtNum(ov.total)} />
        <Kpi label="reach" value={fmtNum(ov.reach_total)} />
        <Kpi label="EMV" value={`RM ${fmtNum(ov.emv_total)}`} />
      </div>
    )
  }
  if (type === 'sentiment') {
    const s = ov.sentiment || {}; const tot = (s.pos + s.neu + s.neg) || 1
    return (
      <div>
        <div className="flex h-3 rounded-full overflow-hidden bg-plane">
          {(['pos', 'neu', 'neg'] as const).map((k) => <div key={k} style={{ width: `${(100 * (s[k] || 0)) / tot}%`, background: SENTIMENT[k].color }} />)}
        </div>
        <div className="flex gap-4 mt-2 text-xs">
          {(['pos', 'neu', 'neg'] as const).map((k) => <span key={k} className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: SENTIMENT[k].color }} />{SENTIMENT[k].label} {s[k] || 0}</span>)}
        </div>
      </div>
    )
  }
  if (type === 'platforms') {
    const rows = ov.by_platform || []; const max = Math.max(1, ...rows.map((r: any) => r.count))
    return (
      <div className="space-y-1.5">
        {rows.slice(0, 7).map((r: any) => (
          <div key={r.platform} className="flex items-center gap-2 text-xs">
            <span className="w-20 truncate capitalize inline-flex items-center gap-1"><PlatformIcon platform={r.platform} size={13} />{r.platform}</span>
            <div className="flex-1 h-2 bg-plane rounded-full overflow-hidden"><div className="h-full bg-accent" style={{ width: `${(100 * r.count) / max}%` }} /></div>
            <span className="tabular-nums text-muted w-10 text-right">{fmtNum(r.count)}</span>
          </div>
        ))}
      </div>
    )
  }
  if (type === 'domains') {
    const rows = ov.top_domains || []
    return rows.length ? (
      <div className="space-y-1">
        {rows.slice(0, 8).map((r: any) => <div key={r.domain} className="flex items-center gap-2 text-sm"><span className="truncate flex-1">{r.domain}</span><span className="tabular-nums text-muted text-xs">{fmtNum(r.count)}</span></div>)}
      </div>
    ) : <Empty />
  }
  if (type === 'volume') {
    const byDay: Record<string, number> = {}
    for (const d of ov.daily || []) byDay[d.day] = (byDay[d.day] || 0) + d.count
    const days = Object.keys(byDay).sort(); const vals = days.map((d) => byDay[d])
    if (!vals.length) return <Empty />
    const max = Math.max(...vals); const w = 300; const h = 60
    const pts = vals.map((v, i) => `${(i / Math.max(1, vals.length - 1)) * w},${h - (v / max) * h}`).join(' ')
    return (
      <div>
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-16"><polyline fill="none" className="stroke-accent" strokeWidth="2" points={pts} /></svg>
        <div className="text-xs text-muted mt-1">{fmtNum(vals.reduce((a, b) => a + b, 0))} mentions over {days.length} days</div>
      </div>
    )
  }
  return <Empty />
}

const Kpi = ({ label, value }: { label: string; value: string }) => (
  <div><div className="text-xl font-bold tabular-nums">{value}</div><div className="text-[11px] text-muted">{label}</div></div>
)
const Empty = () => <div className="text-muted text-sm py-4 text-center">No data yet</div>
