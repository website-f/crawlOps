import { IconCheck, IconLock, IconX } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'
import { blobUrl, del, get, post } from '../lib/api'

/* Live login window. You see the real login page (streamed) and type on it directly —
   keystrokes and clicks are forwarded to a real anti-detect browser running on the
   crawler's own IP, so the session is genuine (not a cookie transplant) and won't get
   flagged as a suspicious login. It captures + closes itself the moment you're in. */
const SPECIAL: Record<string, string> = {
  Enter: 'Enter', Backspace: 'Backspace', Tab: 'Tab', Delete: 'Delete', Escape: 'Escape',
  ArrowUp: 'ArrowUp', ArrowDown: 'ArrowDown', ArrowLeft: 'ArrowLeft', ArrowRight: 'ArrowRight',
}

export default function LoginBrowser({ platform, onDone, onClose }: {
  platform: string; onDone: () => void; onClose: () => void
}) {
  const [sid, setSid] = useState<string | null>(null)
  const [vp, setVp] = useState({ width: 1280, height: 800 })
  const [frame, setFrame] = useState<string>('')
  const [status, setStatus] = useState('Starting secure browser…')
  const [viaProxy, setViaProxy] = useState(false)
  const [busy, setBusy] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const sidRef = useRef<string | null>(null)
  const lastUrl = useRef<string>('')
  const finishing = useRef(false)

  useEffect(() => {
    let alive = true
    post<{ sid: string; width: number; height: number; via_proxy?: boolean }>('/sources/login/start', { platform })
      .then((r) => {
        if (!alive) return
        setSid(r.sid); sidRef.current = r.sid; setVp({ width: r.width, height: r.height })
        setViaProxy(!!r.via_proxy)
        setStatus('Log in on the page below — type and click directly.')
        setTimeout(() => stageRef.current?.focus(), 300)
      })
      .catch(() => setStatus('Login service unavailable. Is loginsvc running?'))
    return () => {
      alive = false
      if (sidRef.current) del(`/sources/login/${sidRef.current}`).catch(() => {})
      if (lastUrl.current) URL.revokeObjectURL(lastUrl.current)
    }
  }, [platform])

  // live frame stream
  useEffect(() => {
    if (!sid) return
    let stop = false
    const tick = async () => {
      try {
        const url = await blobUrl(`/sources/login/${sid}/frame`)
        if (stop) { URL.revokeObjectURL(url); return }
        if (lastUrl.current) URL.revokeObjectURL(lastUrl.current)
        lastUrl.current = url; setFrame(url)
      } catch { /* transient */ }
    }
    const iv = setInterval(tick, 1000); tick()
    return () => { stop = true; clearInterval(iv) }
  }, [sid])

  // auto-detect a completed login → capture + close
  useEffect(() => {
    if (!sid) return
    let stop = false
    const iv = setInterval(async () => {
      if (stop || finishing.current) return
      try {
        const s = await get<{ logged_in: boolean }>(`/sources/login/${sid}/status`)
        if (s.logged_in && !finishing.current) { setStatus('Logged in — saving session…'); setTimeout(finish, 1000) }
      } catch { /* transient */ }
    }, 2500)
    return () => { stop = true; clearInterval(iv) }
  }, [sid])

  const send = (action: string, payload: any) => { if (sid) post(`/sources/login/${sid}/${action}`, payload).catch(() => {}) }

  const onImgClick = (e: React.MouseEvent<HTMLImageElement>) => {
    stageRef.current?.focus()
    const img = imgRef.current; if (!img) return
    const rect = img.getBoundingClientRect()
    send('click', { x: ((e.clientX - rect.left) / rect.width) * vp.width, y: ((e.clientY - rect.top) / rect.height) * vp.height })
  }
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.ctrlKey || e.metaKey) return                 // let copy/paste through to onPaste
    if (SPECIAL[e.key]) { e.preventDefault(); send('key', { key: SPECIAL[e.key] }) }
    else if (e.key.length === 1) { e.preventDefault(); send('type', { text: e.key }) }
  }
  const onPaste = (e: React.ClipboardEvent) => {
    const t = e.clipboardData.getData('text'); if (t) { e.preventDefault(); send('type', { text: t }) }
  }

  const finish = async () => {
    if (!sid || finishing.current) return
    finishing.current = true; setBusy(true); setStatus('Capturing session…')
    try {
      const r = await post<{ ok: boolean; imported: number }>(`/sources/login/${sid}/finish`, { platform })
      sidRef.current = null; setStatus(`Connected ${platform} (${r.imported} cookies).`); onDone()
    } catch (e: any) { finishing.current = false; setStatus(`Could not save: ${String(e.message).slice(0, 80)}`); setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-3">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl border border-grid shadow-xl w-full max-w-3xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-grid">
          <span className="font-semibold capitalize">Log in to {platform}</span>
          {viaProxy && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#0ca30c]/10 text-[#006300] inline-flex items-center gap-1"><IconLock size={11} stroke={2} />via your proxy</span>}
          <span className="text-xs text-inksec ml-2">{status}</span>
          <button onClick={onClose} className="ml-auto p-1 rounded-lg hover:bg-plane"><IconX size={18} stroke={2} /></button>
        </div>

        <div className="p-3">
          <div ref={stageRef} tabIndex={0} onKeyDown={onKeyDown} onPaste={onPaste}
            className="relative bg-black rounded-xl overflow-hidden outline-none focus:ring-2 focus:ring-[#2a78d6]"
            style={{ aspectRatio: `${vp.width}/${vp.height}` }}>
            {frame ? (
              <img ref={imgRef} src={frame} onClick={onImgClick}
                className="w-full h-full object-contain cursor-text select-none" draggable={false}
                onWheel={(e) => send('scroll', { dy: e.deltaY })} />
            ) : (
              <div className="absolute inset-0 grid place-items-center text-white/60 text-sm">Loading live browser…</div>
            )}
          </div>

          <div className="flex items-center justify-between mt-3 gap-3">
            <p className="text-[11px] text-muted max-w-lg">
              Click a field and <b>type directly</b> (paste works too) — including 2FA / CAPTCHA. This is a real
              browser on the crawler's own IP, so the login is genuine and stays logged in. It saves and closes
              automatically the moment you're in. Nothing is stored except the resulting session.
            </p>
            <button onClick={finish} disabled={busy || !sid}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#0ca30c] text-white text-sm disabled:opacity-50 active:scale-[0.98] shrink-0">
              <IconCheck size={15} stroke={2} />Save now
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
