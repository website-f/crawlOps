import {
  IconArrowBigDown, IconArrowBigUp, IconBookmark, IconDots, IconHeart,
  IconMessageCircle, IconRepeat, IconRosetteDiscountCheckFilled, IconSend,
  IconShare3, IconStar, IconThumbUp, IconWorld,
} from '@tabler/icons-react'
import { PostHit, fmtNum } from '../../lib/api'
import { PlatformIcon, PlatformPill } from '../PlatformIcon'
import { Avatar, MediaGrid, OpsFooter, ago } from './shared'

/** Dispatcher: each platform renders a faithful replica of its native post UI,
 *  wrapped with the normalized CrawlOps footer. */
export default function PostCard({ p, onMuted }: { p: PostHit; onMuted?: () => void }) {
  const inner = (() => {
    switch (p.platform) {
      case 'facebook': return <FacebookCard p={p} />
      case 'threads': return <ThreadsCard p={p} />
      case 'reddit': return <RedditCard p={p} />
      case 'bluesky': return <BlueskyCard p={p} />
      case 'mastodon': return <MastodonCard p={p} />
      case 'hackernews': return <HNCard p={p} />
      case 'youtube': return <YouTubeCard p={p} />
      case 'news': return <NewsCard p={p} />
      default: return <GenericCard p={p} />
    }
  })()
  return (
    <article className="rounded-2xl border border-grid bg-white shadow-sm overflow-hidden break-inside-avoid mb-4">
      {inner}
      <OpsFooter p={p} onMuted={onMuted} />
    </article>
  )
}

function FacebookCard({ p }: { p: PostHit }) {
  const e = p.engagement || {}
  return (
    <div className="px-4 pt-3 pb-2" style={{ fontFamily: 'Helvetica, Arial, sans-serif' }}>
      <div className="flex items-center gap-2.5">
        <Avatar src={p.author_avatar} name={p.author_name} size={40} />
        <div className="leading-tight min-w-0">
          <div className="text-[15px] font-semibold text-[#050505] truncate">
            {p.author_name || 'Facebook user'}
            {p.author_verified && <IconRosetteDiscountCheckFilled size={14} className="inline ml-1 text-[#1877F2]" />}
          </div>
          {p.url ? (
            <a href={p.url} target="_blank" rel="noreferrer" title="Open on Facebook"
              className="text-[12px] text-[#65676B] inline-flex items-center gap-1 hover:underline">
              {ago(p.posted_ts)} <IconWorld size={11} stroke={2} />
            </a>
          ) : (
            <div className="text-[12px] text-[#65676B] inline-flex items-center gap-1">
              {ago(p.posted_ts)} <IconWorld size={11} stroke={2} />
            </div>
          )}
        </div>
        <span className="ml-auto shrink-0"><PlatformPill platform="facebook" /></span>
      </div>
      <div className="mt-2.5 text-[15px] text-[#050505] whitespace-pre-wrap leading-snug">{p.text}</div>
      <MediaGrid p={p} />
      {/* crawled posts often carry no counts; show none rather than a row of fake zeros */}
      {(e.likes || e.comments || e.shares) ? <div className="flex items-center justify-between mt-2.5 pb-1 text-[13px] text-[#65676B]">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-[18px] h-[18px] rounded-full bg-[#1877F2] grid place-items-center">
            <IconThumbUp size={11} color="#fff" stroke={2.5} />
          </span>
          {fmtNum(e.likes || 0)}
        </span>
        <span>{fmtNum(e.comments || 0)} comments · {fmtNum(e.shares || 0)} shares</span>
      </div> : null}
      <div className="flex border-t border-[#E4E6EB] mt-2.5 pt-1 text-[#65676B] text-[13px] font-semibold">
        {[
          { label: 'Like', Icon: IconThumbUp },
          { label: 'Comment', Icon: IconMessageCircle },
          { label: 'Share', Icon: IconShare3 },
        ].map(({ label, Icon }) => (
          <span key={label} className="flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 rounded-md hover:bg-[#F2F2F2] cursor-default">
            <Icon size={16} stroke={2} />{label}
          </span>
        ))}
      </div>
    </div>
  )
}

function ThreadsCard({ p }: { p: PostHit }) {
  const e = p.engagement || {}
  return (
    <div className="bg-[#101010] text-[#F3F5F7] px-4 py-3">
      <div className="flex gap-3">
        <div className="flex flex-col items-center">
          <Avatar src={p.author_avatar} name={p.author_handle || p.author_name} size={36} />
          <div className="w-0.5 flex-1 bg-[#333638] mt-2 rounded" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-semibold truncate">{(p.author_handle || p.author_name || '').replace(/^@/, '')}</span>
            <span className="text-[13px] text-[#777]">{ago(p.posted_ts)}</span>
            <span className="ml-auto shrink-0"><PlatformPill platform="threads" /></span>
          </div>
          <div className="text-[15px] mt-0.5 whitespace-pre-wrap leading-snug">{p.text}</div>
          <MediaGrid p={p} dark />
          <div className="flex gap-5 mt-2.5 text-[#F3F5F7]">
            <IconHeart size={19} stroke={1.8} />
            <IconMessageCircle size={19} stroke={1.8} />
            <IconRepeat size={19} stroke={1.8} />
            <IconSend size={19} stroke={1.8} />
          </div>
          <div className="text-[13px] text-[#777] mt-1.5">
            {fmtNum(e.comments || 0)} replies · {fmtNum(e.likes || 0)} likes
          </div>
        </div>
      </div>
    </div>
  )
}

function RedditCard({ p }: { p: PostHit }) {
  const e = p.engagement || {}
  return (
    <div className="flex">
      <div className="w-10 bg-[#F8F9FA] flex flex-col items-center pt-3 text-[#878A8C]">
        <IconArrowBigUp size={18} stroke={1.8} />
        <span className="text-[12px] font-bold text-[#1A1A1B] my-0.5">{fmtNum(e.likes || 0)}</span>
        <IconArrowBigDown size={18} stroke={1.8} />
      </div>
      <div className="flex-1 px-3 py-2.5 min-w-0">
        <div className="flex items-center gap-1.5 text-[12px] text-[#787C7E] flex-wrap">
          <PlatformIcon platform="reddit" size={16} />
          <span className="font-bold text-[#1A1A1B]">{p.author_handle || p.author_name}</span>
          <span>· {ago(p.posted_ts)}</span>
          <span className="ml-auto shrink-0"><PlatformPill platform="reddit" /></span>
        </div>
        <div className="text-[17px] font-medium text-[#222] mt-1 leading-snug">{p.title || p.text.slice(0, 120)}</div>
        {p.title && p.text && p.text !== p.title && (
          <div className="text-[13px] text-[#1A1A1B]/80 mt-1 line-clamp-4 whitespace-pre-wrap">{p.text}</div>
        )}
        <MediaGrid p={p} />
        <div className="flex gap-4 mt-2 text-[12px] font-bold text-[#878A8C]">
          <span className="inline-flex items-center gap-1"><IconMessageCircle size={15} stroke={2} />{fmtNum(e.comments || 0)}</span>
          <span className="inline-flex items-center gap-1"><IconShare3 size={15} stroke={2} />Share</span>
          <span className="inline-flex items-center gap-1"><IconBookmark size={15} stroke={2} />Save</span>
        </div>
      </div>
    </div>
  )
}

function BlueskyCard({ p }: { p: PostHit }) {
  const e = p.engagement || {}
  return (
    <div className="px-4 py-3">
      <div className="flex gap-3">
        <Avatar src={p.author_avatar} name={p.author_name} size={42} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-[15px]">
            <span className="font-bold text-[#0B0F14] truncate">{p.author_name}</span>
            <span className="text-[#42576C] truncate">{p.author_handle}</span>
            <span className="text-[#42576C] shrink-0">· {ago(p.posted_ts)}</span>
            <span className="ml-auto shrink-0"><PlatformPill platform="bluesky" /></span>
          </div>
          <div className="text-[15px] text-[#0B0F14] mt-0.5 whitespace-pre-wrap leading-snug">{p.text}</div>
          <MediaGrid p={p} />
          <div className="flex justify-between max-w-xs mt-2.5 text-[13px] text-[#42576C]">
            <span className="inline-flex items-center gap-1"><IconMessageCircle size={16} stroke={1.8} />{fmtNum(e.comments || 0)}</span>
            <span className="inline-flex items-center gap-1 text-[#20BC7E]"><IconRepeat size={16} stroke={1.8} />{fmtNum(e.shares || 0)}</span>
            <span className="inline-flex items-center gap-1 text-[#EC4899]"><IconHeart size={16} stroke={1.8} />{fmtNum(e.likes || 0)}</span>
            <IconDots size={16} stroke={1.8} />
          </div>
        </div>
      </div>
    </div>
  )
}

function MastodonCard({ p }: { p: PostHit }) {
  const e = p.engagement || {}
  return (
    <div className="px-4 py-3 bg-[#fcfcfd]">
      <div className="flex gap-3">
        <Avatar src={p.author_avatar} name={p.author_name} size={46} round={false} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2">
            <div className="leading-tight min-w-0">
              <div className="font-semibold text-[15px] text-[#1f232b] truncate">{p.author_name || p.author_handle}</div>
              <div className="text-[13px] text-[#606984] truncate">{p.author_handle} · {ago(p.posted_ts)}</div>
            </div>
            <span className="ml-auto shrink-0"><PlatformPill platform="mastodon" /></span>
          </div>
          <div className="text-[15px] text-[#1f232b] mt-1 whitespace-pre-wrap leading-snug">{p.text}</div>
          <MediaGrid p={p} />
          <div className="flex gap-6 mt-2.5 text-[14px] text-[#606984]">
            <span className="inline-flex items-center gap-1"><IconMessageCircle size={16} stroke={1.8} />{fmtNum(e.comments || 0)}</span>
            <span className="inline-flex items-center gap-1"><IconRepeat size={16} stroke={1.8} />{fmtNum(e.shares || 0)}</span>
            <span className="inline-flex items-center gap-1"><IconStar size={16} stroke={1.8} />{fmtNum(e.likes || 0)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function HNCard({ p }: { p: PostHit }) {
  const e = p.engagement || {}
  return (
    <div>
      <div className="h-1.5" style={{ background: '#FF6600' }} />
      <div className="px-4 py-3" style={{ fontFamily: 'Verdana, Geneva, sans-serif' }}>
        <div className="flex items-start gap-2">
          <IconArrowBigUp size={15} stroke={1.8} className="text-[#828282] mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-[14px] text-[#000]">{p.title || p.text.slice(0, 140)}</div>
            <div className="text-[11px] text-[#828282] mt-1">
              {fmtNum(e.likes || 0)} points by {p.author_name} {ago(p.posted_ts)} ago | {fmtNum(e.comments || 0)} comments
            </div>
            {p.title && p.text && p.text !== p.title && (
              <div className="text-[12px] text-[#333] mt-1.5 line-clamp-4">{p.text}</div>
            )}
          </div>
          <span className="shrink-0"><PlatformPill platform="hackernews" /></span>
        </div>
      </div>
    </div>
  )
}

function YouTubeCard({ p }: { p: PostHit }) {
  return (
    <div>
      <MediaGrid p={p} />
      <div className="flex gap-3 px-3 py-2.5" style={{ fontFamily: 'Roboto, Arial, sans-serif' }}>
        <Avatar src={p.author_avatar} name={p.author_name} size={36} />
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-medium text-[#0f0f0f] line-clamp-2 leading-snug">{p.title}</div>
          <div className="text-[12px] text-[#606060] mt-0.5">{p.author_name}</div>
          <div className="text-[12px] text-[#606060]">{ago(p.posted_ts)} ago</div>
        </div>
        <span className="shrink-0"><PlatformPill platform="youtube" /></span>
      </div>
    </div>
  )
}

function NewsCard({ p }: { p: PostHit }) {
  const img = (p.media || [])[0]
  return (
    <div className="flex gap-3 p-3">
      {img && (
        <img src={img.cache_key ? `/api/media/${img.cache_key}` : img.src_url} referrerPolicy="no-referrer"
          className="w-28 sm:w-32 h-24 object-cover rounded-lg bg-slate-100 shrink-0"
          onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-[11px] text-inksec">
          <img src={`https://www.google.com/s2/favicons?domain=${p.domain}&sz=16`} className="w-4 h-4 rounded-sm" />
          <span className="font-semibold uppercase tracking-wide truncate">{p.domain}</span>
          <span className="shrink-0">· {ago(p.posted_ts)}</span>
          <span className="ml-auto shrink-0"><PlatformPill platform="news" /></span>
        </div>
        <a href={p.url} target="_blank" rel="noreferrer"
          className="block text-[16px] font-bold text-ink leading-snug mt-1 hover:underline"
          style={{ fontFamily: 'Georgia, serif' }}>{p.title || p.text.slice(0, 140)}</a>
        {p.title && p.text && p.text !== p.title && (
          <div className="text-[13px] text-inksec mt-1 line-clamp-3">{p.text}</div>
        )}
      </div>
    </div>
  )
}

function GenericCard({ p }: { p: PostHit }) {
  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-2">
        <Avatar src={p.author_avatar} name={p.author_name || p.platform} size={36} />
        <div className="min-w-0">
          <div className="text-[14px] font-semibold truncate">{p.author_name || p.author_handle}</div>
          <div className="text-[12px] text-muted">{ago(p.posted_ts)}</div>
        </div>
        <span className="ml-auto shrink-0"><PlatformPill platform={p.platform} /></span>
      </div>
      {p.title && <div className="font-semibold mt-2">{p.title}</div>}
      <div className="text-[14px] mt-1 whitespace-pre-wrap">{p.text}</div>
      <MediaGrid p={p} />
    </div>
  )
}
