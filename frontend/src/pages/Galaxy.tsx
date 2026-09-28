import { useEffect, useState } from 'react'
import { ConversationGalaxy } from '../components/conversation-galaxy'
import { get } from '../lib/api'

interface Topic { id: number; name: string }
interface GalaxyData {
  title: string; core: number; grade: string; total: number; avgSentiment: number
  sources: { id: string; label: string; color: string; count: number }[]
  stars: { si: number; s: number; e: number; age: number }[]
  topics: { topic: string; n: number }[]
  trends: { topic: string; score: number }[]
}

export default function Galaxy() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [days, setDays] = useState(7)
  const [data, setData] = useState<GalaxyData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])
  useEffect(() => {
    setLoading(true)
    const scope = `?days=${days}${topicId ? `&topic_id=${topicId}` : ''}`
    get<GalaxyData>(`/analytics/galaxy${scope}`).then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [topicId, days])

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <div className="mr-auto">
          <h2 className="font-semibold text-lg">Conversation Galaxy</h2>
          <p className="text-sm text-inksec">The whole conversation as a living solar system — planets are sources, moons are sentiment, the outer belts are topics and emerging trends.</p>
        </div>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
          className="border border-grid rounded-lg px-3 py-1.5 text-sm bg-white">
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <div className="flex rounded-lg border border-grid overflow-hidden">
          {[1, 7, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 text-sm ${days === d ? 'bg-ink text-white' : 'bg-white'}`}>{d === 1 ? '24h' : `${d}d`}</button>
          ))}
        </div>
      </div>

      {data && data.sources.length > 0 ? (
        <ConversationGalaxy
          title={data.title} core={data.core} grade={data.grade} total={data.total}
          avgSentiment={data.avgSentiment} sources={data.sources}
          stars={data.stars} topics={data.topics} trends={data.trends} />
      ) : (
        <div className="rounded-2xl border border-grid bg-white text-center py-24 text-muted">
          {loading ? 'Loading galaxy…' : 'No posts in this window yet — create a topic and let the crawler run.'}
        </div>
      )}
    </div>
  )
}
