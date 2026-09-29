/* Annotated illustrative "screenshots": stylized SVG mockups of the real screens
   with numbered highlight rings and click/result callouts. Accurate by construction
   and always in sync with the app's layout language. */
import React from 'react'

const INK = '#0b0b0b', SEC = '#52514e', MUT = '#898781', GRID = '#e1e0d9'
const PLANE = '#f9f9f7', BLUE = '#2a78d6', RING = '#eb6834'

function Ring({ x, y, r = 26, n }: { x: number; y: number; r?: number; n: number }) {
  return (
    <g>
      <circle cx={x} cy={y} r={r} fill="none" stroke={RING} strokeWidth={2.5} strokeDasharray="5 4" />
      <circle cx={x + r - 2} cy={y - r + 2} r={9} fill={RING} />
      <text x={x + r - 2} y={y - r + 5} textAnchor="middle" fill="#fff" fontSize={11} fontWeight={700}>{n}</text>
    </g>
  )
}

function Note({ x, y, w = 200, lines, tone = 'action' }: { x: number; y: number; w?: number; lines: string[]; tone?: 'action' | 'result' }) {
  const bg = tone === 'result' ? '#0ca30c' : INK
  const h = 16 + lines.length * 15
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={7} fill={bg} />
      {lines.map((l, i) => (
        <text key={i} x={x + 10} y={y + 18 + i * 15} fill="#fff" fontSize={11.5} fontWeight={i === 0 ? 700 : 400}>{l}</text>
      ))}
    </g>
  )
}

function Frame({ active, children, h = 380 }: { active: string; children: React.ReactNode; h?: number }) {
  const nav = ['Feed', 'Topics', 'Geography', 'Overview', 'Sources', 'AI Engine', 'Tutorial']
  return (
    <svg viewBox={`0 0 760 ${h}`} className="w-full rounded-xl border border-grid" style={{ maxHeight: h + 20 }}>
      <rect x={0} y={0} width={760} height={h} fill={PLANE} />
      {/* sidebar */}
      <rect x={0} y={0} width={132} height={h} fill="#fff" stroke={GRID} />
      <text x={16} y={28} fontSize={13} fontWeight={800} fill={INK}>Crawl<tspan fill={BLUE}>Ops</tspan></text>
      {nav.map((n, i) => (
        <g key={n}>
          <rect x={8} y={44 + i * 30} width={116} height={24} rx={7} fill={n === active ? INK : 'transparent'} />
          <text x={20} y={60 + i * 30} fontSize={11} fill={n === active ? '#fff' : SEC}>{n}</text>
        </g>
      ))}
      {children}
    </svg>
  )
}

const Box = ({ x, y, w, h, fill = '#fff', stroke = GRID, r = 8 }: any) =>
  <rect x={x} y={y} width={w} height={h} rx={r} fill={fill} stroke={stroke} />
const Label = ({ x, y, t, s = 12, w = 400, c = INK, b = false }: any) =>
  <text x={x} y={y} fontSize={s} fill={c} fontWeight={b ? 700 : 400}>{t}</text>

export function FigTopic() {
  return (
    <Frame active="Topics" h={380}>
      <Label x={152} y={30} t="Topics" s={16} b />
      <Box x={152} y={46} w={470} h={150} />
      <Label x={168} y={72} t="New topic" s={13} b />
      {/* brief + AI build */}
      <Box x={168} y={84} w={300} h={30} fill={PLANE} />
      <Label x={180} y={104} t="monitor Proton EV vs BYD…" s={11} c={MUT} />
      <Box x={478} y={84} w={130} h={30} fill="#4a3aa7" stroke="#4a3aa7" />
      <Label x={498} y={104} t="AI build" s={12} c="#fff" b />
      {/* query field */}
      <Box x={168} y={126} w={440} h={26} fill={PLANE} />
      <Label x={180} y={143} t='(proton OR "e.mas") AND (ev OR electric)' s={10} c={SEC} />
      {/* create */}
      <Box x={168} y={160} w={190} h={28} fill={INK} stroke={INK} />
      <Label x={182} y={179} t="Create & start crawling" s={11} c="#fff" b />

      <Ring x={543} y={99} r={24} n={1} />
      <Note x={470} y={214} w={230} lines={['1. Click AI build', 'It writes the query + criteria']} />
      <Ring x={263} y={174} r={24} n={2} />
      <Note x={152} y={214} w={250} lines={['2. Click Create', 'Crawler starts within 30 seconds']} tone="result" />
    </Frame>
  )
}

export function FigFeedGroup() {
  const tabs = ['All', 'News', 'Facebook', 'Reddit', 'YouTube']
  return (
    <Frame active="Feed" h={380}>
      <Label x={152} y={30} t="Feed" s={16} b />
      {/* search + topic + filters */}
      <Box x={152} y={44} w={300} h={28} fill="#fff" />
      <Label x={168} y={62} t="Search posts, authors, domains" s={11} c={MUT} />
      <Box x={460} y={44} w={90} h={28} fill="#fff" />
      <Label x={472} y={62} t="Topic ▾" s={11} c={SEC} />
      <Box x={558} y={44} w={64} h={28} fill={INK} stroke={INK} />
      <Label x={570} y={62} t="Filters" s={11} c="#fff" />
      {/* platform tabs */}
      {tabs.map((t, i) => (
        <g key={t}>
          <rect x={152 + i * 66} y={82} width={60} height={24} rx={12} fill={i === 1 ? BLUE : '#fff'} stroke={GRID} />
          <text x={152 + i * 66 + 30} y={98} textAnchor="middle" fontSize={10} fill={i === 1 ? '#fff' : SEC}>{t}</text>
        </g>
      ))}
      {/* post cards */}
      <Box x={152} y={120} w={225} h={120} />
      <Box x={397} y={120} w={225} h={120} />
      <Label x={168} y={144} t="News card" s={11} b />
      <Label x={413} y={144} t="Reddit card" s={11} b />

      <Ring x={248} y={94} r={22} n={1} />
      <Note x={152} y={256} w={260} lines={['1. Click a platform tab to group', 'the feed by that source']} />
      <Ring x={590} y={58} r={22} n={2} />
      <Note x={430} y={256} w={200} lines={['2. Filters: sentiment,', 'date, media, engagement']} tone="result" />
    </Frame>
  )
}

export function FigExport() {
  return (
    <Frame active="Overview" h={340}>
      <Label x={152} y={30} t="Analytics" s={16} b />
      <Box x={430} y={16} w={90} h={26} fill="#fff" />
      <Label x={446} y={33} t="7d  30d  90d" s={10} c={SEC} />
      <Box x={528} y={16} w={70} h={26} fill="#fff" />
      <Label x={544} y={33} t="PDF" s={11} c={SEC} />
      {/* feed export shown below */}
      <Box x={152} y={56} w={470} h={90} />
      <Label x={168} y={80} t="Stat tiles · charts" s={11} c={MUT} />
      <Label x={168} y={120} t="On the Feed toolbar there is also a CSV Export button." s={11} c={SEC} />

      <Ring x={563} y={29} r={22} n={1} />
      <Note x={360} y={162} w={260} lines={['1. PDF exports an executive report', 'CSV export lives on the Feed toolbar']} tone="result" />
    </Frame>
  )
}

export function FigAIEngine() {
  return (
    <Frame active="AI Engine" h={360}>
      <Label x={152} y={30} t="AI Engine" s={16} b />
      <Box x={152} y={44} w={230} h={150} />
      <Label x={168} y={68} t="Groq" s={13} b />
      <Label x={168} y={88} t="free tier · #10" s={10} c={MUT} />
      <Box x={168} y={100} w={198} h={26} fill={PLANE} />
      <Label x={178} y={117} t="API key  sk-…" s={10} c={MUT} />
      <Box x={168} y={134} w={80} h={24} fill="#fff" />
      <Label x={180} y={150} t="Fetch models" s={9} c={BLUE} />
      <Box x={168} y={164} w={60} h={22} fill={INK} stroke={INK} />
      <Label x={180} y={179} t="Test" s={10} c="#fff" />

      <Ring x={267} y={113} r={22} n={1} />
      <Ring x={198} y={175} r={20} n={2} />
      <Note x={400} y={70} w={220} lines={['1. Paste API key,', 'assign a model per task']} />
      <Note x={400} y={140} w={220} lines={['2. Test, then Save & enable', 'Sentiment + AI analytics turn on']} tone="result" />
    </Frame>
  )
}

export function FigConnect() {
  return (
    <Frame active="Sources" h={360}>
      <Label x={152} y={30} t="Your browser" s={16} b />
      {/* browser window */}
      <Box x={152} y={44} w={340} h={200} fill="#fff" />
      <rect x={152} y={44} width={340} height={26} rx={8} fill={PLANE} />
      <Label x={168} y={62} t="facebook.com  (logged in)" s={10} c={SEC} />
      <Box x={172} y={84} w={300} h={40} fill={PLANE} />
      <Label x={188} y={108} t="Real post feed" s={11} c={MUT} />
      {/* extension popup */}
      <Box x={360} y={120} w={150} h={110} fill="#fff" stroke={BLUE} />
      <Label x={374} y={142} t="CrawlOps Connector" s={10} b />
      <Box x={374} y={152} w={122} h={26} fill={INK} stroke={INK} />
      <Label x={386} y={169} t="Send session" s={10} c="#fff" b />
      <Label x={374} y={198} t="Detected: facebook" s={9} c={MUT} />

      <Ring x={435} y={165} r={24} n={1} />
      <Note x={152} y={262} w={330} lines={['1. Log in normally, click the extension → Send session', 'The crawler is now signed in as that account']} tone="result" />
    </Frame>
  )
}

export function FigAudience() {
  const issues = [
    { name: 'cost of living', sup: 20, neu: 25, opp: 55, res: 0.9 },
    { name: 'economy', sup: 45, neu: 35, opp: 20, res: 0.6 },
    { name: 'healthcare', sup: 55, neu: 30, opp: 15, res: 0.4 },
  ]
  return (
    <Frame active="Overview" h={330}>
      <Label x={152} y={30} t="Audience & Issues" s={15} b />
      <Label x={152} y={48} t="Aggregate opinion segments from public posts" s={10} c={MUT} />
      {issues.map((it, i) => {
        const y = 64 + i * 82
        return (
          <g key={it.name}>
            <Box x={152} y={y} w={456} h={72} />
            <Label x={168} y={y + 22} t={it.name} s={12} b />
            <Label x={168} y={y + 40} t="stance" s={9} c={MUT} />
            <rect x={210} y={y + 32} width={140} height={7} rx={3} fill="#0ca30c" />
            <rect x={210 + 140 * it.sup / 100} y={y + 32} width={140 * it.neu / 100} height={7} fill="#898781" />
            <rect x={210 + 140 * (it.sup + it.neu) / 100} y={y + 32} width={140 * it.opp / 100} height={7} rx={3} fill="#d03b3b" />
            <Label x={168} y={y + 58} t="resonance" s={9} c={MUT} />
            <rect x={230} y={y + 50} width={120} height={7} rx={3} fill="#e1e0d9" />
            <rect x={230} y={y + 50} width={120 * it.res} height={7} rx={3} fill="#4a3aa7" />
            <Label x={470} y={y + 30} t="Top regions" s={9} c={MUT} />
            <Label x={470} y={y + 46} t="MY · SG · ID" s={10} c={SEC} />
          </g>
        )
      })}
      <Ring x={310} y={98} r={26} n={1} />
      <Note x={430} y={64} w={175} lines={['1. Stance split', 'support / neutral / oppose']} />
    </Frame>
  )
}

// The data pipeline as a visual flow: Sources -> Crawl -> AI Judge -> Store -> Surfaces.
export function FlowDiagram() {
  const stages: { x: number; title: string; sub: string; color: string }[] = [
    { x: 20, title: 'Sources', sub: 'news · social · research', color: '#2a78d6' },
    { x: 175, title: 'Crawl', sub: 'free API + stealth browser', color: '#1baf7a' },
    { x: 330, title: 'AI Judge', sub: 'relevance · sentiment · topics', color: '#4a3aa7' },
    { x: 485, title: 'Store', sub: 'Postgres · search · media', color: '#eda100' },
    { x: 640, title: 'Surface', sub: 'feed · analytics · alerts', color: '#eb6834' },
  ]
  const W = 135, H = 74, y = 70
  return (
    <svg viewBox="0 0 795 190" className="w-full">
      <style>{`@keyframes dash{to{stroke-dashoffset:-16}} .flow{stroke-dasharray:6 6;animation:dash 1s linear infinite}
        @media (prefers-reduced-motion: reduce){.flow{animation:none}}`}</style>
      {stages.slice(0, -1).map((s, i) => (
        <line key={i} className="flow" x1={s.x + W} y1={y + H / 2} x2={stages[i + 1].x} y2={y + H / 2}
          stroke="#c3c2b7" strokeWidth={2} />
      ))}
      {stages.map((s, i) => (
        <g key={s.title}>
          <rect x={s.x} y={y} width={W} height={H} rx={12} fill="#fff" stroke={GRID} />
          <rect x={s.x} y={y} width={5} height={H} rx={2} fill={s.color} />
          <circle cx={s.x + 24} cy={y + 24} r={7} fill={s.color} />
          <text x={s.x + 16} y={y + 48} fontSize={14} fontWeight={700} fill={INK}>{s.title}</text>
          <text x={s.x + 16} y={y + 64} fontSize={9.5} fill={MUT}>{s.sub}</text>
          <text x={s.x + W / 2} y={y - 12} textAnchor="middle" fontSize={11} fontWeight={700} fill={s.color}>{i + 1}</text>
        </g>
      ))}
      <text x={397} y={175} textAnchor="middle" fontSize={11} fill={SEC}>
        You set a topic → CrawlOps gathers, judges, and enriches every post → you read, filter, and act on it.
      </text>
    </svg>
  )
}

export function FigGalaxyFig() {
  return (
    <Frame active="Overview" h={300}>
      <Label x={152} y={30} t="Conversation Galaxy" s={15} b />
      <rect x={152} y={44} width={470} height={230} rx={10} fill="#0a0a14" />
      <circle cx={387} cy={159} r={40} fill="url(#cg)" />
      <defs>
        <radialGradient id="cg"><stop offset="0%" stopColor="rgba(42,120,214,.8)" /><stop offset="100%" stopColor="rgba(42,120,214,0)" /></radialGradient>
      </defs>
      {Array.from({ length: 60 }).map((_, i) => {
        const a = i * 0.6, r = 30 + (i % 10) * 18
        const c = i % 3 === 0 ? '#4ade80' : i % 3 === 1 ? '#f87171' : '#cbd5e1'
        return <circle key={i} cx={387 + Math.cos(a) * r} cy={159 + Math.sin(a) * r} r={2 + (i % 4)} fill={c} opacity={0.85} />
      })}
      <Note x={430} y={58} w={185} lines={['Each star = a post', 'color = sentiment']} />
    </Frame>
  )
}
