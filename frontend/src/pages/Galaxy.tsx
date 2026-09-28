import { useEffect, useRef, useState } from 'react'
import { get } from '../lib/api'

interface Star { s: number; sent: number; e: number; age: number }
interface Topic { id: number; name: string }

export default function Galaxy() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [days, setDays] = useState(7)
  const [data, setData] = useState<{ stars: Star[]; platforms: string[] }>({ stars: [], platforms: [] })
  const [loading, setLoading] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)
  const starsRef = useRef<Star[]>([])

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])

  useEffect(() => {
    setLoading(true)
    const scope = `?days=${days}${topicId ? `&topic_id=${topicId}` : ''}`
    get<{ stars: Star[]; platforms: string[] }>(`/analytics/galaxy${scope}`)
      .then((d) => { setData(d); starsRef.current = d.stars })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [topicId, days])

  // animation loop — isolated to this page, cleaned up on unmount
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
    }
    resize()
    window.addEventListener('resize', resize)

    const hue = (s: number) => (s > 0.15 ? '#4ade80' : s < -0.15 ? '#f87171' : '#cbd5e1')
    let t = 0
    const draw = () => {
      const W = canvas.width, H = canvas.height, cx = W / 2, cy = H / 2
      const R = Math.min(W, H) / 2 - 24 * dpr
      ctx.fillStyle = '#0a0a14'
      ctx.fillRect(0, 0, W, H)
      // core glow
      const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, 90 * dpr)
      g.addColorStop(0, 'rgba(42,120,214,0.85)'); g.addColorStop(1, 'rgba(42,120,214,0)')
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, 90 * dpr, 0, Math.PI * 2); ctx.fill()
      const spin = reduce ? 0 : t * 0.0004
      for (const st of starsRef.current) {
        const ang = st.s * Math.PI * 2 + st.age * 0.7 + spin
        const r = 34 * dpr + st.age * R
        const x = cx + Math.cos(ang) * r
        const y = cy + Math.sin(ang) * r
        const size = (1 + st.e * 5) * dpr
        // twinkle
        const tw = reduce ? 1 : 0.7 + 0.3 * Math.sin(t * 0.003 + st.s * 40 + st.age * 12)
        ctx.globalAlpha = (0.5 + st.e * 0.5) * tw
        ctx.fillStyle = hue(st.sent)
        ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2); ctx.fill()
      }
      ctx.globalAlpha = 1
      t += 16
      rafRef.current = requestAnimationFrame(draw)
    }
    rafRef.current = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(rafRef.current); window.removeEventListener('resize', resize) }
  }, [])

  const counts = data.stars.reduce((a, s) => {
    const k = s.sent > 0.15 ? 'pos' : s.sent < -0.15 ? 'neg' : 'neu'
    a[k] = (a[k] || 0) + 1; return a
  }, {} as Record<string, number>)

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <div className="mr-auto">
          <h2 className="font-semibold text-lg">Conversation Galaxy</h2>
          <p className="text-sm text-inksec">Every recent post is a star. Angle = platform, distance from core = age, size = engagement, color = sentiment.</p>
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

      <div className="rounded-2xl border border-grid overflow-hidden bg-[#0a0a14]">
        <canvas ref={canvasRef} className="w-full block" style={{ height: '68vh' }} />
      </div>

      <div className="flex flex-wrap items-center gap-4 mt-3 text-sm">
        <span className="text-inksec">{data.stars.length.toLocaleString()} posts · {data.platforms.length} platforms</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#4ade80' }} />Positive {counts.pos || 0}</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#cbd5e1' }} />Neutral {counts.neu || 0}</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: '#f87171' }} />Negative {counts.neg || 0}</span>
        {loading && <span className="text-muted">loading…</span>}
        {!loading && !data.stars.length && <span className="text-muted">No posts in this window yet.</span>}
      </div>
    </div>
  )
}
