import { IconEye, IconExternalLink, IconPlayerPlayFilled, IconVolumeOff } from '@tabler/icons-react'
import { PostHit, fmtNum, mediaUrl, post, thumbUrl, timeAgo } from '../../lib/api'
import { SENTIMENT } from '../../lib/platform'

export function Avatar({ src, name, size = 40, round = true }: { src?: string; name: string; size?: number; round?: boolean }) {
  const initial = (name || '?').replace(/^[@u]\//, '').charAt(0).toUpperCase()
  return src ? (
    <img src={src} width={size} height={size} referrerPolicy="no-referrer"
      className={`${round ? 'rounded-full' : 'rounded-lg'} object-cover shrink-0`}
      style={{ width: size, height: size }}
      onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
  ) : (
    <div className={`${round ? 'rounded-full' : 'rounded-lg'} shrink-0 grid place-items-center bg-slate-200 text-slate-600 font-semibold`}
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
            <a key={i} href={p.url} target="_blank" rel="noreferrer" className="relative block group">
              <img src={thumbUrl(m)} className="w-full aspect-video object-cover" />
              <span className="absolute inset-0 grid place-items-center">
                <span className="w-14 h-10 rounded-lg bg-black/70 grid place-items-center
                                 transition group-hover:bg-black/85">
                  <IconPlayerPlayFilled size={18} color="#fff" />
                </span>
              </span>
            </a>
          ) : m.cache_key ? (
            <video key={i} controls preload="none" poster={m.thumb_key ? `/api/media/${m.thumb_key}` : undefined}
              className="w-full max-h-96 bg-black" src={`/api/media/${m.cache_key}`} />
          ) : (
            <a key={i} href={p.url} target="_blank" rel="noreferrer" className="relative block">
              <img src={thumbUrl(m)} className="w-full aspect-video object-cover bg-slate-100" />
              <span className="absolute inset-0 grid place-items-center">
                <IconPlayerPlayFilled size={28} color="#fff" className="drop-shadow" />
              </span>
            </a>
          )
        ) : (
          <img key={i} src={mediaUrl(m)} loading="lazy" referrerPolicy="no-referrer"
            className={`w-full object-cover ${items.length === 1 ? 'max-h-[28rem]' : 'aspect-square'} ${dark ? 'bg-neutral-800' : 'bg-slate-100'}`}
            onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
        ),
      )}
    </div>
  )
}

/** Normalized CrawlOps footer under every native card: enrichment + actions. */
export function OpsFooter({ p, onMuted }: { p: PostHit; onMuted?: () => void }) {
  const s = p.sentiment ? SENTIMENT[p.sentiment] : null
  const mute = async (mode: 'hide' | 'watch') => {
    if (!p.author_key) return
    await post('/suppression', { platform: p.platform, author_key: p.author_key, mode, reason: 'from feed' })
    onMuted?.()
  }
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5 border-t border-grid bg-plane/60 text-[11px] text-inksec">
      {s ? (
        <span className="inline-flex items-center gap-1 font-medium" style={{ color: s.color }}>
          <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />{s.label}
        </span>
      ) : (
        <span className="text-muted">analyzing</span>
      )}
      {p.relevance != null && <span title="relevance score">rel {p.relevance}</span>}
      {p.reach != null && <span title="estimated reach">~{fmtNum(p.reach)} reach</span>}
      {(p.topics || []).slice(0, 2).map((t) => (
        <span key={t} className="px-1.5 py-0.5 rounded-full bg-grid/60 text-inksec">{t}</span>
      ))}
      {p.suppression_watch && <span className="text-amber-600 font-medium">watched</span>}
      <span className="flex-1" />
      <button onClick={() => mute('watch')} title="keep visible, exclude from analytics"
        className="inline-flex items-center gap-1 hover:text-ink active:scale-[0.96]">
        <IconEye size={13} stroke={2} />watch
      </button>
      <button onClick={() => mute('hide')} title="hide author everywhere (internal shadowban)"
        className="inline-flex items-center gap-1 hover:text-red-700 active:scale-[0.96]">
        <IconVolumeOff size={13} stroke={2} />mute
      </button>
      {p.url && (
        <a href={p.url} target="_blank" rel="noreferrer"
          className="inline-flex items-center gap-1 font-medium hover:text-ink">
          <IconExternalLink size={13} stroke={2} />open
        </a>
      )}
    </div>
  )
}

export const ago = timeAgo
