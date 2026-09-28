import {
  IconAntenna, IconBell, IconBolt, IconBrandChrome, IconChartArcs, IconCpu,
  IconHome, IconMap2, IconMoodSmile, IconPlug, IconRocket, IconScale,
  IconShieldLock, IconTargetArrow, IconWorld,
} from '@tabler/icons-react'
import { useState } from 'react'
import {
  FigAIEngine, FigConnect, FigExport, FigFeedGroup, FigGalaxyFig, FigTopic,
  FlowDiagram,
} from '../components/tutorial-figures'

interface Step { n: number; title: string; body: string; tip?: string }
interface Section { key: string; label: string; Icon: any; intro: string; steps: Step[]; Fig?: () => JSX.Element }

const WALKTHROUGH: Section[] = [
  {
    key: 'start', label: 'Getting started', Icon: IconRocket,
    intro: 'The fastest path to your first results. Three moves and posts start flowing.',
    steps: [
      { n: 1, title: 'Enable an AI provider', body: 'AI Engine → open a preset (e.g. Groq) → paste an API key → Fetch models → assign a model to the "judge" task → enable → Save. This unlocks sentiment, emotion, topics, and every AI analytic.', tip: 'Free tiers (Groq, OpenRouter, Mistral, HuggingFace) are enough to start.' },
      { n: 2, title: 'Create a topic', body: 'Topics → describe what to monitor in plain language and click AI build, or write a boolean query yourself → Save. The crawler starts within 30 seconds.' },
      { n: 3, title: 'Watch the Feed fill', body: 'Open Feed. Keyless sources (news, Hacker News, Mastodon, Reddit, Wikipedia, GitHub and more) begin flowing immediately, each rendered in its native platform style.' },
    ],
    Fig: FigAIEngine,
  },
  {
    key: 'topics', label: 'Topics & crawling', Icon: IconTargetArrow,
    intro: 'A topic is a boolean query plus natural-language criteria the AI judge uses to keep only genuinely relevant posts.',
    steps: [
      { n: 1, title: 'Boolean query', body: 'Use (term OR "multi word") AND (other) NOT (noise). The first group is your subject and its aliases; add NOT terms only for ambiguous names.' },
      { n: 2, title: 'Judge criteria', body: 'Describe in a sentence what counts as relevant, e.g. "posts about our product quality, not job ads." Posts below the threshold are stored but hidden.' },
      { n: 3, title: 'Schedule', body: 'Set how often the topic re-crawls. Use Run now to trigger an immediate cycle.' },
    ],
    Fig: FigTopic,
  },
  {
    key: 'feed', label: 'The Feed', Icon: IconAntenna,
    intro: 'Every post appears as a faithful replica of its home platform, with a filter rail on the left and a normalized footer for sentiment, reach, and actions.',
    steps: [
      { n: 1, title: 'Filter rail', body: 'Multi-select platforms, sentiment, and time on the left — each option shows a live, cross-filtered count.' },
      { n: 2, title: 'Search & sort', body: 'Instant search across text, authors, and domains; sort by newest, engagement, relevance, or reach.' },
      { n: 3, title: 'Suppress noise', body: 'On any post, Mute hides that author everywhere; Watch keeps them visible but out of analytics.' },
      { n: 4, title: 'Export', body: 'Export the current topic/platform to CSV from the toolbar.' },
    ],
    Fig: FigFeedGroup,
  },
  {
    key: 'analytics', label: 'Analytics', Icon: IconChartArcs,
    intro: 'The Analyze section turns the feed into decisions. Every view respects the topic + date range at the top; Overview and Sentiment add a live cross-filter rail.',
    steps: [
      { n: 1, title: 'Overview & Brand Health', body: 'Volume, reach, EMV, net sentiment, plus a 0-100 brand-health composite, crisis risk, forecast, and waterfall.' },
      { n: 2, title: 'Sentiment, Trends, Influencers', body: 'Emotions radar and Source→Topic→Sentiment flow; momentum, heatmap, constellation; the influence pyramid, top voices, and coordinated-narrative detection.' },
      { n: 3, title: 'Galaxy & Daily Brief', body: 'The 3D conversation galaxy, plus an AI-written executive brief and cause-and-effect chains.' },
      { n: 4, title: 'Export PDF', body: 'Export any analytics view as a PDF report from the toolbar.' },
    ],
    Fig: FigExport,
  },
  {
    key: 'competitors', label: 'Competitors', Icon: IconScale,
    intro: 'Track your brand against named competitors and see who owns the conversation.',
    steps: [
      { n: 1, title: 'Add entities', body: 'Add your brand (star it) and each competitor, each with its own keyword set.' },
      { n: 2, title: 'Share of voice', body: 'The streamgraph shows each entity\'s mention volume over time.' },
      { n: 3, title: 'Health comparison', body: 'Compare brand-health scores of your brand, competitors, and the whole market side by side.' },
    ],
  },
  {
    key: 'connect', label: 'Connecting accounts', Icon: IconBrandChrome,
    intro: 'News, Mastodon, Bluesky, Reddit, Wikipedia and others need no login. Facebook, Instagram, TikTok, X and Threads are login-walled — the crawler must be signed in as a real account.',
    steps: [
      { n: 1, title: 'Install the extension', body: 'Load browser-extension/ via chrome://extensions → Developer mode → Load unpacked. Paste your API token (Settings → Browser extension) and CrawlOps URL.' },
      { n: 2, title: 'Log in normally', body: 'Open the platform in your own browser and log in — handle any 2FA/CAPTCHA yourself.' },
      { n: 3, title: 'Send the session', body: 'Click the extension → Send session to CrawlOps. The crawler now browses logged-in as that account.' },
      { n: 4, title: 'Add a proxy', body: 'Sources → proxy pool → add a residential proxy. Even logged in, a datacenter IP gets challenged. Use dedicated accounts.' },
    ],
    Fig: FigConnect,
  },
  {
    key: 'ai', label: 'AI Engine', Icon: IconCpu,
    intro: 'Your own provider rotation. Keys are encrypted in the database; free tiers are tried first and a rate-limited provider cools down while the next takes over.',
    steps: [
      { n: 1, title: 'Add a provider', body: 'Any OpenAI-compatible provider works. Paste the base URL and API key, then Fetch models.' },
      { n: 2, title: 'Assign models to tasks', body: 'judge (relevance + sentiment), enrich (labels, brief), agent (browser extraction), embed (clustering). Only tasks with a model are served.' },
      { n: 3, title: 'Set priority & test', body: 'Lower priority number is tried first. Test the key, then watch usage in the token monitor.' },
    ],
    Fig: FigGalaxyFig,
  },
  {
    key: 'security', label: 'Users & security', Icon: IconShieldLock,
    intro: 'CrawlOps is behind a login. Manage access and protect your keys.',
    steps: [
      { n: 1, title: 'Change the default admin', body: 'The default admin is seeded from .env. Add a new admin in Settings → Users and remove the default before exposing the app.' },
      { n: 2, title: 'Add users', body: 'Roles: admin, analyst, viewer. Admins manage providers and users.' },
      { n: 3, title: 'Protect secrets', body: 'Set a strong SECRET_KEY (encrypts provider keys) before production, and do not rotate it afterwards or stored keys must be re-entered.' },
    ],
  },
]

const CAPABILITIES = [
  { Icon: IconWorld, title: 'Crawl everything', body: 'News, Facebook, Instagram, TikTok, X, Threads, Reddit, Bluesky, Mastodon, YouTube, Telegram, plus arXiv, GitHub, Wikipedia, SEC and more.' },
  { Icon: IconMoodSmile, title: 'AI enrichment', body: 'Every post is judged for relevance and scored for sentiment, emotion, topics, virality and reputational risk.' },
  { Icon: IconChartArcs, title: 'Deep analytics', body: 'Brand health, crisis risk, momentum, share of voice, forecast, heatmaps, coordinated-narrative detection.' },
  { Icon: IconMap2, title: 'Geography', body: 'See which countries and regions the conversation comes from, colored by sentiment.' },
  { Icon: IconBell, title: 'Alerts', body: 'Volume-spike and negative-sentiment alerts delivered to webhook or Telegram.' },
  { Icon: IconBolt, title: 'Your own AI', body: 'Bring any OpenAI-compatible provider; keys encrypted in your database, rotated automatically.' },
]

export default function Tutorial() {
  const [active, setActive] = useState('overview')
  const section = WALKTHROUGH.find((s) => s.key === active)

  return (
    <div>
      <div className="mb-4">
        <h2 className="font-semibold text-lg">Tutorial</h2>
        <p className="text-sm text-inksec">What CrawlOps is, what it does, and how to use every part of it.</p>
      </div>

      <div className="lg:grid lg:grid-cols-[220px_1fr] lg:gap-6">
        {/* tab nav */}
        <nav className="flex lg:flex-col gap-1 overflow-x-auto pb-2 lg:pb-0 mb-4 lg:mb-0">
          <button onClick={() => setActive('overview')}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition
              ${active === 'overview' ? 'bg-ink text-white' : 'text-inksec hover:bg-white'}`}>
            <IconHome size={16} stroke={2} className="shrink-0" />Overview
          </button>
          <div className="hidden lg:block text-[10px] font-semibold uppercase tracking-wider text-muted px-3 pt-3 pb-1">Walkthrough</div>
          {WALKTHROUGH.map(({ key, label, Icon }) => (
            <button key={key} onClick={() => setActive(key)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition
                ${active === key ? 'bg-ink text-white' : 'text-inksec hover:bg-white'}`}>
              <Icon size={16} stroke={2} className="shrink-0" />{label}
            </button>
          ))}
        </nav>

        {/* content */}
        <div className="min-w-0">
          {active === 'overview' ? (
            <div className="space-y-5">
              {/* hero */}
              <div className="bg-ink text-white rounded-2xl p-6 lg:p-8">
                <div className="flex items-center gap-2 text-[#8fb8ec] text-sm font-medium mb-2">
                  <IconAntenna size={18} stroke={2} /> CrawlOps
                </div>
                <h1 className="text-2xl lg:text-3xl font-bold tracking-tight leading-tight max-w-2xl">
                  Self-hosted social intelligence. One topic in, the whole conversation out.
                </h1>
                <p className="text-white/70 mt-3 max-w-2xl leading-relaxed">
                  CrawlOps monitors any topic across news and social platforms, unifies every post into one feed,
                  and runs AI analytics on top — like Meltwater, but self-hosted and running on your own AI keys.
                </p>
              </div>

              {/* what it does */}
              <div>
                <h3 className="font-semibold mb-3">What it does</h3>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {CAPABILITIES.map(({ Icon, title, body }) => (
                    <div key={title} className="bg-white border border-grid rounded-2xl p-4">
                      <span className="w-9 h-9 rounded-xl bg-plane grid place-items-center mb-2">
                        <Icon size={18} stroke={2} className="text-ink" />
                      </span>
                      <div className="font-medium text-sm">{title}</div>
                      <p className="text-[13px] text-inksec mt-1 leading-relaxed">{body}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* how it works — flow */}
              <div className="bg-white border border-grid rounded-2xl p-5">
                <h3 className="font-semibold mb-1">How it works</h3>
                <p className="text-sm text-inksec mb-3">The pipeline every post travels through, end to end.</p>
                <FlowDiagram />
              </div>

              {/* quick start */}
              <div className="bg-white border border-grid rounded-2xl p-5">
                <h3 className="font-semibold mb-3">Start in 3 steps</h3>
                <ol className="grid sm:grid-cols-3 gap-3">
                  {[
                    ['Enable AI', 'AI Engine → paste a free Groq key → assign a model → enable.'],
                    ['Create a topic', 'Topics → describe it → AI build → Create. Crawling starts in 30s.'],
                    ['Read & act', 'Watch the Feed fill, explore Analytics, set Alerts.'],
                  ].map(([t, b], i) => (
                    <li key={t} className="border border-grid rounded-xl p-3">
                      <span className="w-7 h-7 rounded-full bg-ink text-white grid place-items-center text-sm font-semibold mb-2">{i + 1}</span>
                      <div className="font-medium text-sm">{t}</div>
                      <p className="text-[13px] text-inksec mt-0.5">{b}</p>
                    </li>
                  ))}
                </ol>
                <button onClick={() => setActive('start')}
                  className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-ink text-white text-sm active:scale-[0.98]">
                  <IconRocket size={15} stroke={2} />Open the walkthrough
                </button>
              </div>
            </div>
          ) : section && (
            <>
              <div className="bg-white border border-grid rounded-2xl p-5 lg:p-6">
                <div className="flex items-center gap-3 mb-2">
                  <span className="w-10 h-10 rounded-xl bg-ink grid place-items-center shrink-0">
                    <section.Icon size={20} color="#fcfcfb" stroke={2} />
                  </span>
                  <h3 className="font-semibold text-lg">{section.label}</h3>
                </div>
                <p className="text-sm text-inksec leading-relaxed mb-4 max-w-2xl">{section.intro}</p>

                {section.Fig && (
                  <div className="mb-5 max-w-2xl">
                    <section.Fig />
                    <div className="text-[11px] text-muted mt-1.5 text-center">Orange rings mark where to click · green notes show the result.</div>
                  </div>
                )}

                <ol className="space-y-3">
                  {section.steps.map((s) => (
                    <li key={s.n} className="flex gap-3">
                      <span className="w-7 h-7 rounded-full bg-plane border border-grid grid place-items-center text-sm font-semibold shrink-0 tabular-nums">{s.n}</span>
                      <div className="min-w-0">
                        <div className="font-medium text-sm">{s.title}</div>
                        <p className="text-sm text-inksec leading-relaxed mt-0.5">{s.body}</p>
                        {s.tip && <div className="mt-1.5 text-[13px] text-[#006300] bg-[#0ca30c]/8 border border-[#0ca30c]/20 rounded-lg px-2.5 py-1.5">Tip: {s.tip}</div>}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="flex justify-between mt-4">
                <button onClick={() => { const i = WALKTHROUGH.findIndex((s) => s.key === active); setActive(i > 0 ? WALKTHROUGH[i - 1].key : 'overview') }}
                  className="px-4 py-2 rounded-xl text-sm border border-grid bg-white">Previous</button>
                <button onClick={() => { const i = WALKTHROUGH.findIndex((s) => s.key === active); if (i < WALKTHROUGH.length - 1) setActive(WALKTHROUGH[i + 1].key) }}
                  disabled={WALKTHROUGH[WALKTHROUGH.length - 1].key === active}
                  className="px-4 py-2 rounded-xl text-sm bg-ink text-white disabled:opacity-40">Next</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
