import { IconChartBar, IconChartLine, IconChartPie, IconExternalLink, IconTable } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { fmtNum, get } from '../lib/api'
import { SLOT_ORDER, SERIES } from '../lib/platform'

interface Topic { id: number; name: string }
type Row = { key: string; value: number }

const DIMENSIONS = ['platform', 'sentiment', 'emotion', 'issue', 'stance', 'country', 'topic', 'day', 'lang', 'domain']
const MEASURES: [string, string][] = [
  ['count', 'Post volume'], ['reach', 'Estimated reach'], ['emv', 'Earned media value'],
  ['engagement', 'Total engagement'], ['avg_sentiment', 'Avg sentiment'],
]
const PALETTE = SLOT_ORDER.map((k) => SERIES[k])

export default function DataExplorer() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [days, setDays] = useState(30)
  const [dimension, setDimension] = useState('platform')
  const [measure, setMeasure] = useState('count')
  const [chart, setChart] = useState<'bar' | 'line' | 'pie' | 'table'>('bar')
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])
  useEffect(() => {
    setLoading(true)
    const p = new URLSearchParams({ dimension, measure, days: String(days) })
    if (topicId) p.set('topic_id', String(topicId))
    get<{ rows: Row[] }>(`/analytics/pivot?${p}`).then((d) => setRows(d.rows)).catch(() => setRows([])).finally(() => setLoading(false))
  }, [dimension, measure, days, topicId])

  const total = useMemo(() => rows.reduce((a, r) => a + r.value, 0), [rows])
  const measureLabel = MEASURES.find(([m]) => m === measure)?.[1] || measure

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <div className="mr-auto">
          <h2 className="font-semibold text-lg">Data Explorer</h2>
          <p className="text-sm text-inksec">Slice the aggregate data any way you like — pick a dimension, a measure, and a chart.</p>
        </div>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
          className="border border-grid rounded-lg px-3 py-1.5 text-sm bg-white">
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <div className="flex rounded-lg border border-grid overflow-hidden">
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 text-sm ${days === d ? 'bg-ink text-white' : 'bg-white'}`}>{d}d</button>
          ))}
        </div>
        <a href={`${location.protocol}//${location.hostname}:8405`} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border bg-white border-grid" title="Open Metabase (full BI dashboards)">
          <IconExternalLink size={15} stroke={2} /><span className="hidden sm:inline">Full BI</span>
        </a>
      </div>

      <div className="bg-white border border-grid rounded-2xl p-4 mb-4">
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm">Group by (dimension)
            <select value={dimension} onChange={(e) => setDimension(e.target.value)}
              className="block mt-1 border border-grid rounded-lg px-2 py-1.5 text-sm capitalize">
              {DIMENSIONS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label className="text-sm">Measure
            <select value={measure} onChange={(e) => setMeasure(e.target.value)}
              className="block mt-1 border border-grid rounded-lg px-2 py-1.5 text-sm">
              {MEASURES.map(([m, l]) => <option key={m} value={m}>{l}</option>)}
            </select>
          </label>
          <div className="flex gap-1 ml-auto">
            {[['bar', IconChartBar], ['line', IconChartLine], ['pie', IconChartPie], ['table', IconTable]].map(([k, Ic]: any) => (
              <button key={k} onClick={() => setChart(k)} title={k}
                className={`p-2 rounded-lg border ${chart === k ? 'bg-ink text-white border-ink' : 'bg-white border-grid text-inksec'}`}>
                <Ic size={16} stroke={2} />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white border border-grid rounded-2xl p-4">
        <div className="text-sm text-inksec mb-3">{measureLabel} by {dimension} · {rows.length} groups · total {fmtNum(total)}</div>
        {loading ? <div className="text-muted text-sm py-16 text-center">Loading…</div>
          : !rows.length ? <div className="text-muted text-sm py-16 text-center">No data for this slice.</div>
          : chart === 'table' ? (
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-muted text-left"><th className="font-normal pb-1 capitalize">{dimension}</th><th className="font-normal text-right">{measureLabel}</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key} className="border-t border-grid/60">
                    <td className="py-1.5 capitalize">{r.key}</td>
                    <td className="text-right tabular-nums">{fmtNum(r.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : chart === 'pie' ? (
            <ResponsiveContainer width="100%" height={340}>
              <PieChart>
                <Pie data={rows.slice(0, 10)} dataKey="value" nameKey="key" cx="50%" cy="50%" outerRadius={120} label>
                  {rows.slice(0, 10).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : chart === 'line' ? (
            <ResponsiveContainer width="100%" height={340}>
              <LineChart data={rows}>
                <CartesianGrid stroke="#e1e0d9" vertical={false} />
                <XAxis dataKey="key" tick={{ fontSize: 11, fill: '#898781' }} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#898781' }} tickFormatter={(v) => fmtNum(v)} axisLine={false} tickLine={false} width={44} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                <Line dataKey="value" stroke="#2a78d6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={rows.slice(0, 20)} barCategoryGap="25%">
                <CartesianGrid stroke="#e1e0d9" vertical={false} />
                <XAxis dataKey="key" tick={{ fontSize: 11, fill: '#898781' }} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} interval={0} angle={-25} textAnchor="end" height={70} />
                <YAxis tick={{ fontSize: 11, fill: '#898781' }} tickFormatter={(v) => fmtNum(v)} axisLine={false} tickLine={false} width={44} />
                <Tooltip cursor={{ fill: 'rgba(11,11,11,0.04)' }} contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {rows.slice(0, 20).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
      </div>
    </div>
  )
}
