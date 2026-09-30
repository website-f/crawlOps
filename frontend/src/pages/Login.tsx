import { IconAlertTriangle, IconAntenna, IconLock } from '@tabler/icons-react'
import { useState } from 'react'
import { post, setToken } from '../lib/api'

export default function Login({ onAuthed }: { onAuthed: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      const r = await post<{ token: string }>('/auth/login', { username, password })
      setToken(r.token)
      onAuthed()
    } catch {
      setErr('Invalid username or password')
    }
    setBusy(false)
  }

  const field = 'w-full border border-grid rounded-xl px-3 py-2 mt-1.5 text-sm bg-plane/60 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition'

  return (
    <div className="relative min-h-[100dvh] grid place-items-center bg-plane px-4 overflow-hidden">
      {/* restrained brand wash — a single soft accent glow, not a gradient field */}
      <div aria-hidden className="pointer-events-none absolute -top-40 -right-32 w-[36rem] h-[36rem] rounded-full opacity-[0.07]"
        style={{ background: 'radial-gradient(circle, #2a78d6 0%, transparent 70%)' }} />
      <div aria-hidden className="pointer-events-none absolute -bottom-48 -left-40 w-[40rem] h-[40rem] rounded-full opacity-[0.05]"
        style={{ background: 'radial-gradient(circle, #0b0b0b 0%, transparent 70%)' }} />

      <div className="relative w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-6 justify-center">
          <span className="w-9 h-9 rounded-xl bg-ink grid place-items-center shadow-raise">
            <IconAntenna size={19} color="#fcfcfb" stroke={2} />
          </span>
          <span className="font-bold text-xl tracking-tight">Crawl<span className="text-accent">Ops</span></span>
        </div>

        <form onSubmit={submit} className="bg-surface border border-grid rounded-2xl p-6 shadow-float">
          <h1 className="font-semibold text-[15px] text-ink">Sign in to your workspace</h1>
          <p className="text-[13px] text-inksec mt-1 mb-5">Social &amp; media intelligence, self-hosted.</p>

          <label className="block text-[13px] font-medium text-inksec mb-3">Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus className={field} />
          </label>
          <label className="block text-[13px] font-medium text-inksec mb-4">Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className={field} />
          </label>

          {err && (
            <div className="flex items-center gap-1.5 text-[13px] text-danger bg-danger/5 border border-danger/20 rounded-lg px-3 py-2 mb-3">
              <IconAlertTriangle size={15} stroke={2} className="shrink-0" />{err}
            </div>
          )}
          <button disabled={busy}
            className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-xl bg-ink text-white text-sm font-medium
                       disabled:opacity-50 hover:brightness-110 active:scale-[0.99] transition">
            <IconLock size={15} stroke={2} />{busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
