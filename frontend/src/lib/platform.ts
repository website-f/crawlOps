// Chart series colors: validated reference categorical palette, entity-fixed slots
// (dataviz skill — order is the CVD-safety mechanism, never re-sort by rank).
export const SERIES: Record<string, string> = {
  facebook: '#2a78d6', // slot 1 blue
  bluesky: '#1baf7a',  // slot 2 aqua
  hackernews: '#eda100', // slot 3 yellow
  news: '#008300',     // slot 4 green
  mastodon: '#4a3aa7', // slot 5 violet
  youtube: '#e34948',  // slot 6 red
  threads: '#e87ba4',  // slot 7 magenta
  reddit: '#eb6834',   // slot 8 orange
}
export const SLOT_ORDER = ['facebook', 'bluesky', 'hackernews', 'news', 'mastodon', 'youtube', 'threads', 'reddit']

// Brand identity on cards/badges (real logo via PlatformIcon carries identity, not color alone)
export const BRAND: Record<string, { label: string; color: string }> = {
  facebook: { label: 'Facebook', color: '#1877F2' },
  threads: { label: 'Threads', color: '#101010' },
  reddit: { label: 'Reddit', color: '#FF4500' },
  bluesky: { label: 'Bluesky', color: '#1185FE' },
  mastodon: { label: 'Mastodon', color: '#6364FF' },
  hackernews: { label: 'Hacker News', color: '#FF6600' },
  youtube: { label: 'YouTube', color: '#FF0000' },
  news: { label: 'News', color: '#334155' },
  instagram: { label: 'Instagram', color: '#E4405F' },
  tiktok: { label: 'TikTok', color: '#010101' },
  telegram: { label: 'Telegram', color: '#26A5E4' },
  x: { label: 'X', color: '#0f1419' },
  arxiv: { label: 'arXiv', color: '#B31B1B' },
  sec: { label: 'SEC EDGAR', color: '#1e40af' },
  wikipedia: { label: 'Wikipedia', color: '#636466' },
  github: { label: 'GitHub', color: '#181717' },
  stackexchange: { label: 'Stack Overflow', color: '#F48024' },
  clinicaltrials: { label: 'ClinicalTrials', color: '#0f766e' },
  appstore: { label: 'App Store', color: '#0D96F6' },
  factcheck: { label: 'Fact Check', color: '#059669' },
  podcast: { label: 'Podcast', color: '#8b5cf6' },
  places: { label: 'Places', color: '#EA4335' },
}

export const SENTIMENT = {
  pos: { label: 'Positive', color: '#0ca30c' },   // status good
  neu: { label: 'Neutral', color: '#898781' },    // muted ink
  neg: { label: 'Negative', color: '#d03b3b' },   // status critical
}

export const FEED_TABS = ['all', 'news', 'facebook', 'instagram', 'tiktok', 'threads', 'x', 'reddit', 'bluesky', 'mastodon', 'telegram', 'hackernews', 'youtube', 'arxiv', 'sec', 'wikipedia', 'github', 'stackexchange', 'clinicaltrials', 'appstore', 'factcheck', 'podcast', 'places']
