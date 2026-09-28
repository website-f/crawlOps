import { IconCheck, IconPlugConnected, IconX } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtNum, get, post } from '../lib/api'

// entity-fixed slot colors for providers (validated categorical palette order)
const PROVIDER_COLOR: Record<string, string> = {
  groq: '#2a78d6', openrouter: '#1baf7a', mistral: '#eda100',
  huggingface: '#008300', deepseek: '#4a3aa7', openai: '#e34948', unknown: '#898781',
}

interface Provider { name: string; tier: string }
interface TestResult { provider: string; ok: boolean; latency_ms?: number; served_model?: string; error?: string }
interface Usage {
  by_provider: { provider: string; prompt: number; completion: number; calls: number }[]
  by_task: { task: string; prompt: number; completion: number; calls: number }[]
  daily: { day: string; provider: string; tokens: number }[]
  fallback_events: { at: string; task: string; model: string; provider: string }[]
}

export default function AIEngine() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [tests, setTests] = useState<Record<string, TestResult | 'testing'>>({})
  const [usage, setUsage] = useState<Usage | null>(null)

  useEffect(() => {
    get<Provider[]>('/ai/providers').then(setProviders)
    get<Usage>('/ai/usage?days=7').then(setUsage).catch(() => {})
  }, [])

  const test = async (name: string) => {
    setTests((t) => ({ ...t, [name]: 'testing' }))
    const r = await post<TestResult>(`/ai/providers/${name}/test`)
    setTests((t) => ({ ...t, [name]: r }))
  }

  const dailyRows = useMemo(() => {
    if (!usage) return []
    const byDay: Record<string, any> = {}
    for (const r of usage.daily) {
      byDay[r.day] = byDay[r.day] || { day: r.day.slice(5) }
      byDay[r.day][r.provider] = r.tokens
    }
    return Object.values(byDay)
  }, [usage])
  const provsInData = Object.keys(PROVIDER_COLOR).filter((p) => usage?.daily.some((d) => d.provider === p))

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-semibold text-lg">AI Engine</h2>
        <p className="text-sm text-inksec mt-0.5">
          Free tiers run first (Groq, OpenRouter, Mistral, HuggingFace), paid last (DeepSeek, OpenAI).
          A rate-limited provider cools down for 5 minutes while the chain moves on automatically.
          Keys live in <code>.env</code>; blank keys are skipped.
        </p>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {providers.map((p, i) => {
          const t = tests[p.name]
          return (
            <div key={p.name} className="bg-white border border-grid rounded-2xl p-4">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: PROVIDER_COLOR[p.name] }} />
                <span className="font-semibold capitalize">{p.name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium
                  ${p.tier === 'free' ? 'bg-[#0ca30c]/10 text-[#006300]' : 'bg-grid text-inksec'}`}>
                  {p.tier} tier
                </span>
                <span className="ml-auto text-xs text-muted">#{i + 1} in chain</span>
              </div>
              <div className="mt-3 flex items-center gap-2 min-w-0">
                <button onClick={() => test(p.name)} disabled={t === 'testing'}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ink text-white text-xs
                             disabled:opacity-50 active:scale-[0.98] whitespace-nowrap shrink-0">
                  <IconPlugConnected size={13} stroke={2} />
                  {t === 'testing' ? 'Testing' : 'Test connection'}
                </button>
                {t && t !== 'testing' && (
                  t.ok
                    ? <span className="inline-flex items-center gap-1 text-xs text-[#006300] font-medium truncate">
                        <IconCheck size={13} stroke={2.5} className="shrink-0" />{t.latency_ms}ms · {t.served_model}
                      </span>
                    : <span className="inline-flex items-center gap-1 text-xs text-[#d03b3b] truncate" title={t.error}>
                        <IconX size={13} stroke={2.5} className="shrink-0" />{t.error?.slice(0, 60)}
                      </span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {usage && (
        <>
          <div className="bg-white border border-grid rounded-2xl p-4">
            <div className="text-sm font-medium mb-2">Tokens per day by provider (7d)</div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={dailyRows} barCategoryGap="25%">
                <CartesianGrid stroke="#e1e0d9" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#898781' }} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#898781' }} tickFormatter={(v) => fmtNum(v)} axisLine={false} tickLine={false} width={44} />
                <Tooltip cursor={{ fill: 'rgba(11,11,11,0.04)' }} contentStyle={{ fontSize: 12, borderRadius: 10, border: '1px solid #e1e0d9' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {provsInData.map((pf) => (
                  <Bar key={pf} dataKey={pf} stackId="t" fill={PROVIDER_COLOR[pf]} stroke="#fcfcfb" strokeWidth={1} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="grid lg:grid-cols-2 gap-5">
            <div className="bg-white border border-grid rounded-2xl p-4">
              <div className="text-sm font-medium mb-2">Usage by provider (7d)</div>
              <UsageTable rows={usage.by_provider.map((r) => ({ name: r.provider, ...r }))} />
            </div>
            <div className="bg-white border border-grid rounded-2xl p-4">
              <div className="text-sm font-medium mb-2">Usage by pipeline task (7d)</div>
              <UsageTable rows={usage.by_task.map((r) => ({ name: r.task, ...r }))} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function UsageTable({ rows }: { rows: { name: string; prompt: number; completion: number; calls: number }[] }) {
  return (
    <table className="w-full text-sm">
      <thead><tr className="text-xs text-muted text-left">
        <th className="font-normal pb-1">name</th><th className="font-normal text-right">calls</th>
        <th className="font-normal text-right">prompt</th><th className="font-normal text-right">completion</th>
      </tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.name} className="border-t border-grid/60">
            <td className="py-1.5 capitalize">{r.name}</td>
            <td className="text-right tabular-nums">{r.calls}</td>
            <td className="text-right tabular-nums">{fmtNum(r.prompt)}</td>
            <td className="text-right tabular-nums">{fmtNum(r.completion)}</td>
          </tr>
        ))}
        {rows.length === 0 && <tr><td className="text-muted py-2" colSpan={4}>No AI calls yet.</td></tr>}
      </tbody>
    </table>
  )
}
