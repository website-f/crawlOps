import { IconDeviceFloppy, IconSend } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { get, post, put } from '../lib/api'

interface AllSettings {
  cpm: Record<string, number>
  notifiers: { webhook_url: string; telegram_bot_token: string; telegram_chat_id: string }
  pipeline: { default_threshold: number; retention_days: number }
}

export default function Settings() {
  const [s, setS] = useState<AllSettings | null>(null)
  const [saved, setSaved] = useState('')
  const [testResult, setTestResult] = useState('')

  useEffect(() => { get<AllSettings>('/settings').then(setS) }, [])

  const save = async (key: keyof AllSettings) => {
    if (!s) return
    await put(`/settings/${key}`, { value: s[key] })
    setSaved(key); setTimeout(() => setSaved(''), 1500)
  }

  const testNotifiers = async () => {
    setTestResult('testing')
    const r = await post<{ ok: boolean; results: any }>('/settings/notifiers/test')
    setTestResult(r.ok ? 'Sent. Check your channel.' : 'No channel delivered (configure and save first).')
  }

  if (!s) return <div className="text-muted p-10">Loading</div>

  return (
    <div className="max-w-3xl space-y-5">
      <h2 className="font-semibold text-lg">Settings</h2>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">Alert channels</h3>
          <button onClick={() => save('notifiers')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-[#2a78d6]">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'notifiers' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-3">Where alerts are delivered. Both are optional.</p>
        <label className="block text-sm mb-2">Webhook URL
          <input value={s.notifiers.webhook_url}
            onChange={(e) => setS({ ...s, notifiers: { ...s.notifiers, webhook_url: e.target.value } })}
            placeholder="https://hooks.example.com/crawlops"
            className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px]" />
        </label>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="block text-sm">Telegram bot token
            <input value={s.notifiers.telegram_bot_token}
              onChange={(e) => setS({ ...s, notifiers: { ...s.notifiers, telegram_bot_token: e.target.value } })}
              placeholder="123456:ABC..."
              className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px]" />
          </label>
          <label className="block text-sm">Telegram chat ID
            <input value={s.notifiers.telegram_chat_id}
              onChange={(e) => setS({ ...s, notifiers: { ...s.notifiers, telegram_chat_id: e.target.value } })}
              placeholder="-1001234567890"
              className="w-full border border-grid rounded-lg px-3 py-2 mt-1 font-mono text-[13px]" />
          </label>
        </div>
        <div className="flex items-center gap-3 mt-3">
          <button onClick={testNotifiers}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ink text-white text-sm active:scale-[0.98]">
            <IconSend size={14} stroke={2} />Send test
          </button>
          {testResult && testResult !== 'testing' && <span className="text-sm text-inksec">{testResult}</span>}
          {testResult === 'testing' && <span className="text-sm text-muted">testing</span>}
        </div>
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">Pipeline</h3>
          <button onClick={() => save('pipeline')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-[#2a78d6]">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'pipeline' ? 'Saved' : 'Save'}
          </button>
        </div>
        <div className="flex flex-wrap gap-5 mt-2 text-sm">
          <label>Default relevance threshold
            <input type="number" value={s.pipeline.default_threshold}
              onChange={(e) => setS({ ...s, pipeline: { ...s.pipeline, default_threshold: Number(e.target.value) } })}
              className="border border-grid rounded-lg px-2 py-1 w-20 ml-2" />
          </label>
          <label>Retention (days)
            <input type="number" value={s.pipeline.retention_days}
              onChange={(e) => setS({ ...s, pipeline: { ...s.pipeline, retention_days: Number(e.target.value) } })}
              className="border border-grid rounded-lg px-2 py-1 w-20 ml-2" />
          </label>
        </div>
      </section>

      <section className="bg-white border border-grid rounded-2xl p-5">
        <div className="flex items-center mb-1">
          <h3 className="font-semibold">CPM table (RM per 1000 impressions)</h3>
          <button onClick={() => save('cpm')}
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-[#2a78d6]">
            <IconDeviceFloppy size={15} stroke={2} />{saved === 'cpm' ? 'Saved' : 'Save'}
          </button>
        </div>
        <p className="text-sm text-inksec mb-3">Drives the earned media value estimate. Adjust to your market rates.</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {Object.entries(s.cpm).map(([k, v]) => (
            <label key={k} className="text-sm capitalize">{k}
              <input type="number" step="0.5" value={v}
                onChange={(e) => setS({ ...s, cpm: { ...s.cpm, [k]: Number(e.target.value) } })}
                className="w-full border border-grid rounded-lg px-2 py-1 mt-0.5 tabular-nums" />
            </label>
          ))}
        </div>
      </section>
    </div>
  )
}
