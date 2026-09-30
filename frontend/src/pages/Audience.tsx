import { IconInfoCircle } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { Panel } from '../components/analytics'
import { fmtNum, get } from '../lib/api'
import { SENTIMENT } from '../lib/platform'

interface Topic { id: number; name: string }
interface Issue {
  issue: string; total: number
  stance: { support: number; oppose: number; neutral: number }
  sentiment: { pos: number; neu: number; neg: number }
  avg_sentiment: number; resonance: number
  top_regions: { name: string; count: number }[]
}

const STANCE_COLOR = { support: '#0ca30c', neutral: '#898781', oppose: '#d03b3b' }

function SplitBar({ parts }: { parts: [string, number, string][] }) {
  const total = parts.reduce((a, [, v]) => a + v, 0) || 1
  return (
    <div className="flex h-2 rounded-full overflow-hidden w-full">
      {parts.map(([k, v, c]) => v > 0 ? <div key={k} style={{ width: `${(v / total) * 100}%`, background: c }} /> : null)}
    </div>
  )
}

export default function Audience() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [days, setDays] = useState(30)
  const [issues, setIssues] = useState<Issue[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])
  useEffect(() => {
    setLoading(true)
    const scope = `?days=${days}${topicId ? `&topic_id=${topicId}` : ''}`
    get<{ issues: Issue[] }>(`/analytics/issues${scope}`).then((d) => setIssues(d.issues)).catch(() => {}).finally(() => setLoading(false))
  }, [topicId, days])

  const maxRes = Math.max(1, ...issues.map((i) => i.resonance))

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <div className="mr-auto">
          <h1 className="text-lg font-bold tracking-tight">Audience &amp; Issues</h1>
          <p className="text-[13px] text-inksec mt-0.5">Which issues the public is talking about, how they lean, and what resonates — aggregate and anonymous.</p>
        </div>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
          className="border border-grid rounded-xl px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition">
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <div className="flex rounded-xl border border-grid overflow-hidden">
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 text-sm transition ${days === d ? 'bg-ink text-white' : 'bg-white hover:bg-plane'}`}>{d}d</button>
          ))}
        </div>
      </div>

      <div className="flex items-start gap-2 text-[13px] text-inksec bg-plane border border-grid rounded-xl px-3 py-2 mb-4">
        <IconInfoCircle size={16} stroke={2} className="shrink-0 mt-0.5 text-muted" />
        These are aggregate opinion segments from public posts — counts and regions only. CrawlOps does not build per-person profiles or targeting lists.
      </div>

      {loading && <div className="py-16 grid place-items-center"><span className="w-6 h-6 rounded-full border-2 border-grid border-t-accent animate-spin" /></div>}

      {!loading && !issues.length && (
        <div className="grid place-items-center gap-2 py-16 bg-white rounded-2xl border border-grid shadow-card text-center">
          <IconInfoCircle size={24} stroke={1.5} className="text-muted" />
          <p className="text-muted text-sm max-w-md">
            No issue data yet. Enable an AI provider so the judge can classify posts by issue and stance,
            then let the crawler run. Edit the issue list in Settings.
          </p>
        </div>
      )}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {issues.map((it) => (
          <Panel key={it.issue} title={it.issue} right={<span className="text-xs text-muted">{fmtNum(it.total)} posts</span>}>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-[11px] text-inksec mb-1">
                  <span>Stance</span>
                  <span>{Math.round((it.stance.support / (it.total || 1)) * 100)}% support · {Math.round((it.stance.oppose / (it.total || 1)) * 100)}% oppose</span>
                </div>
                <SplitBar parts={[['support', it.stance.support, STANCE_COLOR.support], ['neutral', it.stance.neutral, STANCE_COLOR.neutral], ['oppose', it.stance.oppose, STANCE_COLOR.oppose]]} />
              </div>
              <div>
                <div className="flex justify-between text-[11px] text-inksec mb-1">
                  <span>Sentiment</span>
                  <span className={it.avg_sentiment > 0.1 ? 'text-positive' : it.avg_sentiment < -0.1 ? 'text-danger' : ''}>{it.avg_sentiment > 0 ? '+' : ''}{it.avg_sentiment}</span>
                </div>
                <SplitBar parts={[['pos', it.sentiment.pos, SENTIMENT.pos.color], ['neu', it.sentiment.neu, SENTIMENT.neu.color], ['neg', it.sentiment.neg, SENTIMENT.neg.color]]} />
              </div>
              <div>
                <div className="flex justify-between text-[11px] text-inksec mb-1">
                  <span>Resonance</span><span>avg {fmtNum(it.resonance)} eng/post</span>
                </div>
                <div className="h-2 rounded-full bg-grid overflow-hidden">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${(it.resonance / maxRes) * 100}%` }} />
                </div>
              </div>
              {it.top_regions.length > 0 && (
                <div className="text-[11px] text-inksec">
                  <span className="text-muted">Top regions: </span>
                  {it.top_regions.map((r) => `${r.name} (${r.count})`).join(' · ')}
                </div>
              )}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  )
}
