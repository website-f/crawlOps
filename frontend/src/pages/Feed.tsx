import { IconAdjustmentsHorizontal, IconAntennaOff, IconDownload, IconSearch } from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'
import PostCard from '../components/cards/PostCard'
import { PlatformIcon } from '../components/PlatformIcon'
import { PostHit, download, get } from '../lib/api'
import { BRAND, FEED_TABS } from '../lib/platform'

interface Topic { id: number; name: string }

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-grid bg-white p-4 mb-4 break-inside-avoid animate-pulse">
      <div className="flex items-center gap-2.5">
        <div className="w-10 h-10 rounded-full bg-grid/70" />
        <div className="space-y-1.5">
          <div className="h-3 w-32 rounded bg-grid/70" />
          <div className="h-2.5 w-20 rounded bg-grid/50" />
        </div>
      </div>
      <div className="mt-3 space-y-2">
        <div className="h-3 w-full rounded bg-grid/60" />
        <div className="h-3 w-4/5 rounded bg-grid/60" />
        <div className="h-3 w-2/3 rounded bg-grid/50" />
      </div>
    </div>
  )
}

export default function Feed() {
  const [tab, setTab] = useState('all')
  const [q, setQ] = useState('')
  const [qLive, setQLive] = useState('')
  const [topicId, setTopicId] = useState<number | ''>('')
  const [sentiment, setSentiment] = useState('')
  const [hasMedia, setHasMedia] = useState(false)
  const [minEng, setMinEng] = useState(0)
  const [days, setDays] = useState(0)
  const [sort, setSort] = useState('posted_ts:desc')
  const [showFilters, setShowFilters] = useState(false)
  const [hits, setHits] = useState<PostHit[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [topics, setTopics] = useState<Topic[]>([])

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])
  useEffect(() => { const t = setTimeout(() => setQ(qLive), 350); return () => clearTimeout(t) }, [qLive])

  const load = useCallback(async (pageNum: number, append: boolean) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(pageNum), per_page: '30', sort })
      if (q) params.set('q', q)
      if (tab !== 'all') params.set('platform', tab)
      if (topicId) params.set('topic_id', String(topicId))
      if (sentiment) params.set('sentiment', sentiment)
      if (hasMedia) params.set('has_media', 'true')
      if (minEng > 0) params.set('min_engagement', String(minEng))
      if (days > 0) params.set('since_ts', String(Math.floor(Date.now() / 1000) - days * 86400))
      const res = await get<{ hits: PostHit[]; total: number }>(`/posts?${params}`)
      setHits((prev) => (append ? [...prev, ...res.hits] : res.hits))
      setTotal(res.total)
    } catch { /* search not ready yet */ }
    setLoading(false)
  }, [q, tab, topicId, sentiment, hasMedia, minEng, days, sort])

  useEffect(() => { setPage(1); load(1, false) }, [load])
  useEffect(() => { const t = setInterval(() => { if (page === 1) load(1, false) }, 30000); return () => clearInterval(t) }, [load, page])

  const exportQuery = () => {
    const p = new URLSearchParams()
    if (topicId) p.set('topic_id', String(topicId))
    if (tab !== 'all') p.set('platform', tab)
    const s = p.toString()
    return s ? `?${s}` : ''
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <label className="relative flex-1 min-w-56">
          <IconSearch size={16} stroke={2}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <input value={qLive} onChange={(e) => setQLive(e.target.value)}
            placeholder="Search posts, authors, domains"
            className="w-full border border-grid rounded-xl pl-9 pr-3.5 py-2 text-sm bg-white
                       focus:outline-none focus:ring-2 focus:ring-slate-300" />
        </label>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
          className="border border-grid rounded-xl px-3 py-2 text-sm bg-white">
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <button onClick={() => setShowFilters(!showFilters)}
          className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm border active:scale-[0.98]
            ${showFilters ? 'bg-ink text-white border-ink' : 'bg-white border-grid'}`}>
          <IconAdjustmentsHorizontal size={16} stroke={2} />
          <span className="hidden sm:inline">Filters</span>
        </button>
        <button onClick={() => download(`/posts/export.csv${exportQuery()}`, 'crawlops.csv')}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm border bg-white border-grid active:scale-[0.98]"
          title="Export current topic/platform to CSV">
          <IconDownload size={16} stroke={2} />
          <span className="hidden sm:inline">Export</span>
        </button>
      </div>

      {showFilters && (
        <div className="flex items-center gap-x-4 gap-y-2 flex-wrap mb-3 p-3 bg-white border border-grid rounded-xl text-sm">
          <label className="flex items-center gap-1.5">Sentiment
            <select value={sentiment} onChange={(e) => setSentiment(e.target.value)} className="border border-grid rounded-lg px-2 py-1">
              <option value="">any</option><option value="pos">positive</option>
              <option value="neu">neutral</option><option value="neg">negative</option>
            </select>
          </label>
          <label className="flex items-center gap-1.5">Period
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="border border-grid rounded-lg px-2 py-1">
              <option value={0}>all time</option><option value={1}>24h</option>
              <option value={7}>7 days</option><option value={30}>30 days</option>
            </select>
          </label>
          <label className="flex items-center gap-1.5">Min engagement
            <input type="number" value={minEng} onChange={(e) => setMinEng(Number(e.target.value))}
              className="border border-grid rounded-lg px-2 py-1 w-20" />
          </label>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={hasMedia} onChange={(e) => setHasMedia(e.target.checked)} /> with media
          </label>
          <label className="flex items-center gap-1.5">Sort
            <select value={sort} onChange={(e) => setSort(e.target.value)} className="border border-grid rounded-lg px-2 py-1">
              <option value="posted_ts:desc">newest</option>
              <option value="engagement_total:desc">engagement</option>
              <option value="relevance:desc">relevance</option>
              <option value="reach:desc">reach</option>
            </select>
          </label>
        </div>
      )}

      <div className="flex items-center gap-1.5 mb-4 overflow-x-auto pb-1">
        {FEED_TABS.map((t) => {
          const b = BRAND[t]
          const active = tab === t
          return (
            <button key={t} onClick={() => setTab(t)}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[13px] font-medium
                whitespace-nowrap border transition active:scale-[0.97]
                ${active ? 'text-white border-transparent' : 'bg-white text-inksec border-grid hover:border-slate-300'}`}
              style={active ? { background: b ? b.color : '#0b0b0b' } : {}}>
              {t !== 'all' && <PlatformIcon platform={t} size={13} color={active ? '#fff' : undefined} />}
              {t === 'all' ? 'All' : b?.label ?? t}
            </button>
          )
        })}
        <span className="ml-auto self-center text-xs text-muted whitespace-nowrap pl-2">
          {total.toLocaleString()} posts
        </span>
      </div>

      {loading && hits.length === 0 && (
        <div className="columns-1 md:columns-2 xl:columns-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {!loading && hits.length === 0 && (
        <div className="text-center py-20 bg-white rounded-2xl border border-grid">
          <IconAntennaOff size={32} stroke={1.5} className="mx-auto text-muted" />
          <div className="mt-3 font-medium">No posts match</div>
          <p className="text-sm text-muted mt-1">
            Create a topic and the worker starts crawling within 30 seconds, or loosen the filters.
          </p>
        </div>
      )}

      <div className="columns-1 md:columns-2 xl:columns-3 gap-4">
        {hits.map((p) => <PostCard key={p.id} p={p} onMuted={() => load(1, false)} />)}
      </div>

      {hits.length < total && (
        <div className="text-center my-6">
          <button disabled={loading} onClick={() => { const n = page + 1; setPage(n); load(n, true) }}
            className="px-6 py-2.5 rounded-xl bg-ink text-white text-sm disabled:opacity-50 active:scale-[0.98]">
            {loading ? 'Loading' : 'Load more'}
          </button>
        </div>
      )}
    </div>
  )
}
