import { IconPlus, IconStar, IconStarFilled, IconTrash } from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Panel } from '../components/analytics'
import { del, get, post, put } from '../lib/api'
import { SLOT_ORDER, SERIES } from '../lib/platform'

interface Topic { id: number; name: string }
interface Entity { id: number; name: string; keywords: string[]; is_own_brand: boolean }
interface Compare { name: string; score: number; grade: string; total: number; is_brand: boolean }

const PALETTE = SLOT_ORDER.map((k) => SERIES[k])

export default function Competitors() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [entities, setEntities] = useState<Entity[]>([])
  const [sov, setSov] = useState<{ entities: string[]; days: any[] }>({ entities: [], days: [] })
  const [compare, setCompare] = useState<Compare[]>([])
  const [name, setName] = useState('')
  const [keywords, setKeywords] = useState('')

  useEffect(() => {
    get<Topic[]>('/topics').then((t) => { setTopics(t); if (t[0]) setTopicId(t[0].id) })
  }, [])

  const reload = useCallback(() => {
    if (!topicId) return
    get<Entity[]>(`/benchmark/entities?topic_id=${topicId}`).then(setEntities)
    get(`/benchmark/sov?topic_id=${topicId}&days=30`).then(setSov)
    get<Compare[]>(`/benchmark/compare?topic_id=${topicId}&days=14`).then(setCompare)
  }, [topicId])
  useEffect(() => { reload() }, [reload])

  const addEntity = async (isBrand: boolean) => {
    if (!name.trim() || !topicId) return
    await post('/benchmark/entities', {
      topic_id: topicId, name: name.trim(), is_own_brand: isBrand,
      keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
    })
    setName(''); setKeywords(''); reload()
  }

  const toggleBrand = async (e: Entity) => {
    await put(`/benchmark/entities/${e.id}`, { ...e, topic_id: topicId, is_own_brand: !e.is_own_brand })
    reload()
  }

  const maxScore = useMemo(() => Math.max(...compare.map((c) => c.score), 100), [compare])

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 flex-wrap">
        <h2 className="font-semibold text-lg mr-auto">Competitors &amp; Share of Voice</h2>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
          className="border border-grid rounded-lg px-3 py-1.5 text-sm bg-white">
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-5">
        <div className="space-y-5 min-w-0">
          <Panel title="Share of voice" right={<span className="text-xs text-muted">30 days, by mention volume</span>}>
            {sov.entities.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={sov.days}>
                  <CartesianGrid stroke="#e1e0d9" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#898781' }} tickFormatter={(d) => d.slice(5)} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#898781' }} axisLine={false} tickLine={false} width={34} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {sov.entities.map((name, i) => (
                    <Area key={name} type="monotone" dataKey={name} stackId="1"
                      stroke={PALETTE[i % PALETTE.length]} fill={PALETTE[i % PALETTE.length]} fillOpacity={0.7} />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            ) : <div className="text-muted text-sm py-16 text-center">Add your brand and competitors to see share of voice.</div>}
          </Panel>

          <Panel title="Brand health comparison" right={<span className="text-xs text-muted">14 days</span>}>
            {compare.length ? (
              <div className="space-y-2.5">
                {compare.map((c, i) => (
                  <div key={c.name} className="flex items-center gap-3">
                    <span className="w-32 truncate text-sm flex items-center gap-1">
                      {c.is_brand && <IconStarFilled size={12} className="text-[#eda100]" />}{c.name}
                    </span>
                    <div className="flex-1 h-6 rounded-lg bg-grid/50 overflow-hidden relative">
                      <div className="h-full rounded-lg flex items-center justify-end px-2 text-white text-xs font-medium"
                        style={{ width: `${(c.score / maxScore) * 100}%`,
                          background: c.name.startsWith('Market') ? '#898781' : PALETTE[i % PALETTE.length] }}>
                        {c.score}
                      </div>
                    </div>
                    <span className="text-xs text-inksec w-16 text-right">{c.grade}</span>
                  </div>
                ))}
              </div>
            ) : <div className="text-muted text-sm py-10 text-center">No entities yet.</div>}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Tracked entities">
            <div className="space-y-2 mb-3">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Brand / competitor name"
                className="w-full border border-grid rounded-lg px-3 py-2 text-sm" />
              <input value={keywords} onChange={(e) => setKeywords(e.target.value)}
                placeholder="keywords, comma separated (defaults to name)"
                className="w-full border border-grid rounded-lg px-3 py-2 text-sm font-mono text-[12px]" />
              <div className="flex gap-2">
                <button onClick={() => addEntity(true)}
                  className="flex-1 inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-[#eda100] text-white text-xs active:scale-[0.98]">
                  <IconStar size={13} stroke={2} />Add as my brand
                </button>
                <button onClick={() => addEntity(false)}
                  className="flex-1 inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-ink text-white text-xs active:scale-[0.98]">
                  <IconPlus size={13} stroke={2} />Add competitor
                </button>
              </div>
            </div>
            <div className="divide-y divide-grid/60">
              {entities.map((e) => (
                <div key={e.id} className="flex items-center gap-2 py-2 text-sm">
                  <button onClick={() => toggleBrand(e)} title="mark as own brand">
                    {e.is_own_brand ? <IconStarFilled size={14} className="text-[#eda100]" /> : <IconStar size={14} className="text-muted" />}
                  </button>
                  <div className="min-w-0">
                    <div className="font-medium truncate">{e.name}</div>
                    {e.keywords.length > 0 && <div className="text-[11px] text-muted truncate">{e.keywords.join(', ')}</div>}
                  </div>
                  <button onClick={() => del(`/benchmark/entities/${e.id}`).then(reload)}
                    className="ml-auto text-inksec hover:text-red-700"><IconTrash size={14} stroke={2} /></button>
                </div>
              ))}
              {entities.length === 0 && <div className="text-muted text-sm py-4 text-center">No entities tracked.</div>}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
