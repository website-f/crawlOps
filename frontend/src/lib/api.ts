const TOKEN_KEY = 'crawlops_token'
export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

function authHeaders(): Record<string, string> {
  const t = getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

export async function api<T = any>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(opts?.headers || {}) },
    ...opts,
  })
  if (r.status === 401) {
    clearToken()
    if (!location.pathname.startsWith('/login')) location.href = '/login'
    throw new Error('unauthorized')
  }
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json()
}

/** Authenticated image fetch → object URL (for live frames behind auth). */
export async function blobUrl(path: string): Promise<string> {
  const r = await fetch(`/api${path}`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`${r.status}`)
  return URL.createObjectURL(await r.blob())
}

/** Authenticated file download (blob) — for CSV export, since <a> can't send headers. */
export async function download(path: string, filename: string): Promise<void> {
  const r = await fetch(`/api${path}`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`${r.status}`)
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export const get = <T = any>(path: string) => api<T>(path)
export const post = <T = any>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
export const put = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(body) })
export const del = <T = any>(path: string) => api<T>(path, { method: 'DELETE' })

export interface PostHit {
  id: number
  platform: string
  topic_id: number
  title: string
  text: string
  author_key: string
  author_name: string
  author_handle: string
  author_avatar: string
  author_verified: boolean
  domain: string
  url: string
  lang: string
  sentiment: 'pos' | 'neu' | 'neg' | null
  sentiment_score: number | null
  relevance: number | null
  topics: string[]
  media: { kind: string; src_url: string; cache_key?: string; thumb_key?: string; thumb_src?: string; youtube_id?: string }[]
  has_media: boolean
  engagement: Record<string, number>
  engagement_total: number
  reach: number | null
  emv: number | null
  posted_ts: number
  cluster_id: number | null
  suppression_watch?: boolean
  score?: number   // cosine similarity, set by semantic search / "more like this"
}

export const mediaUrl = (m: PostHit['media'][number]) =>
  m.cache_key ? `/api/media/${m.cache_key}` : m.src_url

export const thumbUrl = (m: PostHit['media'][number]) =>
  m.thumb_key ? `/api/media/${m.thumb_key}` : m.thumb_src || mediaUrl(m)

export const timeAgo = (ts: number) => {
  if (!ts) return ''
  const s = Math.max(1, Math.floor(Date.now() / 1000 - ts))
  if (s < 3600) return `${Math.floor(s / 60)}m`
  if (s < 86400) return `${Math.floor(s / 3600)}h`
  return `${Math.floor(s / 86400)}d`
}

export const fmtNum = (n: number | null | undefined) => {
  if (n == null) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}
