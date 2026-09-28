import {
  IconAntennaOff, IconDownload, IconFilter, IconSearch, IconX,
} from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import PostCard from '../components/cards/PostCard'
import { PlatformIcon } from '../components/PlatformIcon'
import { PostHit, download, get, post } from '../lib/api'
import { BRAND, SENTIMENT } from '../lib/platform'

interface Topic { id: number; name: string }
interface Facet { value: string; count: number }

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-grid bg-white p-4 mb-4 break-inside-avoid animate-pulse">
      <div className="flex items-center gap-2.5">
        <div className="w-10 h-10 rounded-full bg-grid/70" />
        <div className="space-y-1.5"><div className="h-3 w-32 rounded bg-grid/70" /><div className="h-2.5 w-20 rounded bg-grid/50" /></div>
      </div>
      <div className="mt-3 space-y-2"><div className="h-3 w-full rounded bg-grid/60" /><div className="h-3 w-4/5 rounded bg-grid/60" /><div className="h-3 w-2/3 rounded bg-grid/50" /></div>
    </div>
  )
}

const DATE_PRESETS: [string, number][] = [['All time', 0], ['24 hours', 1], ['7 days', 7], ['30 days', 30]]

export default function Feed() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [qLive, setQLive] = useState('')
  const [q, setQ] = useState('')
  const [platforms, setPlatforms] = useState<string[]>([])
  const [sentiments, setSentiments] = useState<string[]>([])
  const [days, setDays] = useState(0)
  const [hasMedia, setHasMedia] = useState(false)
  const [sort, setSort] = useState('posted_ts:desc')
  const [railOpen, setRailOpen] = useState(false)

  const [facets, setFacets] = useState<{ platforms: Facet[]; sentiments: Facet[] }>({ platforms: [], sentiments: [] })
  const [hits, setHits] = useState<PostHit[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])
  useEffect(() => { const t = setTimeout(() => setQ(qLive), 350); return () => clearTimeout(t) }, [qLive])

  // facet counts from the explore engine (cross-filtered)
  useEffect(() => {
    post('/explore', { topic_id: topicId || null, days: days || 3650, platforms, sentiments })
      .then((d: any) => setFacets({ platforms: d.facets.platforms, sentiments: d.facets.sentiments }))
      .catch(() => {})
  }, [topicId, days, platforms, sentiments])

  const load = useCallback(async (pageNum: number, append: boolean) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(pageNum), per_page: '30', sort })
      if (q) params.set('q', q)
      if (platforms.length) params.set('platform', platforms.join(','))
      if (sentiments.length) params.set('sentiment', sentiments.join(','))
      if (topicId) params.set('topic_id', String(topicId))
      if (hasMedia) params.set('has_media', 'true')
      if (days > 0) params.set('since_ts', String(Math.floor(Date.now() / 1000) - days * 86400))
      const res = await get<{ hits: PostHit[]; total: number }>(`/posts?${params}`)
      setHits((prev) => (append ? [...prev, ...res.hits] : res.hits))
      setTotal(res.total)
    } catch { /* search not ready */ }
    setLoading(false)
  }, [q, platforms, sentiments, topicId, hasMedia, days, sort])

  useEffect(() => { setPage(1); load(1, false) }, [load])
  useEffect(() => { const t = setInterval(() => { if (page === 1) load(1, false) }, 30000); return () => clearInterval(t) }, [load, page])

  const toggle = (arr: string[], set: (v: string[]) => void, v: string) =>
    set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])
  const activeCount = platforms.length + sentiments.length + (days ? 1 : 0) + (hasMedia ? 1 : 0)

  const exportQuery = () => {
    const p = new URLSearchParams()
    if (topicId) p.set('topic_id', String(topicId))
    if (platforms.length === 1) p.set('platform', platforms[0])
    const s = p.toString(); return s ? `?${s}` : ''
  }

  const Rail = (
    <div className="bg-white border border-grid rounded-2xl p-3 lg:sticky lg:top-4">
      <div className="flex items-center mb-2">
        <span className="text-sm font-semibold">Filters</span>
        {activeCount > 0 && (
          <button onClick={() => { setPlatforms([]); setSentiments([]); setDays(0); setHasMedia(false) }}
            className="ml-auto inline-flex items-center gap-1 text-xs text-inksec hover:text-ink"><IconX size={12} stroke={2} />clear</button>
        )}
      </div>

      <FacetBlock title="Sentiment">
        {['pos', 'neu', 'neg'].map((s) => {
          const f = facets.sentiments.find((x) => x.value === s)
          const on = sentiments.includes(s)
          return (
            <FacetRow key={s} on={on} onClick={() => toggle(sentiments, setSentiments, s)}
              dot={SENTIMENT[s as 'pos'].color} label={SENTIMENT[s as 'pos'].label} count={f?.count || 0} />
          )
        })}
      </FacetBlock>

      <FacetBlock title="Platform">
        {facets.platforms.slice(0, 14).map((f) => (
          <FacetRow key={f.value} on={platforms.includes(f.value)} onClick={() => toggle(platforms, setPlatforms, f.value)}
            icon={<PlatformIcon platform={f.value} size={13} />} label={BRAND[f.value]?.label || f.value} count={f.count} />
        ))}
      </FacetBlock>

      <FacetBlock title="Time">
        {DATE_PRESETS.map(([label, d]) => (
          <FacetRow key={label} on={days === d} onClick={() => setDays(d)} label={label} radio />
        ))}
      </FacetBlock>

      <label className="flex items-center gap-2 px-2 py-1.5 text-[13px] text-inksec cursor-pointer">
        <input type="checkbox" checked={hasMedia} onChange={(e) => setHasMedia(e.target.checked)} /> With media only
      </label>
    </div>
  )

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <label className="relative flex-1 min-w-56">
          <IconSearch size={16} stroke={2} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <input value={qLive} onChange={(e) => setQLive(e.target.value)} placeholder="Search posts, authors, domains"
            className="w-full border border-grid rounded-xl pl-9 pr-3.5 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-slate-300" />
        </label>
        <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
          className="border border-grid rounded-xl px-3 py-2 text-sm bg-white">
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="border border-grid rounded-xl px-3 py-2 text-sm bg-white">
          <option value="posted_ts:desc">Newest</option>
          <option value="engagement_total:desc">Engagement</option>
          <option value="relevance:desc">Relevance</option>
          <option value="reach:desc">Reach</option>
        </select>
        <button onClick={() => setRailOpen(!railOpen)}
          className={`lg:hidden inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm border ${railOpen ? 'bg-ink text-white border-ink' : 'bg-white border-grid'}`}>
          <IconFilter size={16} stroke={2} />{activeCount > 0 && activeCount}
        </button>
        <button onClick={() => download(`/posts/export.csv${exportQuery()}`, 'crawlops.csv')}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm border bg-white border-grid active:scale-[0.98]">
          <IconDownload size={16} stroke={2} /><span className="hidden sm:inline">Export</span>
        </button>
      </div>

      <div className="lg:grid lg:grid-cols-[236px_1fr] lg:gap-5">
        <aside className={`${railOpen ? 'block' : 'hidden'} lg:block mb-4 lg:mb-0`}>{Rail}</aside>

        <div className="min-w-0">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-inksec">{total.toLocaleString()} posts</span>
            {(platforms.length + sentiments.length) > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {[...platforms, ...sentiments].map((v) => (
                  <span key={v} className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-plane border border-grid">
                    {BRAND[v]?.label || SENTIMENT[v as 'pos']?.label || v}
                    <button onClick={() => { setPlatforms(platforms.filter((x) => x !== v)); setSentiments(sentiments.filter((x) => x !== v)) }}><IconX size={11} stroke={2} /></button>
                  </span>
                ))}
              </div>
            )}
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
              <p className="text-sm text-muted mt-1">Create a topic, or loosen the filters on the left.</p>
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
      </div>
    </div>
  )
}

function FacetBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-grid/70 pb-2 mb-2 last:border-0">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted mb-1 px-2">{title}</div>
      {children}
    </div>
  )
}

function FacetRow({ on, onClick, label, count, dot, icon, radio }: {
  on: boolean; onClick: () => void; label: string; count?: number; dot?: string; icon?: React.ReactNode; radio?: boolean
}) {
  return (
    <button onClick={onClick}
      className={`w-full flex items-center gap-2 px-2 py-1 rounded-lg text-[13px] transition ${on ? 'bg-ink text-white' : 'hover:bg-plane text-inksec'}`}>
      <span className={`w-3.5 h-3.5 ${radio ? 'rounded-full' : 'rounded'} border grid place-items-center shrink-0 ${on ? 'bg-white border-white' : 'border-grid'}`}>
        {on && <span className={`${radio ? 'w-1.5 h-1.5 rounded-full' : 'w-2 h-2 rounded-[2px]'} bg-ink`} />}
      </span>
      {dot && <span className="w-2 h-2 rounded-full shrink-0" style={{ background: dot }} />}
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="truncate flex-1 text-left capitalize">{label}</span>
      {count != null && <span className={`tabular-nums text-[11px] ${on ? 'text-white/80' : 'text-muted'}`}>{count}</span>}
    </button>
  )
}
