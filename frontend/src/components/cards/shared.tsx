import { IconArrowsDiagonal, IconBookmark, IconEye, IconExternalLink, IconLock, IconPlayerPlayFilled, IconPlus, IconSparkles, IconVolumeOff } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PostHit, fmtNum, get, mediaUrl, post, thumbUrl, timeAgo } from '../../lib/api'
import { SENTIMENT } from '../../lib/platform'
import { usePostDetail } from '../postdetail-ctx'

// tag palette loaded once, shared across cards, so label chips can be colored
let _palette: { name: string; color: string }[] = []
let _paletteLoaded = false
function usePalette(): [{ name: string; color: string }[], () => void] {
  const [, force] = useState(0)
  useEffect(() => {
    if (_paletteLoaded) return
    _paletteLoaded = true
    get<{ name: string; color: string }[]>('/tags').then((t) => { _palette = t; force((n) => n + 1) }).catch(() => {})
  }, [])
  return [_palette, () => force((n) => n + 1)]
}
const tagColor = (name: string) => _palette.find((t) => t.name === name)?.color || '#64748b'

/** In-feed YouTube: thumbnail + play button, swaps to the embedded player on click
 *  (lite pattern — no iframe until the user actually wants to watch). */
function YouTubeEmbed({ id, thumb }: { id: string; thumb: string }) {
  const [play, setPlay] = useState(false)
  if (play) {
    return (
      <iframe className="w-full aspect-video" allow="autoplay; encrypted-media; picture-in-picture"
        allowFullScreen title="YouTube video"
        src={`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0`} />
    )
  }
  return (
    <button onClick={() => setPlay(true)} className="relative block w-full group" title="Play video">
      <img src={thumb} loading="lazy"
        className="w-full aspect-video object-cover bg-black"
        onError={(e) => ((e.target as HTMLImageElement).src = `https://i.ytimg.com/vi/${id}/hqdefault.jpg`)} />
      <span className="absolute inset-0 grid place-items-center">
        <span className="w-16 h-11 rounded-xl bg-[#f00]/90 grid place-items-center transition group-hover:bg-[#f00]">
          <IconPlayerPlayFilled size={22} color="#fff" />
        </span>
      </span>
    </button>
  )
}

export function Avatar({ src, name, size = 40, round = true }: { src?: string; name: string; size?: number; round?: boolean }) {
  const initial = (name || '?').replace(/^[@u]\//, '').charAt(0).toUpperCase()
  return src ? (
    <img src={src} width={size} height={size} referrerPolicy="no-referrer"
      className={`${round ? 'rounded-full' : 'rounded-lg'} object-cover shrink-0`}
      style={{ width: size, height: size }}
      onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
  ) : (
    <div className={`${round ? 'rounded-full' : 'rounded-lg'} shrink-0 grid place-items-center bg-grid text-inksec font-semibold`}
      style={{ width: size, height: size, fontSize: size * 0.42 }}>{initial}</div>
  )
}

export function MediaGrid({ p, dark = false }: { p: PostHit; dark?: boolean }) {
  const items = (p.media || []).filter((m) => mediaUrl(m))
  if (!items.length) return null
  const cls = items.length === 1 ? 'grid-cols-1' : 'grid-cols-2'
  return (
    <div className={`grid ${cls} gap-0.5 mt-2 rounded-xl overflow-hidden`}>
      {items.slice(0, 4).map((m, i) =>
        m.kind === 'video' ? (
          m.youtube_id ? (
            <YouTubeEmbed key={i} id={m.youtube_id} thumb={thumbUrl(m)} />
          ) : m.cache_key ? (
            <video key={i} controls preload="none" poster={m.thumb_key ? `/api/media/${m.thumb_key}` : undefined}
              className="w-full max-h-96 bg-black" src={`/api/media/${m.cache_key}`} />
          ) : (
            <a key={i} href={p.url} target="_blank" rel="noreferrer" className="relative block">
              <img src={thumbUrl(m)} className="w-full aspect-video object-cover bg-plane" />
              <span className="absolute inset-0 grid place-items-center">
                <IconPlayerPlayFilled size={28} color="#fff" className="drop-shadow" />
              </span>
            </a>
          )
        ) : (
          <img key={i} src={mediaUrl(m)} loading="lazy" referrerPolicy="no-referrer"
            className={`w-full object-cover ${items.length === 1 ? 'max-h-[28rem]' : 'aspect-square'} ${dark ? 'bg-neutral-800' : 'bg-plane'}`}
            onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
        ),
      )}
    </div>
  )
}

/** Normalized CrawlOps footer under every native card: enrichment + actions. */
export function OpsFooter({ p, onMuted }: { p: PostHit; onMuted?: () => void }) {
  const { open } = usePostDetail()
  const [palette] = usePalette()
  const [labels, setLabels] = useState<string[]>(p.labels || [])
  const [sentiment, setSentiment] = useState(p.sentiment)
  const [locked, setLocked] = useState(!!p.sentiment_locked)
  const [menu, setMenu] = useState(false)
  const [newTag, setNewTag] = useState('')
  const s = sentiment ? SENTIMENT[sentiment] : null

  const mute = async (mode: 'hide' | 'watch') => {
    if (!p.author_key) return
    await post('/suppression', { platform: p.platform, author_key: p.author_key, mode, reason: 'from feed' })
    onMuted?.()
  }
  const toggleLabel = async (name: string) => {
    const on = labels.includes(name)
    const next = on ? labels.filter((x) => x !== name) : [...labels, name]
    setLabels(next)
    await post('/posts/tag', { ids: [p.id], add: on ? [] : [name], remove: on ? [name] : [] }).catch(() => {})
  }
  const addNewTag = async () => {
    const name = newTag.trim(); if (!name) return
    setNewTag('')
    await post('/tags', { name, color: '#2a78d6' }).catch(() => {})
    if (!palette.find((t) => t.name === name)) palette.push({ name, color: '#2a78d6' })
    toggleLabel(name)
  }
  const setSent = async (val: string) => {
    setSentiment((val || null) as PostHit['sentiment']); setLocked(!!val); setMenu(false)
    await post(`/posts/${p.id}/sentiment`, { sentiment: val }).catch(() => {})
  }

  return (
    <div className="relative">
      {labels.length > 0 && (
        <div className="flex flex-wrap gap-1 px-3 pt-1.5">
          {labels.map((l) => (
            <span key={l} className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full text-white"
              style={{ background: tagColor(l) }}>{l}</span>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5 border-t border-grid bg-plane/60 text-[11px] text-inksec">
        {s ? (
          <span className="inline-flex items-center gap-1 font-medium" style={{ color: s.color }}>
            <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />{s.label}
            {locked && <IconLock size={10} stroke={2} title="manually set" />}
          </span>
        ) : (
          <span className="text-muted">analyzing</span>
        )}
        {p.relevance != null && <span title="relevance score">rel {p.relevance}</span>}
        {p.reach != null && <span title="estimated reach">~{fmtNum(p.reach)} reach</span>}
        {!!p.custom_score && <span title="custom impact score" className="font-semibold text-accent">impact {p.custom_score}</span>}
        {(p.topics || []).slice(0, 2).map((t) => (
          <span key={t} className="px-1.5 py-0.5 rounded-full bg-grid/60 text-inksec">{t}</span>
        ))}
        {p.suppression_watch && <span className="text-warn font-medium">watched</span>}
        <span className="flex-1" />
        <button onClick={() => setMenu((m) => !m)} title="tag / correct sentiment"
          className={`inline-flex items-center gap-1 active:scale-[0.96] ${menu ? 'text-ink' : 'hover:text-ink'}`}>
          <IconBookmark size={13} stroke={2} />tag
        </button>
        <button onClick={() => open(p)} title="open full detail + this author's posts"
          className="inline-flex items-center gap-1 hover:text-ink active:scale-[0.96]">
          <IconArrowsDiagonal size={13} stroke={2} />details
        </button>
        <button onClick={() => mute('watch')} title="keep visible, exclude from analytics"
          className="inline-flex items-center gap-1 hover:text-ink active:scale-[0.96]">
          <IconEye size={13} stroke={2} />watch
        </button>
        <button onClick={() => mute('hide')} title="hide author everywhere (internal shadowban)"
          className="inline-flex items-center gap-1 hover:text-danger active:scale-[0.96]">
          <IconVolumeOff size={13} stroke={2} />mute
        </button>
        <Link to={`/search?similar=${p.id}`} title="find semantically similar posts"
          className="inline-flex items-center gap-1 hover:text-ink active:scale-[0.96]">
          <IconSparkles size={13} stroke={2} />similar
        </Link>
        {p.url && (
          <a href={p.url} target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1 font-medium hover:text-ink">
            <IconExternalLink size={13} stroke={2} />open
          </a>
        )}
      </div>

      {menu && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setMenu(false)} />
          <div className="absolute right-2 bottom-9 z-30 w-56 bg-white border border-grid rounded-xl shadow-xl p-2.5 text-[12px]">
            <div className="text-[10px] uppercase tracking-wide text-muted mb-1">Sentiment</div>
            <div className="flex gap-1 mb-2">
              {(['pos', 'neu', 'neg'] as const).map((k) => (
                <button key={k} onClick={() => setSent(sentiment === k && locked ? '' : k)}
                  className={`flex-1 py-1 rounded-lg border text-[11px] ${sentiment === k ? 'text-white' : 'text-inksec'}`}
                  style={sentiment === k ? { background: SENTIMENT[k].color, borderColor: SENTIMENT[k].color } : {}}>
                  {SENTIMENT[k].label}
                </button>
              ))}
            </div>
            <div className="text-[10px] uppercase tracking-wide text-muted mb-1">Tags</div>
            <div className="flex flex-wrap gap-1 mb-2 max-h-24 overflow-y-auto">
              {palette.map((t) => (
                <button key={t.name} onClick={() => toggleLabel(t.name)}
                  className={`text-[11px] px-1.5 py-0.5 rounded-full border ${labels.includes(t.name) ? 'text-white' : 'text-inksec'}`}
                  style={labels.includes(t.name) ? { background: t.color, borderColor: t.color } : { borderColor: '#e5e7eb' }}>
                  {t.name}
                </button>
              ))}
              {palette.length === 0 && <span className="text-muted text-[11px]">No tags yet</span>}
            </div>
            <div className="flex gap-1">
              <input value={newTag} onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addNewTag()}
                placeholder="new tag" className="flex-1 border border-grid rounded-lg px-2 py-1 text-[11px]" />
              <button onClick={addNewTag} className="px-2 rounded-lg bg-ink text-white"><IconPlus size={13} stroke={2} /></button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export const ago = timeAgo
