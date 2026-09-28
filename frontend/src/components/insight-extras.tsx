const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// Day x hour activity heatmap. Single-hue sequential ramp (dataviz: blue).
export function HeatmapGrid({ grid }: { grid: number[][] }) {
  const max = Math.max(1, ...grid.flat())
  const shade = (v: number) => {
    if (v === 0) return '#f4f3ef'
    const t = 0.15 + (v / max) * 0.85
    return `rgba(42, 120, 214, ${t.toFixed(2)})`
  }
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-0.5" style={{ gridTemplateColumns: `28px repeat(24, minmax(9px, 1fr))` }}>
        <div />
        {Array.from({ length: 24 }).map((_, h) => (
          <div key={h} className="text-[8px] text-muted text-center">{h % 6 === 0 ? h : ''}</div>
        ))}
        {grid.map((row, d) => (
          <>
            <div key={`l${d}`} className="text-[10px] text-inksec pr-1 flex items-center">{DOW[d]}</div>
            {row.map((v, h) => (
              <div key={`${d}-${h}`} title={`${DOW[d]} ${h}:00 — ${v}`}
                className="aspect-square rounded-[2px]" style={{ background: shade(v) }} />
            ))}
          </>
        ))}
      </div>
    </div>
  )
}

// Topic co-occurrence constellation: nodes on a circle, edges weighted, node hue by sentiment.
export function ConstellationGraph({ nodes, edges }: {
  nodes: { topic: string; freq: number; sentiment: number }[]
  edges: { a: string; b: string; weight: number }[]
}) {
  if (!nodes.length) return <div className="text-muted text-sm py-16 text-center">Needs enriched posts with topics.</div>
  const size = 340, cx = size / 2, cy = size / 2, R = 130
  const maxFreq = Math.max(...nodes.map((n) => n.freq), 1)
  const maxW = Math.max(...edges.map((e) => e.weight), 1)
  const pos: Record<string, { x: number; y: number }> = {}
  nodes.forEach((n, i) => {
    const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2
    pos[n.topic] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R }
  })
  const hue = (s: number) => s > 0.15 ? '#0ca30c' : s < -0.15 ? '#d03b3b' : '#898781'
  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-md mx-auto" style={{ maxHeight: 360 }}>
        {edges.map((e, i) => {
          const p1 = pos[e.a], p2 = pos[e.b]
          if (!p1 || !p2) return null
          return <line key={i} x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
            stroke="#c3c2b7" strokeWidth={0.5 + (e.weight / maxW) * 2.5} strokeOpacity={0.4} />
        })}
        {nodes.map((n) => {
          const p = pos[n.topic]
          const r = 4 + (n.freq / maxFreq) * 10
          return (
            <g key={n.topic}>
              <circle cx={p.x} cy={p.y} r={r} fill={hue(n.sentiment)} stroke="#fcfcfb" strokeWidth={1.5} />
              <text x={p.x} y={p.y - r - 3} textAnchor="middle" className="fill-inksec" style={{ fontSize: 9 }}>{n.topic}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
