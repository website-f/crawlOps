import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import { get } from '../lib/api'
import { SENTIMENT } from '../lib/platform'

;(L as any)._crawlops = true

interface GeoPost { id: number; lat: number; lon: number; platform: string; title: string; sentiment: 'pos' | 'neu' | 'neg' | null; url: string }
interface CountryAgg { country: string; name: string; total: number; pos: number; neu: number; neg: number }
interface RegionAgg { country: string; region: string; total: number; pos: number; neu: number; neg: number }

function SentimentBar({ pos, neu, neg }: { pos: number; neu: number; neg: number }) {
  const total = pos + neu + neg || 1
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden w-full">
      {([['pos', pos], ['neu', neu], ['neg', neg]] as const).map(([k, v]) =>
        v > 0 ? <div key={k} style={{ width: `${(v / total) * 100}%`, background: SENTIMENT[k].color }} /> : null)}
    </div>
  )
}

export default function MapView() {
  const [posts, setPosts] = useState<GeoPost[]>([])
  const [countries, setCountries] = useState<CountryAgg[]>([])
  const [regions, setRegions] = useState<RegionAgg[]>([])
  const [focus, setFocus] = useState<string | null>(null)

  useEffect(() => {
    get<GeoPost[]>('/posts/geo').then(setPosts).catch(() => {})
    get<{ countries: CountryAgg[]; regions: RegionAgg[] }>('/analytics/geo?days=90')
      .then((d) => { setCountries(d.countries); setRegions(d.regions) }).catch(() => {})
  }, [])

  return (
    <div className="grid lg:grid-cols-[1fr_320px] gap-5">
      <div className="bg-white border border-grid rounded-2xl overflow-hidden">
        <div className="px-4 py-3 text-sm font-medium border-b border-grid flex items-center gap-3 flex-wrap">
          Geographic distribution
          <span className="text-muted font-normal">{posts.length} geolocated posts</span>
          <span className="ml-auto flex gap-3 text-xs">
            {(['pos', 'neu', 'neg'] as const).map((k) => (
              <span key={k} className="inline-flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: SENTIMENT[k].color }} />{SENTIMENT[k].label}
              </span>
            ))}
          </span>
        </div>
        <MapContainer center={[20, 20]} zoom={2} style={{ height: '68vh', width: '100%' }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {posts.map((p) => (
            <CircleMarker key={p.id} center={[p.lat, p.lon]} radius={7}
              pathOptions={{ color: '#fcfcfb', weight: 2,
                fillColor: p.sentiment ? SENTIMENT[p.sentiment].color : '#898781', fillOpacity: 0.9 }}>
              <Popup>
                <div className="text-sm max-w-56">
                  <b className="capitalize">{p.platform}</b>: {p.title}
                  {p.url && <div><a href={p.url} target="_blank" rel="noreferrer" className="text-blue-600 underline">open original</a></div>}
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="space-y-5">
        <div className="bg-white border border-grid rounded-2xl p-4">
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
            {!countries.length && <div className="text-muted text-sm py-6 text-center">No geolocated posts yet. The judge extracts locations, then Nominatim resolves them.</div>}
          </div>
        </div>

        {focus && (
          <div className="bg-white border border-grid rounded-2xl p-4">
            <div className="text-sm font-medium mb-3">Regions in {countries.find((c) => c.country === focus)?.name || focus?.toUpperCase()}</div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {regions.filter((r) => r.country === focus).map((r) => (
                <div key={r.region} className="text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span>{r.region}</span><span className="ml-auto tabular-nums text-inksec">{r.total}</span>
                  </div>
                  <SentimentBar pos={r.pos} neu={r.neu} neg={r.neg} />
                </div>
              ))}
              {!regions.filter((r) => r.country === focus).length && <div className="text-muted text-sm">No region detail.</div>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
