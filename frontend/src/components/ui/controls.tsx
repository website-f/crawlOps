import { IconCheck, IconChevronDown, IconSearch, IconX } from '@tabler/icons-react'
import { useEffect, useRef, useState } from 'react'

/* Advanced form primitives shared across the app — all on the design system
   (accent token, rounded-xl, border-grid, accent focus rings). */

// ---- TagInput: chips + free entry (issues list, keyword terms) ----------
export function TagInput({ value, onChange, placeholder, suggestions }: {
  value: string[]; onChange: (v: string[]) => void; placeholder?: string; suggestions?: string[]
}) {
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const add = (raw: string) => {
    const t = raw.trim()
    if (t && !value.includes(t)) onChange([...value, t])
    setDraft('')
  }
  const remove = (t: string) => onChange(value.filter((x) => x !== t))
  const hints = (suggestions || []).filter((s) => !value.includes(s) && (!draft || s.toLowerCase().includes(draft.toLowerCase()))).slice(0, 6)

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 border border-grid rounded-xl px-2 py-2 bg-white focus-within:ring-2 focus-within:ring-accent/30 focus-within:border-accent transition"
        onClick={() => inputRef.current?.focus()}>
        {value.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 pl-2.5 pr-1.5 py-1 rounded-lg bg-accent/10 text-accent-ink text-[12.5px] font-medium">
            {t}
            <button type="button" onClick={(e) => { e.stopPropagation(); remove(t) }} className="hover:text-danger"><IconX size={13} stroke={2.2} /></button>
          </span>
        ))}
        <input ref={inputRef} value={draft} placeholder={value.length ? '' : (placeholder || 'Type and press Enter')}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(draft) }
            else if (e.key === 'Backspace' && !draft && value.length) remove(value[value.length - 1])
          }}
          onBlur={() => draft && add(draft)}
          className="flex-1 min-w-[8rem] bg-transparent text-sm px-1 py-0.5 focus:outline-none" />
      </div>
      {hints.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {hints.map((s) => (
            <button key={s} type="button" onClick={() => add(s)}
              className="text-[12px] px-2 py-0.5 rounded-full border border-grid text-inksec hover:border-accent hover:text-accent transition">+ {s}</button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---- MultiSelect: searchable dropdown with checkboxes -------------------
export interface Opt { value: string; label: string; color?: string }
export function MultiSelect({ value, onChange, options, placeholder = 'Select…', searchable = true }: {
  value: string[]; onChange: (v: string[]) => void; options: Opt[]; placeholder?: string; searchable?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', onDoc); return () => document.removeEventListener('mousedown', onDoc)
  }, [])
  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v])
  const shown = options.filter((o) => !q || o.label.toLowerCase().includes(q.toLowerCase()))
  const selected = options.filter((o) => value.includes(o.value))

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-1.5 min-h-[2.5rem] border border-grid rounded-xl px-2.5 py-1.5 bg-white text-left hover:border-muted transition">
        <div className="flex flex-wrap gap-1 flex-1 min-w-0">
          {selected.length === 0 && <span className="text-sm text-muted px-1">{placeholder}</span>}
          {selected.map((o) => (
            <span key={o.value} className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-lg bg-plane border border-grid text-[12px]">
              {o.color && <span className="w-2 h-2 rounded-full" style={{ background: o.color }} />}
              {o.label}
              <button type="button" onClick={(e) => { e.stopPropagation(); toggle(o.value) }} className="text-muted hover:text-danger"><IconX size={12} stroke={2.2} /></button>
            </span>
          ))}
        </div>
        <IconChevronDown size={16} stroke={2} className={`shrink-0 text-muted transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute z-40 mt-1 w-full bg-surface border border-grid rounded-xl shadow-float overflow-hidden animate-[pop_.14s_ease-out]">
          {searchable && (
            <div className="flex items-center gap-2 px-3 py-2 border-b border-grid">
              <IconSearch size={14} stroke={2} className="text-muted" />
              <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…"
                className="flex-1 text-sm bg-transparent focus:outline-none" />
            </div>
          )}
          <div className="max-h-60 overflow-y-auto py-1">
            {shown.map((o) => {
              const on = value.includes(o.value)
              return (
                <button key={o.value} type="button" onClick={() => toggle(o.value)}
                  className="w-full flex items-center gap-2.5 px-3 py-1.5 text-sm hover:bg-plane text-left">
                  <span className={`w-4 h-4 rounded grid place-items-center shrink-0 border ${on ? 'bg-accent border-accent' : 'border-grid'}`}>
                    {on && <IconCheck size={12} stroke={3} className="text-white" />}
                  </span>
                  {o.color && <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: o.color }} />}
                  <span className="truncate">{o.label}</span>
                </button>
              )
            })}
            {shown.length === 0 && <div className="px-3 py-2 text-sm text-muted">No matches</div>}
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Segmented: pill toggle group ---------------------------------------
export function Segmented<T extends string>({ value, onChange, options }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]
}) {
  return (
    <div className="inline-flex items-center gap-0.5 p-0.5 rounded-xl bg-plane border border-grid">
      {options.map((o) => (
        <button key={o.value} type="button" onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 rounded-lg text-[13px] font-medium transition ${value === o.value ? 'bg-surface text-ink shadow-card' : 'text-inksec hover:text-ink'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}
