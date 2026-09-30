import {
  IconActivity, IconAffiliate, IconChartBar, IconClock, IconExternalLink, IconLanguage,
  IconMapPin, IconRosetteDiscountCheck, IconSparkles, IconTrendingUp,
} from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PostHit, fmtNum, get, timeAgo } from '../lib/api'
import { SENTIMENT } from '../lib/platform'
import { PlatformBadge } from './PlatformIcon'
import PostCard from './cards/PostCard'
import { Avatar } from './cards/shared'
import { usePostDetail } from './postdetail-ctx'
import { Segmented } from './ui/controls'
import { Offcanvas } from './ui/offcanvas'

function Stat({ Icon, label, value, tone }: { Icon: any; label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-grid bg-surface px-3 py-2">
      <Icon size={16} stroke={2} className="text-muted shrink-0" />
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-wide text-muted leading-none">{label}</div>
        <div className={`text-[13px] font-semibold tabular-nums truncate ${tone || 'text-ink'}`}>{value}</div>
      </div>
    </div>
  )
}

export function PostDetailPanel() {
  const { active, close, open } = usePostDetail()
  const [tab, setTab] = useState<'author' | 'similar'>('author')
  const [authorPosts, setAuthorPosts] = useState<PostHit[]>([])
  const [similar, setSimilar] = useState<PostHit[]>([])
  const [loading, setLoading] = useState(false)
  const id = active?.id

  useEffect(() => {
    if (!active) return
    setTab('author'); setAuthorPosts([]); setSimilar([]); setLoading(true)
    const jobs: Promise<any>[] = []
    if (active.author_key) {
      jobs.push(get<{ hits: PostHit[] }>(`/posts?author_key=${encodeURIComponent(active.author_key)}&per_page=24&sort=posted_ts:desc`)
        .then((d) => setAuthorPosts((d.hits || []).filter((h) => h.id !== active.id))).catch(() => {}))
    }
    jobs.push(get<{ hits: PostHit[] }>(`/search/similar/${active.id}`).then((d) => setSimilar(d.hits || [])).catch(() => {}))
    Promise.allSettled(jobs).then(() => setLoading(false))
  }, [id]) // eslint-disable-line

  if (!active) return null
  const p = active
  const s = p.sentiment ? SENTIMENT[p.sentiment] : null
  const eng = Object.entries(p.engagement || {}).filter(([, v]) => v > 0)
  const list = tab === 'author' ? authorPosts : similar

  return (
    <Offcanvas open={!!active} onClose={close} width="42rem"
      title={<span className="flex items-center gap-1.5">{p.author_name || p.author_handle || 'Post'}
        {p.author_verified && <IconRosetteDiscountCheck size={15} className="text-accent" />}</span>}
      subtitle={<span className="capitalize">{p.author_handle ? `@${p.author_handle.replace(/^@/, '')} · ` : ''}{p.platform}</span>}>
      <div className="p-4 sm:p-5 space-y-5">
        {/* author header */}
        <div className="flex items-center gap-3">
          <Avatar src={p.author_avatar} name={p.author_name || p.author_handle || '?'} size={52} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-[15px] truncate">{p.author_name || p.author_handle || 'Unknown'}</span>
              {p.author_verified && <IconRosetteDiscountCheck size={16} className="text-accent shrink-0" />}
            </div>
            <div className="text-[12.5px] text-muted flex items-center gap-1.5">
              <PlatformBadge platform={p.platform} size={14} />
              <span className="capitalize">{p.platform}</span>
              {p.author_handle && <span className="truncate">· @{p.author_handle.replace(/^@/, '')}</span>}
            </div>
          </div>
          {p.url && (
            <a href={p.url} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[12.5px] font-medium px-3 py-1.5 rounded-lg border border-grid hover:border-accent/40 hover:text-accent-ink transition">
              <IconExternalLink size={14} stroke={2} />Open original
            </a>
          )}
        </div>

        {/* the post itself, platform-formatted */}
        <PostCard p={p} />

        {/* metrics */}
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted mb-2">Signals</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {s && <Stat Icon={IconActivity} label="Sentiment" value={s.label} tone="" />}
            {p.relevance != null && <Stat Icon={IconChartBar} label="Relevance" value={String(p.relevance)} />}
            {p.reach != null && <Stat Icon={IconTrendingUp} label="Reach" value={`~${fmtNum(p.reach)}`} />}
            {p.custom_score != null && p.custom_score > 0 && <Stat Icon={IconSparkles} label="Impact" value={String(p.custom_score)} tone="text-accent" />}
            {p.emv != null && p.emv > 0 && <Stat Icon={IconChartBar} label="EMV" value={`RM ${fmtNum(p.emv)}`} />}
            {p.virality != null && p.virality > 0 && <Stat Icon={IconTrendingUp} label="Virality" value={String(p.virality)} />}
            {p.risk != null && p.risk > 0 && <Stat Icon={IconActivity} label="Risk" value={String(p.risk)} tone="text-danger" />}
            {p.emotion && <Stat Icon={IconActivity} label="Emotion" value={p.emotion} />}
            {(p.country_name || p.country) && <Stat Icon={IconMapPin} label="Country" value={p.country_name || p.country || ''} />}
            {p.lang && <Stat Icon={IconLanguage} label="Language" value={p.lang.toUpperCase()} />}
            <Stat Icon={IconClock} label="Posted" value={timeAgo(p.posted_ts)} />
          </div>
        </div>

        {eng.length > 0 && (
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted mb-2">Engagement</div>
            <div className="flex flex-wrap gap-2">
              {eng.map(([k, v]) => (
                <span key={k} className="inline-flex items-center gap-1.5 rounded-lg bg-plane border border-grid px-2.5 py-1 text-[13px]">
                  <span className="text-muted capitalize">{k}</span>
                  <span className="font-semibold tabular-nums">{fmtNum(v)}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {(p.entities?.length || p.topics?.length) ? (
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted mb-2">Topics &amp; entities</div>
            <div className="flex flex-wrap gap-1.5">
              {(p.topics || []).map((t) => <span key={`t${t}`} className="text-[12px] px-2 py-0.5 rounded-full bg-accent/10 text-accent-ink">{t}</span>)}
              {(p.entities || []).slice(0, 20).map((e) => <span key={`e${e}`} className="text-[12px] px-2 py-0.5 rounded-full bg-grid/60 text-inksec">{e}</span>)}
            </div>
          </div>
        ) : null}

        {/* related */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <Segmented value={tab} onChange={setTab} options={[
              { value: 'author', label: `More from author${authorPosts.length ? ` (${authorPosts.length})` : ''}` },
              { value: 'similar', label: `Similar${similar.length ? ` (${similar.length})` : ''}` },
            ]} />
            {tab === 'similar' && (
              <Link to={`/search?similar=${p.id}`} onClick={close}
                className="text-[12px] text-inksec hover:text-ink inline-flex items-center gap-1">
                <IconSparkles size={13} stroke={2} />see all
              </Link>
            )}
          </div>

          {loading && list.length === 0 && (
            <div className="py-10 grid place-items-center"><span className="w-6 h-6 rounded-full border-2 border-grid border-t-accent animate-spin" /></div>
          )}
          {!loading && list.length === 0 && (
            <div className="text-center py-10 text-muted text-sm rounded-xl border border-grid bg-surface">
              <IconAffiliate size={26} stroke={1.5} className="mx-auto mb-1.5" />
              {tab === 'author' ? 'No other posts from this author yet.' : 'No similar posts found.'}
            </div>
          )}
          <div className="space-y-3">
            {list.map((hit) => (
              <button key={hit.id} onClick={() => open(hit)} className="block w-full text-left group">
                <div className="pointer-events-none group-hover:opacity-95 transition-opacity"><PostCard p={hit} /></div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </Offcanvas>
  )
}
