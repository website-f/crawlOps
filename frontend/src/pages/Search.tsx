import { IconSearch, IconSparkles, IconX } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import PostCard from '../components/cards/PostCard'
import { PostHit, get, post } from '../lib/api'

interface Topic { id: number; name: string }

export default function Search() {
  const [params, setParams] = useSearchParams()
  const similarId = params.get('similar')
  const [q, setQ] = useState(params.get('q') || '')
  const [topicId, setTopicId] = useState<string>('')
  const [topics, setTopics] = useState<Topic[]>([])
  const [hits, setHits] = useState<PostHit[]>([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [ran, setRan] = useState(false)

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])

  // "more like this" mode — triggered from a card's "similar" link
  useEffect(() => {
    if (!similarId) return
    setLoading(true); setErr(''); setRan(true)
    get<{ hits: PostHit[] }>(`/search/similar/${similarId}`)
      .then((r) => setHits(r.hits))
      .catch((e) => { setErr(prettyErr(e)); setHits([]) })
      .finally(() => setLoading(false))
  }, [similarId])

  const runSemantic = async () => {
    if (!q.trim()) return
    setLoading(true); setErr(''); setRan(true)
    if (similarId) setParams({ q })   // leave similar-mode
    try {
      const r = await post<{ hits: PostHit[] }>('/search/semantic', {
        query: q, topic_id: topicId ? Number(topicId) : null, limit: 40,
      })
      setHits(r.hits)
    } catch (e) { setErr(prettyErr(e)); setHits([]) } finally { setLoading(false) }
  }

  return (
    <div className="space-y-5 max-w-3xl mx-auto">
      <div>
        <div className="flex items-center gap-2">
          <IconSparkles size={20} stroke={2} className="text-[#7c3aed]" />
          <h1 className="text-lg font-bold">Semantic search</h1>
        </div>
        <p className="text-sm text-muted mt-1">
          Finds posts that <b>mean</b> what you asked for, even when they share no words with your query.
        </p>
      </div>

      <div className="bg-white border border-grid rounded-2xl p-4">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex-1 flex items-center gap-2 border border-grid rounded-xl px-3">
            <IconSearch size={16} stroke={2} className="text-muted shrink-0" />
            <input value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSemantic()}
              placeholder="e.g. concerns about AI job displacement"
              className="flex-1 py-2.5 text-sm outline-none bg-transparent" />
            {q && <button onClick={() => setQ('')} className="text-muted hover:text-ink"><IconX size={15} /></button>}
          </div>
          <select value={topicId} onChange={(e) => setTopicId(e.target.value)}
            className="border border-grid rounded-xl px-3 py-2.5 text-sm">
            <option value="">All topics</option>
            {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <button onClick={runSemantic} disabled={loading || !q.trim()}
            className="px-5 py-2.5 rounded-xl bg-ink text-white text-sm font-medium disabled:opacity-40 active:scale-[0.98]">
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </div>

      {/* Shown until the first search: the feature is useless without knowing what
          to type into it, and "semantic" tells a new operator nothing. */}
      {!ran && !err && (
        <div className="bg-white border border-grid rounded-2xl p-4 space-y-3">
          <div className="text-sm font-semibold">What this does differently</div>
          <p className="text-[13px] text-inksec">
            The keyword Feed matches letters: searching <i>“layoffs”</i> finds posts containing
            the word “layoffs”. This searches by meaning, so the same query also surfaces
            <i> “200 staff let go”</i>, <i>“restructuring exercise”</i> and
            <i> “pekerja diberhentikan”</i> — different words, same idea, including across
            languages.
          </p>
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="rounded-xl border border-grid p-3">
              <div className="text-[12px] font-semibold mb-1">Ask for it like a sentence</div>
              <ul className="text-[12px] text-inksec space-y-1">
                <li>• “customers complaining about delivery delays”</li>
                <li>• “people defending the price increase”</li>
                <li>• “concerns about water supply disruption”</li>
              </ul>
            </div>
            <div className="rounded-xl border border-grid p-3">
              <div className="text-[12px] font-semibold mb-1">What comes back</div>
              <p className="text-[12px] text-inksec">
                Up to 40 posts ranked by closeness, each tagged with a <b>% match</b>. Roughly:
                above 60% is on-topic, 45–60% is related, below that is drifting. There is no
                “no results” — it always returns the closest posts it has, so judge by the score.
              </p>
            </div>
          </div>
          <p className="text-[12px] text-muted">
            Use the <b>similar</b> link on any post card to find near-duplicates and the rest of a
            story. Only enriched posts are searchable, so a very recent crawl may not be included yet.
          </p>
        </div>
      )}

      {similarId && (
        <div className="flex items-center gap-2 text-sm text-inksec">
          <IconSparkles size={15} stroke={2} className="text-[#7c3aed]" />
          Showing posts similar to <span className="font-mono">#{similarId}</span>
          <button onClick={() => { setParams({}); setHits([]); setRan(false) }}
            className="text-[#2a78d6] hover:underline">clear</button>
        </div>
      )}

      {err && (
        <div className="bg-[#fef2f2] border border-[#fecaca] rounded-xl p-3 text-sm text-[#991b1b]">{err}</div>
      )}

      {loading && <div className="py-16 grid place-items-center text-muted">Searching…</div>}

      {!loading && ran && !err && hits.length === 0 && (
        <div className="py-16 grid place-items-center text-muted text-sm">No matches yet — try broader wording, or wait for more posts to be enriched.</div>
      )}

      {!loading && hits.length > 0 && (
        <div className="columns-1 md:columns-2 gap-4">
          {hits.map((p) => (
            <div key={p.id} className="relative break-inside-avoid">
              {p.score != null && (
                <span className="absolute z-10 top-2 right-2 text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-[#7c3aed] text-white shadow">
                  {Math.round(p.score * 100)}% match
                </span>
              )}
              <PostCard p={p} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function prettyErr(e: unknown): string {
  const msg = String(e)
  if (msg.includes('503')) {
    if (msg.includes('embedding') || msg.includes('AI Engine'))
      return 'Semantic search needs an embedding model (768-dimension, e.g. nomic-embed-text). '
        + 'In AI Engine, set the "embed" task to a real embedding model — a chat model like '
        + 'gpt-4o-mini or deepseek-flash cannot produce embeddings.'
    if (msg.includes('pgvector'))
      return 'Semantic search needs the pgvector database image. Rebuild the postgres service.'
    return 'Search is temporarily unavailable.'
  }
  if (msg.includes('404')) return 'That post has no embedding yet (enrichment may still be pending).'
  return msg.replace(/^Error:\s*/, '')
}
