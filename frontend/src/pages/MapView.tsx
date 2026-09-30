import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import { get } from '../lib/api'
import { SENTIMENT } from '../lib/platform'

;(L as any)._crawlops = true

interface Topic { id: number; name: string }
interface CountryAgg { country: string; name: string; lat: number | null; lon: number | null; total: number; pos: number; neu: number; neg: number }
interface RegionAgg { country: string; region: string; total: number; pos: number; neu: number; neg: number }
interface GeoPost { id: number; lat: number; lon: number; platform: string; title: string; sentiment: 'pos' | 'neu' | 'neg' | null; url: string }

function SentimentBar({ pos, neu, neg }: { pos: number; neu: number; neg: number }) {
  const total = pos + neu + neg || 1
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden w-full">
      {([['pos', pos], ['neu', neu], ['neg', neg]] as const).map(([k, v]) =>
        v > 0 ? <div key={k} style={{ width: `${(v / total) * 100}%`, background: SENTIMENT[k].color }} /> : null)}
    </div>
  )
}

const dominant = (c: { pos: number; neu: number; neg: number }) =>
  c.neg > c.pos && c.neg >= c.neu ? 'neg' : c.pos > c.neg && c.pos >= c.neu ? 'pos' : 'neu'

export default function MapView() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [topicId, setTopicId] = useState<number | ''>('')
  const [countries, setCountries] = useState<CountryAgg[]>([])
  const [regions, setRegions] = useState<RegionAgg[]>([])
  const [posts, setPosts] = useState<GeoPost[]>([])
  const [focus, setFocus] = useState<string | null>(null)

  useEffect(() => { get<Topic[]>('/topics').then(setTopics).catch(() => {}) }, [])
  useEffect(() => {
    const scope = `?days=90${topicId ? `&topic_id=${topicId}` : ''}`
    get<{ countries: CountryAgg[]; regions: RegionAgg[] }>(`/analytics/geo${scope}`)
      .then((d) => { setCountries(d.countries); setRegions(d.regions) }).catch(() => {})
    get<GeoPost[]>(`/posts/geo${topicId ? `?topic_id=${topicId}` : ''}`).then(setPosts).catch(() => {})
  }, [topicId])

  const withCoords = countries.filter((c) => c.lat != null && c.lon != null)
  const maxTotal = Math.max(1, ...withCoords.map((c) => c.total))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold tracking-tight">Map</h1>
        <p className="text-[13px] text-inksec mt-0.5">Where the conversation is coming from, colored by sentiment.</p>
      </div>
      <div className="grid lg:grid-cols-[1fr_320px] gap-5">
      <div className="bg-white border border-grid rounded-2xl shadow-card overflow-hidden">
        <div className="px-4 py-3 text-sm font-medium border-b border-grid flex items-center gap-3 flex-wrap">
          Geographic distribution
          <span className="text-muted font-normal">{withCoords.length} countries · {posts.length} pinned posts</span>
          <select value={topicId} onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : '')}
            className="ml-auto border border-grid rounded-xl px-2.5 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition">
            <option value="">All topics</option>
            {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <MapContainer center={[20, 10]} zoom={2} style={{ height: '68vh', width: '100%' }} worldCopyJump>
          <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {/* country-level markers (deterministic, works without AI) */}
          {withCoords.map((c) => {
            const d = dominant(c)
            const radius = 8 + Math.sqrt(c.total / maxTotal) * 26
            return (
              <CircleMarker key={c.country} center={[c.lat!, c.lon!]} radius={radius}
                pathOptions={{ color: '#fcfcfb', weight: 1.5, fillColor: SENTIMENT[d].color, fillOpacity: 0.55 }}
                eventHandlers={{ click: () => setFocus(c.country) }}>
                <Popup>
                  <div className="text-sm">
                    <b>{c.name}</b> — {c.total} mentions
                    <div className="mt-1 w-40"><SentimentBar pos={c.pos} neu={c.neu} neg={c.neg} /></div>
                  </div>
                </Popup>
              </CircleMarker>
            )
          })}
          {/* precise post pins (only when AI has geocoded a location) */}
          {posts.map((p) => (
            <CircleMarker key={`p${p.id}`} center={[p.lat, p.lon]} radius={5}
              pathOptions={{ color: '#0b0b0b', weight: 1, fillColor: p.sentiment ? SENTIMENT[p.sentiment].color : '#898781', fillOpacity: 0.9 }}>
              <Popup><div className="text-sm max-w-56"><b className="capitalize">{p.platform}</b>: {p.title}</div></Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="space-y-5">
        <div className="bg-white border border-grid rounded-2xl shadow-card p-4">
          <div className="text-sm font-medium mb-3">By country</div>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {countries.map((c) => (
              <button key={c.country} onClick={() => setFocus(focus === c.country ? null : c.country)}
                className={`w-full text-left p-2 rounded-lg transition ${focus === c.country ? 'bg-plane' : 'hover:bg-plane'}`}>
                <div className="flex items-center gap-2 text-sm mb-1">
                  <span className="font-medium">{c.name || c.country?.toUpperCase()}</span>
                  <span className="ml-auto tabular-nums text-inksec">{c.total}</span>
                </div>
                <SentimentBar pos={c.pos} neu={c.neu} neg={c.neg} />
              </button>
            ))}
            {!countries.length && <div className="text-muted text-sm py-6 text-center">No geolocated posts yet. Country is derived from each source's domain — news and web sources populate this automatically once crawled.</div>}
          </div>
        </div>

        {focus && (
          <div className="bg-white border border-grid rounded-2xl shadow-card p-4">
            <div className="text-sm font-medium mb-3">Regions in {countries.find((c) => c.country === focus)?.name || focus?.toUpperCase()}</div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {regions.filter((r) => r.country === focus).map((r) => (
                <div key={r.region} className="text-sm">
                  <div className="flex items-center gap-2 mb-1"><span>{r.region}</span><span className="ml-auto tabular-nums text-inksec">{r.total}</span></div>
                  <SentimentBar pos={r.pos} neu={r.neu} neg={r.neg} />
                </div>
              ))}
              {!regions.filter((r) => r.country === focus).length && <div className="text-muted text-sm">Region detail needs AI-inferred locations.</div>}
            </div>
          </div>
        )}
      </div>
      </div>
    </div>
  )
}
