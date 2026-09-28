import { IconNews, IconWorld } from '@tabler/icons-react'
import {
  SiBluesky, SiFacebook, SiInstagram, SiMastodon, SiReddit, SiTelegram,
  SiThreads, SiTiktok, SiX, SiYcombinator, SiYoutube,
} from 'react-icons/si'
import { BRAND } from '../lib/platform'

const GLYPHS: Record<string, React.ComponentType<{ size?: number; color?: string; className?: string }>> = {
  facebook: SiFacebook,
  threads: SiThreads,
  reddit: SiReddit,
  bluesky: SiBluesky,
  mastodon: SiMastodon,
  hackernews: SiYcombinator,
  youtube: SiYoutube,
  instagram: SiInstagram,
  tiktok: SiTiktok,
  telegram: SiTelegram,
  x: SiX,
  news: IconNews as any,
}

/** Real platform logo, brand-colored by default. */
export function PlatformIcon({ platform, size = 14, color, className }: {
  platform: string; size?: number; color?: string; className?: string
}) {
  const Glyph = GLYPHS[platform] || (IconWorld as any)
  const c = color ?? BRAND[platform]?.color ?? '#64748b'
  return <Glyph size={size} color={c} className={className} />
}

/** Square badge with white logo on the platform's brand color. */
export function PlatformBadge({ platform, size = 24 }: { platform: string; size?: number }) {
  const b = BRAND[platform]
  return (
    <span className="rounded-lg grid place-items-center shrink-0"
      style={{ width: size, height: size, background: b?.color || '#64748b' }}>
      <PlatformIcon platform={platform} size={size * 0.55} color="#ffffff" />
    </span>
  )
}

/** Inline pill: logo + label, used on card corners. */
export function PlatformPill({ platform }: { platform: string }) {
  const b = BRAND[platform] || { label: platform, color: '#64748b' }
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full"
      style={{ background: `${b.color}14`, color: b.color }}>
      <PlatformIcon platform={platform} size={11} color={b.color} />
      {b.label}
    </span>
  )
}
