import { IconAntenna, IconLock } from '@tabler/icons-react'
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

  return (
    <div className="min-h-[100dvh] grid place-items-center bg-plane px-4">
      <form onSubmit={submit} className="w-full max-w-sm bg-white border border-grid rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-8 h-8 rounded-lg bg-ink grid place-items-center">
            <IconAntenna size={18} color="#fcfcfb" stroke={2} />
          </span>
          <span className="font-bold text-lg tracking-tight">Crawl<span className="text-[#2a78d6]">Ops</span></span>
        </div>
        <p className="text-sm text-inksec mb-5">Sign in to your workspace.</p>

        <label className="block text-sm mb-3">Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus
            className="w-full border border-grid rounded-xl px-3 py-2 mt-1" />
        </label>
        <label className="block text-sm mb-4">Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-grid rounded-xl px-3 py-2 mt-1" />
        </label>

        {err && <div className="text-sm text-[#d03b3b] mb-3">{err}</div>}
        <button disabled={busy}
          className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-xl bg-ink text-white text-sm font-medium disabled:opacity-50 active:scale-[0.99]">
          <IconLock size={15} stroke={2} />{busy ? 'Signing in' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
