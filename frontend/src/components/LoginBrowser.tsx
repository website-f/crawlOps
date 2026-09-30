import { IconArrowBackUp, IconCheck, IconX } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { blobUrl, del, get, post } from '../lib/api'

/* Live interactive remote browser for logging into a platform inside CrawlOps.
   Driven by the Playwright+Camoufox login service: you see the real login page as
   a screenshot stream and click/type on it exactly like your own browser. */
export default function LoginBrowser({ platform, onDone, onClose }: {
  platform: string; onDone: () => void; onClose: () => void
}) {
  const [sid, setSid] = useState<string | null>(null)
  const [vp, setVp] = useState({ width: 1280, height: 800 })
  const [frame, setFrame] = useState<string>('')
  const [text, setText] = useState('')
  const [status, setStatus] = useState('Starting secure browser…')
  const [busy, setBusy] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)
  const sidRef = useRef<string | null>(null)
  const lastUrl = useRef<string>('')
  const finishing = useRef(false)

  useEffect(() => {
    let alive = true
    post<{ sid: string; width: number; height: number }>('/sources/login/start', { platform })
      .then((r) => { if (!alive) return; setSid(r.sid); sidRef.current = r.sid; setVp({ width: r.width, height: r.height }); setStatus('Log in on the page below.') })
      .catch(() => setStatus('Login service unavailable. Is loginsvc running?'))
    return () => {
      alive = false
      if (sidRef.current) del(`/sources/login/${sidRef.current}`).catch(() => {})
      if (lastUrl.current) URL.revokeObjectURL(lastUrl.current)
    }
  }, [platform])

  // poll the live frame
  useEffect(() => {
    if (!sid) return
    let stop = false
    const tick = async () => {
      try {
        const url = await blobUrl(`/sources/login/${sid}/frame`)
        if (stop) { URL.revokeObjectURL(url); return }
        if (lastUrl.current) URL.revokeObjectURL(lastUrl.current)
        lastUrl.current = url
        setFrame(url)
      } catch { /* transient */ }
    }
    const iv = setInterval(tick, 1200)
    tick()
    return () => { stop = true; clearInterval(iv) }
  }, [sid])

  const send = (action: string, payload: any) => {
    if (!sid) return
    post(`/sources/login/${sid}/${action}`, payload).catch(() => {})
  }

  const onImgClick = (e: React.MouseEvent<HTMLImageElement>) => {
    const img = imgRef.current
    if (!img) return
    const rect = img.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * vp.width
    const y = ((e.clientY - rect.top) / rect.height) * vp.height
    send('click', { x, y })
  }

  const typeText = () => { if (text) { send('type', { text }); setText('') } }

  const finish = async () => {
    if (!sid || finishing.current) return
    finishing.current = true
    setBusy(true); setStatus('Capturing session…')
    try {
      const r = await post<{ ok: boolean; imported: number }>(`/sources/login/${sid}/finish`, { platform })
      sidRef.current = null
      setStatus(`Connected ${platform} (${r.imported} cookies).`)
      onDone()
    } catch (e: any) {
      finishing.current = false
      setStatus(`Could not save: ${String(e.message).slice(0, 80)}`)
      setBusy(false)
    }
  }

  // auto-detect a completed login (platform auth cookie appears) and capture + close
  // automatically — no need to eyeball the page and click Save.
  useEffect(() => {
    if (!sid) return
    let stop = false
    const iv = setInterval(async () => {
      if (stop || finishing.current) return
      try {
        const s = await get<{ logged_in: boolean }>(`/sources/login/${sid}/status`)
        if (s.logged_in && !finishing.current) {
          setStatus('Login detected — saving session…')
          setTimeout(() => finish(), 1200)   // let post-login cookies settle
        }
      } catch { /* transient */ }
    }, 2500)
    return () => { stop = true; clearInterval(iv) }
  }, [sid])

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-3">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl border border-grid shadow-xl w-full max-w-3xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-grid">
          <span className="font-semibold capitalize">Log in to {platform}</span>
          <span className="text-xs text-inksec ml-2">{status}</span>
          <button onClick={onClose} className="ml-auto p-1 rounded-lg hover:bg-plane"><IconX size={18} stroke={2} /></button>
        </div>

        <div className="p-3">
          <div className="relative bg-black rounded-xl overflow-hidden" style={{ aspectRatio: `${vp.width}/${vp.height}` }}>
            {frame ? (
              <img ref={imgRef} src={frame} onClick={onImgClick}
                className="w-full h-full object-contain cursor-pointer select-none" draggable={false}
                onWheel={(e) => send('scroll', { dy: e.deltaY })} />
            ) : (
              <div className="absolute inset-0 grid place-items-center text-white/60 text-sm">Loading live browser…</div>
            )}
          </div>

          {/* keyboard bar */}
          <div className="flex flex-wrap items-center gap-2 mt-3">
            <input value={text} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); typeText() } }}
              placeholder="Click a field above, type here, then Send"
              className="flex-1 min-w-48 border border-grid rounded-lg px-3 py-2 text-sm" />
            <button onClick={typeText} className="px-3 py-2 rounded-lg bg-ink text-white text-sm">Send text</button>
            <button onClick={() => send('key', { key: 'Enter' })} className="px-3 py-2 rounded-lg border border-grid text-sm">Enter</button>
            <button onClick={() => send('key', { key: 'Tab' })} className="px-3 py-2 rounded-lg border border-grid text-sm">Tab</button>
            <button onClick={() => send('key', { key: 'Backspace' })} title="Backspace"
              className="px-3 py-2 rounded-lg border border-grid text-sm"><IconArrowBackUp size={15} stroke={2} /></button>
          </div>

          <div className="flex items-center justify-between mt-3">
            <p className="text-[11px] text-muted max-w-md">
              This is the real login page, opened through your crawl proxy so the session matches
              the IP the crawler uses. Type your credentials (and 2FA / CAPTCHA) here — nothing is
              stored. It saves and closes automatically once you're logged in; Save session is a manual fallback.
            </p>
            <button onClick={finish} disabled={busy || !sid}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#0ca30c] text-white text-sm disabled:opacity-50 active:scale-[0.98]">
              <IconCheck size={15} stroke={2} />Save session
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
