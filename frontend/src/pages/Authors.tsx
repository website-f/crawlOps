import { IconArrowLeft, IconSearch, IconUsersGroup, IconWorld } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import PostCard from '../components/cards/PostCard'
import { PlatformIcon } from '../components/PlatformIcon'
import { PostHit, fmtNum, get } from '../lib/api'

interface TopAuthor {
  author_name: string; author_handle: string; platform: string
  posts: number; reach: number; avg_sentiment: number | null
}
interface Profile {
  identity: { name: string; handle: string; display?: string }
  platforms: { platform: string; posts: number; reach: number; handles: string[]; verified: boolean }[]
  cross_platform: boolean
  topics: { topic: string; count: number }[]
  sentiment: { pos: number; neu: number; neg: number }
  totals: { posts: number; reach: number; platforms: number }
  posts: PostHit[]
}

const SENT = { pos: '#0a7d0a', neu: '#898781', neg: '#d03b3b' }

export default function Authors() {
  const [topics, setTopics] = useState<{ id: number; name: string }[]>([])
  const [topicId, setTopicId] = useState('')
  const [top, setTop] = useState<TopAuthor[]>([])
  const [q, setQ] = useState('')
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { get('/topics').then(setTopics).catch(() => {}) }, [])
  const loadTop = () => get<TopAuthor[]>(`/authors/top?limit=40${topicId ? `&topic_id=${topicId}` : ''}`).then(setTop).catch(() => {})
  useEffect(() => { loadTop() }, [topicId])

  const openAuthor = async (name: string, handle: string) => {
    setLoading(true)
    try {
      const p = new URLSearchParams()
      if (name) p.set('name', name)
      if (handle) p.set('handle', handle)
      setProfile(await get<Profile>(`/authors/profile?${p.toString()}`))
    } finally { setLoading(false) }
  }

  if (profile) {
    const s = profile.sentiment
    const tot = s.pos + s.neu + s.neg || 1
    return (
      <div className="space-y-5 max-w-4xl mx-auto">
        <button onClick={() => setProfile(null)} className="inline-flex items-center gap-1 text-sm text-inksec hover:text-ink">
          <IconArrowLeft size={15} stroke={2} />Back to authors
        </button>
        <div className="bg-white border border-grid rounded-2xl p-5">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-lg font-bold">{profile.identity.display || profile.identity.name || profile.identity.handle}</h1>
            {profile.cross_platform && (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-accent/10 text-accent">
                <IconWorld size={12} stroke={2} />posts on {profile.totals.platforms} platforms
              </span>
            )}
          </div>
          <div className="flex gap-6 mt-3 text-sm">
            <div><span className="text-2xl font-bold tabular-nums">{fmtNum(profile.totals.posts)}</span><div className="text-xs text-muted">posts</div></div>
            <div><span className="text-2xl font-bold tabular-nums">{fmtNum(profile.totals.reach)}</span><div className="text-xs text-muted">est. reach</div></div>
          </div>
          {/* per-platform presence — the "which other platforms does this author post on" answer */}
          <div className="grid sm:grid-cols-2 gap-2 mt-4">
            {profile.platforms.map((pl) => (
              <div key={pl.platform} className="flex items-center gap-2 border border-grid rounded-xl px-3 py-2">
                <PlatformIcon platform={pl.platform} size={20} />
                <span className="capitalize font-medium text-sm">{pl.platform}</span>
                {pl.verified && <span className="text-[10px] text-[#2a78d6]">verified</span>}
                <span className="ml-auto text-xs text-muted tabular-nums">{pl.posts} posts · {fmtNum(pl.reach)} reach</span>
              </div>
            ))}
          </div>
          {/* sentiment mix */}
          <div className="mt-4">
            <div className="text-xs text-muted mb-1">sentiment of their posts</div>
            <div className="flex h-2.5 rounded-full overflow-hidden bg-plane">
              {(['pos', 'neu', 'neg'] as const).map((k) => (
                <div key={k} style={{ width: `${(100 * s[k]) / tot}%`, background: SENT[k] }} />
              ))}
            </div>
          </div>
          {profile.topics.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-muted mb-1.5">what they post about</div>
              <div className="flex flex-wrap gap-1.5">
                {profile.topics.map((t) => (
                  <span key={t.topic} className="text-xs px-2 py-0.5 rounded-full bg-grid/60 text-inksec">{t.topic} <span className="text-muted">{t.count}</span></span>
                ))}
              </div>
            </div>
          )}
        </div>
        <div>
          <div className="text-sm font-medium mb-2">Their posts</div>
          <div className="columns-1 md:columns-2 gap-4">
            {profile.posts.map((p) => <div key={p.id} className="break-inside-avoid"><PostCard p={p} /></div>)}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <IconUsersGroup size={20} stroke={2} className="text-[#2a78d6]" />
        <h1 className="text-lg font-bold">Author intelligence</h1>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value)}
          className="ml-auto border border-grid rounded-lg px-2 py-1.5 text-sm">
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>
      <p className="text-sm text-muted -mt-2">Most active voices on your topics. Open one to see every platform they post on and everything they've said. Cross-platform match is heuristic (by name/handle).</p>

      <div className="flex items-center gap-2 border border-grid rounded-xl px-3 bg-white max-w-md">
        <IconSearch size={16} stroke={2} className="text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && q.trim() && openAuthor(q.trim(), q.trim())}
          placeholder="Look up an author by name or @handle" className="flex-1 py-2.5 text-sm outline-none bg-transparent" />
        <button onClick={() => q.trim() && openAuthor(q.trim(), q.trim())} className="text-sm text-[#2a78d6] font-medium">Look up</button>
      </div>

      {loading && <div className="py-10 text-center text-muted">Loading…</div>}

      <div className="bg-white border border-grid rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] text-muted text-left border-b border-grid">
            <th className="font-normal px-4 py-2">author</th><th className="font-normal">platform</th>
            <th className="font-normal text-right">posts</th><th className="font-normal text-right">reach</th>
            <th className="font-normal text-right px-4">sentiment</th>
          </tr></thead>
          <tbody>
            {top.map((a, i) => (
              <tr key={i} className="border-b border-grid/50 hover:bg-plane cursor-pointer"
                onClick={() => openAuthor(a.author_name, a.author_handle)}>
                <td className="px-4 py-2 font-medium">{a.author_name || a.author_handle || 'unknown'}</td>
                <td><span className="inline-flex items-center gap-1.5"><PlatformIcon platform={a.platform} size={16} /><span className="capitalize text-inksec">{a.platform}</span></span></td>
                <td className="text-right tabular-nums">{fmtNum(a.posts)}</td>
                <td className="text-right tabular-nums text-muted">{fmtNum(a.reach)}</td>
                <td className="text-right px-4 tabular-nums" style={{ color: a.avg_sentiment == null ? '#898781' : a.avg_sentiment > 0.15 ? SENT.pos : a.avg_sentiment < -0.15 ? SENT.neg : SENT.neu }}>
                  {a.avg_sentiment == null ? '—' : a.avg_sentiment.toFixed(2)}
                </td>
              </tr>
            ))}
            {top.length === 0 && !loading && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted">No authors yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
