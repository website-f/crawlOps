import { IconFilter, IconX } from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Area, AreaChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart,
  ReferenceLine, ResponsiveContainer, Sankey, Scatter, ScatterChart, Tooltip,
  XAxis, YAxis, ZAxis,
} from 'recharts'
import { FacetPanel, Gauge, Panel, Sparkline, StatTile, platformIconFor } from '../components/analytics'
import { PlatformIcon } from '../components/PlatformIcon'
import { fmtNum, get, post } from '../lib/api'
import { BRAND, SENTIMENT, SERIES } from '../lib/platform'

interface Topic { id: number; name: string }
interface Facet { value: string; count: number }
interface ExploreResp {
  facets: { platforms: Facet[]; sentiments: Facet[]; emotions: Facet[]; countries: Facet[]; topics: Facet[] }
  summary: { total: number; sentiment: { pos: number; neu: number; neg: number; pending: number }; reach: number; emv: number }
  timeseries: { day: string; pos: number; neu: number; neg: number }[]
}

const EMPTY_SEL = { platforms: [] as string[], sentiments: [] as string[], emotions: [] as string[], countries: [] as string[], topics: [] as string[] }
const EMOTION_COLOR: Record<string, string> = {
  joy: '#eda100', trust: '#1baf7a', anticipation: '#eb6834', surprise: '#e87ba4',
  fear: '#4a3aa7', anger: '#e34948', sadness: '#2a78d6', disgust: '#008300', neutral: '#898781',
}

export default function Analytics() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [days, setDays] = useState(30)
  const [sel, setSel] = useState(EMPTY_SEL)
  const [data, setData] = useState<ExploreResp | null>(null)
  const [health, setHealth] = useState<any>(null)
  const [crisis, setCrisis] = useState<any>(null)
  const [momentum, setMomentum] = useState<any[]>([])
  const [flow, setFlow] = useState<any>({ nodes: [], links: [] })
  const [pyramid, setPyramid] = useState<any>({ tiers: [], top_authors: [] })
  const [railOpen, setRailOpen] = useState(false)

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])

  const loadExplore = useCallback(async () => {
    const body = { topic_id: topicId || null, days, ...sel }
    try { setData(await post<ExploreResp>('/explore', body)) } catch { /* not ready */ }
  }, [topicId, days, sel])

  useEffect(() => { loadExplore() }, [loadExplore])

  useEffect(() => {
    const scope = `?days=${days}${topicId ? `&topic_id=${topicId}` : ''}`
    get(`/analytics/brand-health${scope}`).then(setHealth).catch(() => {})
    get(`/analytics/crisis${scope}`).then(setCrisis).catch(() => {})
    get(`/analytics/momentum${scope}`).then(setMomentum).catch(() => {})
    get(`/analytics/flow${scope}`).then(setFlow).catch(() => {})
    get(`/analytics/pyramid${scope}`).then(setPyramid).catch(() => {})
  }, [topicId, days])

  const toggle = (dim: keyof typeof EMPTY_SEL, v: string) =>
    setSel((s) => ({ ...s, [dim]: s[dim].includes(v) ? s[dim].filter((x) => x !== v) : [...s[dim], v] }))

  const activeCount = Object.values(sel).flat().length
  const s = data?.summary
  const net = s && s.total ? Math.round(((s.sentiment.pos - s.sentiment.neg) / s.total) * 100) : 0

  const emotionData = useMemo(
    () => (data?.facets.emotions || []).map((e) => ({ emotion: e.value, count: e.count })), [data])
  const sankeyData = useMemo(() => ({
    nodes: (flow.nodes || []).map((n: any) => ({ name: n.label })),
    links: flow.links || [],
  }), [flow])

  return (
    <div>
      {/* header */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <h2 className="font-semibold text-lg mr-auto">Analytics</h2>
        <button onClick={() => setRailOpen(!railOpen)}
          className="lg:hidden inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border bg-white border-grid">
          <IconFilter size={15} stroke={2} />Filters{activeCount > 0 && ` (${activeCount})`}
        </button>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
          className="border border-grid rounded-lg px-3 py-1.5 text-sm bg-white">
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <div className="flex rounded-lg border border-grid overflow-hidden">
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1.5 text-sm ${days === d ? 'bg-ink text-white' : 'bg-white'}`}>{d}d</button>
          ))}
        </div>
      </div>

      <div className="lg:grid lg:grid-cols-[240px_1fr] lg:gap-5">
        {/* facet rail */}
        <aside className={`${railOpen ? 'block' : 'hidden'} lg:block mb-4 lg:mb-0`}>
          <div className="bg-white border border-grid rounded-2xl p-3 lg:sticky lg:top-4">
            <div className="flex items-center mb-2">
              <span className="text-sm font-semibold">Cross-filter</span>
              {activeCount > 0 && (
                <button onClick={() => setSel(EMPTY_SEL)}
                  className="ml-auto inline-flex items-center gap-1 text-xs text-inksec hover:text-ink">
                  <IconX size={12} stroke={2} />clear
                </button>
              )}
            </div>
            <FacetPanel title="Platform" options={data?.facets.platforms || []}
              selected={sel.platforms} onToggle={(v) => toggle('platforms', v)}
              icon={platformIconFor} />
            <FacetPanel title="Sentiment"
              options={(data?.facets.sentiments || []).map((f) => ({ ...f, label: SENTIMENT[f.value as 'pos']?.label }))}
              selected={sel.sentiments} onToggle={(v) => toggle('sentiments', v)} />
            <FacetPanel title="Emotion" options={data?.facets.emotions || []}
              selected={sel.emotions} onToggle={(v) => toggle('emotions', v)} />
            <FacetPanel title="Topic" options={data?.facets.topics || []}
              selected={sel.topics} onToggle={(v) => toggle('topics', v)} />
            <FacetPanel title="Country" options={(data?.facets.countries || []).map((f) => ({ ...f, label: (f.value || '').toUpperCase() }))}
              selected={sel.countries} onToggle={(v) => toggle('countries', v)} />
          </div>
        </aside>

        {/* main */}
        <div className="space-y-5 min-w-0">
          {/* stat tiles */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatTile label="Mentions" value={(s?.total ?? 0).toLocaleString()} hint={activeCount ? 'filtered' : `last ${days} days`} />
            <StatTile label="Est. reach" value={fmtNum(s?.reach ?? 0)} />
            <StatTile label="Earned media value" value={`RM ${fmtNum(s?.emv ?? 0)}`} />
            <StatTile label="Net sentiment" value={`${net > 0 ? '+' : ''}${net}`} hint="(pos - neg) / total" />
          </div>

          {/* brand health + crisis */}
          <div className="grid md:grid-cols-2 gap-5">
            <Panel title="Brand Health Index" right={<span className="text-xs text-muted">weighted composite</span>}>
              {health ? (
                <div className="flex flex-col sm:flex-row gap-4 items-center">
                  <Gauge value={health.score} label={health.grade} />
                  <div className="flex-1 w-full space-y-2">
                    {Object.entries(health.components || {}).map(([k, v]: any) => (
                      <div key={k}>
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="capitalize text-inksec">{k}</span><span className="tabular-nums">{v}</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-grid overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${v}%`, background: '#2a78d6' }} />
                        </div>
                      </div>
                    ))}
                    <div className="pt-1"><Sparkline data={health.spark || []} /></div>
                  </div>
                </div>
              ) : <div className="text-muted text-sm py-8 text-center">No data yet.</div>}
            </Panel>

            <Panel title="Crisis Risk" right={<span className="text-xs text-muted">48h window</span>}>
              {crisis ? (
                <div className="flex flex-col sm:flex-row gap-4 items-center">
                  <Gauge value={crisis.risk} label={crisis.level}
                    band={(v) => v >= 75 ? '#d03b3b' : v >= 50 ? '#ec835a' : v >= 25 ? '#eda100' : '#0ca30c'} />
                  <div className="flex-1 w-full space-y-2">
                    {Object.entries(crisis.drivers || {}).map(([k, v]: any) => (
                      <div key={k}>
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="capitalize text-inksec">{k === 'negative' ? 'negative share' : k}</span>
                          <span className="tabular-nums">{v}</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-grid overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${(v / (k === 'negative' ? 50 : k === 'spike' ? 30 : 20)) * 100}%`, background: '#d03b3b' }} />
                        </div>
                      </div>
                    ))}
                    <div className="text-[11px] text-muted pt-1">
                      {crisis.neg_share_48h}% negative in last 48h · spike x{crisis.spike_ratio}
                    </div>
                  </div>
                </div>
              ) : <div className="text-muted text-sm py-8 text-center">No data yet.</div>}
            </Panel>
          </div>

          {/* sentiment over time */}
          <Panel title="Sentiment over time">
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={data?.timeseries || []}>
                <CartesianGrid stroke="#e1e0d9" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#898781' }} tickFormatter={(d) => d.slice(5)} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#898781' }} axisLine={false} tickLine={false} width={34} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                <Area type="monotone" dataKey="pos" stackId="1" stroke="#0ca30c" fill="#0ca30c" fillOpacity={0.75} name="Positive" />
                <Area type="monotone" dataKey="neu" stackId="1" stroke="#898781" fill="#c3c2b7" fillOpacity={0.6} name="Neutral" />
                <Area type="monotone" dataKey="neg" stackId="1" stroke="#d03b3b" fill="#d03b3b" fillOpacity={0.75} name="Negative" />
              </AreaChart>
            </ResponsiveContainer>
          </Panel>

          {/* emotions + momentum */}
          <div className="grid md:grid-cols-2 gap-5">
            <Panel title="Emotions">
              {emotionData.length ? (
                <ResponsiveContainer width="100%" height={240}>
                  <RadarChart data={emotionData} outerRadius={80}>
                    <PolarGrid stroke="#e1e0d9" />
                    <PolarAngleAxis dataKey="emotion" tick={{ fontSize: 11, fill: '#52514e' }} />
                    <Radar dataKey="count" stroke="#4a3aa7" fill="#4a3aa7" fillOpacity={0.4} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                  </RadarChart>
                </ResponsiveContainer>
              ) : <div className="text-muted text-sm py-16 text-center">No emotion data yet.</div>}
            </Panel>

            <Panel title="Topic momentum" right={<span className="text-xs text-muted">volume vs acceleration</span>}>
              {momentum.length ? (
                <ResponsiveContainer width="100%" height={240}>
                  <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                    <CartesianGrid stroke="#e1e0d9" />
                    <XAxis type="number" dataKey="volume" name="volume" tick={{ fontSize: 11, fill: '#898781' }} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
                    <YAxis type="number" dataKey="acceleration" name="accel %" tick={{ fontSize: 11, fill: '#898781' }} axisLine={false} tickLine={false} width={38} />
                    <ZAxis range={[60, 61]} />
                    <ReferenceLine y={0} stroke="#c3c2b7" />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }}
                      formatter={(v: any, n: any) => [v, n]} labelFormatter={() => ''} />
                    <Scatter data={momentum} fill="#2a78d6"
                      shape={(props: any) => {
                        const q = props.payload.quadrant
                        const c = q === 'Rising stars' ? '#0ca30c' : q === 'Emerging' ? '#eda100' : q === 'Steady' ? '#2a78d6' : '#d03b3b'
                        return <circle cx={props.cx} cy={props.cy} r={6} fill={c} stroke="#fcfcfb" strokeWidth={1.5} />
                      }} />
                  </ScatterChart>
                </ResponsiveContainer>
              ) : <div className="text-muted text-sm py-16 text-center">Need a few topics with volume.</div>}
              <div className="flex flex-wrap gap-3 mt-1 text-[11px] text-inksec">
                {[['Rising stars', '#0ca30c'], ['Emerging', '#eda100'], ['Steady', '#2a78d6'], ['Declining', '#d03b3b']].map(([l, c]) => (
                  <span key={l} className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: c }} />{l}</span>
                ))}
              </div>
            </Panel>
          </div>

          {/* sentiment flow Sankey */}
          <Panel title="Source to Topic to Sentiment flow">
            {sankeyData.links.length ? (
              <ResponsiveContainer width="100%" height={320}>
                <Sankey data={sankeyData} nodePadding={18} nodeWidth={12}
                  link={{ stroke: '#c3c2b7', strokeOpacity: 0.35 } as any}
                  node={{ fill: '#2a78d6' } as any}>
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                </Sankey>
              </ResponsiveContainer>
            ) : <div className="text-muted text-sm py-16 text-center">Needs enriched posts with topics + sentiment.</div>}
          </Panel>

          {/* pyramid + platform breakdown */}
          <div className="grid md:grid-cols-2 gap-5">
            <Panel title="Influence pyramid" right={<span className="text-xs text-muted">by reach</span>}>
              {pyramid.tiers?.length ? (
                <div className="space-y-2">
                  {pyramid.tiers.map((t: any, i: number) => (
                    <div key={t.tier} className="flex items-center gap-3">
                      <div className="h-8 rounded-lg flex items-center px-2 text-white text-xs font-medium justify-center"
                        style={{ width: `${100 - i * 18}%`, background: SERIES[['facebook', 'bluesky', 'hackernews', 'news'][i]] }}>
                        {t.tier}
                      </div>
                      <div className="text-xs text-inksec whitespace-nowrap">{t.authors} authors · {t.share}%</div>
                    </div>
                  ))}
                </div>
              ) : <div className="text-muted text-sm py-8 text-center">No author data yet.</div>}
            </Panel>

            <Panel title="Platform breakdown">
              <div className="space-y-1.5">
                {(data?.facets.platforms || []).slice(0, 8).map((p) => {
                  const max = Math.max(...(data?.facets.platforms || []).map((x) => x.count), 1)
                  const b = BRAND[p.value]
                  return (
                    <div key={p.value} className="flex items-center gap-2 text-sm">
                      <PlatformIcon platform={p.value} size={14} />
                      <span className="w-20 truncate text-inksec">{b?.label || p.value}</span>
                      <div className="flex-1 h-2 rounded-full bg-grid overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${(p.count / max) * 100}%`, background: b?.color || '#64748b' }} />
                      </div>
                      <span className="tabular-nums text-xs text-inksec w-10 text-right">{p.count}</span>
                    </div>
                  )
                })}
                {!data?.facets.platforms.length && <div className="text-muted text-sm py-6 text-center">No data yet.</div>}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </div>
  )
}
