import {
  IconAntenna, IconBell, IconBrandChrome, IconChartArcs, IconCpu, IconPlug,
  IconRocket, IconScale, IconShieldLock, IconTargetArrow,
} from '@tabler/icons-react'
import { useState } from 'react'
import {
  FigAIEngine, FigConnect, FigExport, FigFeedGroup, FigGalaxyFig, FigTopic,
} from '../components/tutorial-figures'

interface Step { n: number; title: string; body: string; tip?: string }
interface Section { key: string; label: string; Icon: any; intro: string; steps: Step[]; Fig?: () => JSX.Element }

const SECTIONS: Section[] = [
  {
    key: 'start', label: 'Getting started', Icon: IconRocket,
    intro: 'CrawlOps monitors a topic across news and social platforms, unifies everything into one feed, and runs AI analytics on top. Here is the fastest path to your first results.',
    steps: [
      { n: 1, title: 'Enable an AI provider', body: 'Go to AI Engine, open a preset (e.g. Groq), paste an API key, click Fetch models, assign a model to the "judge" task, enable it, and Save. This unlocks sentiment, emotion, topics, and every AI analytic.', tip: 'Free tiers (Groq, OpenRouter, Mistral, HuggingFace) are enough to start. Rotation uses free ones first.' },
      { n: 2, title: 'Create a topic', body: 'Go to Topics, describe what to monitor in plain language and click AI build, or write a boolean query yourself. Save it — the crawler starts within 30 seconds.' },
      { n: 3, title: 'Watch the Feed fill', body: 'Open Feed. Keyless sources (news, Hacker News, Mastodon, Reddit, arXiv, Wikipedia, and more) begin flowing immediately. Each post renders in its native platform style.' },
    ],
    Fig: FigAIEngine,
  },
  {
    key: 'topics', label: 'Topics & crawling', Icon: IconTargetArrow,
    intro: 'A topic is a boolean query plus natural-language criteria the AI judge uses to keep only genuinely relevant posts.',
    steps: [
      { n: 1, title: 'Boolean query', body: 'Use (term OR "multi word") AND (other) NOT (noise). The first group is your subject and its aliases. Add NOT terms only for ambiguous names.' },
      { n: 2, title: 'Judge criteria', body: 'Describe in a sentence what counts as relevant, e.g. "posts about our product quality, not job ads." Posts scoring below the threshold are stored but hidden.' },
      { n: 3, title: 'Schedule', body: 'Set how often the topic re-crawls. Use Run now to trigger an immediate cycle.' },
    ],
    Fig: FigTopic,
  },
  {
    key: 'feed', label: 'The Feed', Icon: IconAntenna,
    intro: 'Every fetched post appears as a faithful replica of its home platform, with a normalized footer for sentiment, reach, and actions.',
    steps: [
      { n: 1, title: 'Filter by platform', body: 'Use the platform tabs, or open Filters for sentiment, date range, media, engagement, and sort.' },
      { n: 2, title: 'Search', body: 'The search box does instant faceted search across post text, authors, and domains.' },
      { n: 3, title: 'Suppress noise', body: 'On any post, Mute hides that author everywhere; Watch keeps them visible but out of analytics. Manage them in Suppression.' },
      { n: 4, title: 'Export', body: 'Export the current topic/platform to CSV from the toolbar.' },
    ],
    Fig: FigFeedGroup,
  },
  {
    key: 'analytics', label: 'Analytics', Icon: IconChartArcs,
    intro: 'The Analyze section turns the feed into decisions. Every view respects the topic + date range at the top, and the Overview/Sentiment views add a live cross-filter rail.',
    steps: [
      { n: 1, title: 'Overview', body: 'Volume, reach, earned media value, net sentiment, and the cross-filter rail (platform × sentiment × emotion × topic × country).' },
      { n: 2, title: 'Brand Health', body: 'A 0-100 composite (sentiment, positivity, momentum, reach) plus crisis risk, volume forecast, and net-sentiment waterfall.' },
      { n: 3, title: 'Sentiment, Trends, Influencers', body: 'Emotions radar and Source→Topic→Sentiment flow; momentum quadrant, heatmap, constellation, and the conversation galaxy; the influence pyramid, top voices, and coordinated-narrative detection.' },
      { n: 4, title: 'Daily Brief', body: 'An AI-written executive summary plus cause-and-effect chains. Export any view as a PDF report from the toolbar.' },
    ],
    Fig: FigExport,
  },
  {
    key: 'competitors', label: 'Competitors', Icon: IconScale,
    intro: 'Track your brand against named competitors and see who owns the conversation.',
    steps: [
      { n: 1, title: 'Add entities', body: 'Add your brand (mark it with the star) and each competitor, each with its own keyword set.' },
      { n: 2, title: 'Share of voice', body: 'The streamgraph shows each entity\'s mention volume over time.' },
      { n: 3, title: 'Health comparison', body: 'Compare brand-health scores of your brand, competitors, and the whole market side by side.' },
    ],
  },
  {
    key: 'alerts', label: 'Alerts', Icon: IconBell,
    intro: 'Get told when something moves, delivered to a webhook or Telegram.',
    steps: [
      { n: 1, title: 'Set channels', body: 'In Settings → Alert channels, add a webhook URL and/or a Telegram bot token + chat id, then Send test.' },
      { n: 2, title: 'Add a rule', body: 'In Alerts, add a Volume spike or Negative sentiment rule per topic. Spikes use an EWMA baseline; negative-sentiment fires when the negative share crosses your threshold.' },
      { n: 3, title: 'Review firings', body: 'Recent alerts are listed with the reason and timestamp.' },
    ],
  },
  {
    key: 'connect', label: 'Connecting social accounts', Icon: IconBrandChrome,
    intro: 'News, Hacker News, Mastodon, Bluesky, Reddit, arXiv, Wikipedia and others need no login. Facebook, Instagram, TikTok, X and Threads are login-walled — the crawler must be signed in as a real account.',
    steps: [
      { n: 1, title: 'Install the connector extension', body: 'Load the browser-extension/ folder via chrome://extensions → Developer mode → Load unpacked. Paste your API token (Settings → Browser extension) and CrawlOps URL into it.' },
      { n: 2, title: 'Log in normally', body: 'Open the platform in your own browser and log in — handle any 2FA or CAPTCHA yourself, as a human.' },
      { n: 3, title: 'Send the session', body: 'Click the extension → Send session to CrawlOps. The crawler now browses logged-in as that account. Re-run if a session expires.' },
      { n: 4, title: 'Add a proxy', body: 'In Sources → proxy pool, add a residential proxy. Even logged in, a datacenter IP gets challenged. Use dedicated accounts, not personal ones.' },
    ],
    Fig: FigConnect,
  },
  {
    key: 'ai', label: 'AI Engine', Icon: IconCpu,
    intro: 'Your own provider rotation. Keys are encrypted in the database; free tiers are tried first and a rate-limited provider cools down while the next takes over.',
    steps: [
      { n: 1, title: 'Add a provider', body: 'Any OpenAI-compatible provider works. Paste the base URL and API key, then Fetch models.' },
      { n: 2, title: 'Assign models to tasks', body: 'Assign a model per task: judge (relevance + sentiment), enrich (labels, brief), agent (browser extraction), embed (clustering). Only tasks with a model are served.' },
      { n: 3, title: 'Set priority & test', body: 'Lower priority number is tried first. Use Test to confirm the key works. Watch usage in the token monitor.' },
    ],
    Fig: FigGalaxyFig,
  },
  {
    key: 'sources', label: 'Sources & data', Icon: IconPlug,
    intro: 'Every connector, its status, the proxy pool, and stealth sessions live here.',
    steps: [
      { n: 1, title: 'Toggle connectors', body: 'Enable or disable any source. Keyless ones run immediately; some (Threads, YouTube, RSS, App Store, Fact Check, Podcast) need config — click Configure.' },
      { n: 2, title: 'Configure feeds', body: 'For RSS add feed URLs or RSSHub routes; for Telegram add public channel names; for App Store add app ids.' },
      { n: 3, title: 'Watch runs', body: 'Recent fetch runs show what each source found and inserted, and any error.' },
    ],
  },
  {
    key: 'security', label: 'Users & security', Icon: IconShieldLock,
    intro: 'CrawlOps is behind a login. Manage who has access and protect your keys.',
    steps: [
      { n: 1, title: 'Change the default admin', body: 'The default admin is seeded from your .env. Add a new admin in Settings → Users and remove the default before exposing the app.' },
      { n: 2, title: 'Add users', body: 'Roles: admin, analyst, viewer. Admins manage providers and users.' },
      { n: 3, title: 'Protect secrets', body: 'Set a strong SECRET_KEY (encrypts provider keys) before production, and do not rotate it afterwards or stored keys must be re-entered.' },
    ],
  },
]

export default function Tutorial() {
  const [active, setActive] = useState(SECTIONS[0].key)
  const section = SECTIONS.find((s) => s.key === active)!

  return (
    <div>
      <div className="mb-4">
        <h2 className="font-semibold text-lg">Tutorial</h2>
        <p className="text-sm text-inksec">A guided walkthrough of every part of CrawlOps.</p>
      </div>

      <div className="lg:grid lg:grid-cols-[220px_1fr] lg:gap-6">
        {/* tab nav */}
        <nav className="flex lg:flex-col gap-1 overflow-x-auto pb-2 lg:pb-0 mb-4 lg:mb-0">
          {SECTIONS.map(({ key, label, Icon }) => (
            <button key={key} onClick={() => setActive(key)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition
                ${active === key ? 'bg-ink text-white' : 'text-inksec hover:bg-white'}`}>
              <Icon size={16} stroke={2} className="shrink-0" />{label}
            </button>
          ))}
        </nav>

        {/* content */}
        <div className="min-w-0">
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
                <div className="text-[11px] text-muted mt-1.5 text-center">Illustration — orange rings mark where to click; green notes show the result.</div>
              </div>
            )}

            <ol className="space-y-3">
              {section.steps.map((s) => (
                <li key={s.n} className="flex gap-3">
                  <span className="w-7 h-7 rounded-full bg-plane border border-grid grid place-items-center text-sm font-semibold shrink-0 tabular-nums">{s.n}</span>
                  <div className="min-w-0">
                    <div className="font-medium text-sm">{s.title}</div>
                    <p className="text-sm text-inksec leading-relaxed mt-0.5">{s.body}</p>
                    {s.tip && (
                      <div className="mt-1.5 text-[13px] text-[#006300] bg-[#0ca30c]/8 border border-[#0ca30c]/20 rounded-lg px-2.5 py-1.5">
                        Tip: {s.tip}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className="flex justify-between mt-4">
            <button
              onClick={() => { const i = SECTIONS.findIndex((s) => s.key === active); if (i > 0) setActive(SECTIONS[i - 1].key) }}
              disabled={SECTIONS[0].key === active}
              className="px-4 py-2 rounded-xl text-sm border border-grid bg-white disabled:opacity-40">Previous</button>
            <button
              onClick={() => { const i = SECTIONS.findIndex((s) => s.key === active); if (i < SECTIONS.length - 1) setActive(SECTIONS[i + 1].key) }}
              disabled={SECTIONS[SECTIONS.length - 1].key === active}
              className="px-4 py-2 rounded-xl text-sm bg-ink text-white disabled:opacity-40">Next</button>
          </div>
        </div>
      </div>
    </div>
  )
}
