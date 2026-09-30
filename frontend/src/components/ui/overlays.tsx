import { IconAlertTriangle, IconCheck, IconInfoCircle, IconX } from '@tabler/icons-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

/* Our own modal / confirm / prompt / toast layer — replaces window.alert/confirm/prompt
   and any default browser chrome. Promise-based so call sites read like the natives:
     if (await dialog.confirm({...})) { ... }
     const name = await dialog.prompt({...})   // null on cancel
     dialog.toast('Saved', 'success')                                            */

type Variant = 'default' | 'danger'
interface ConfirmOpts { title: string; message?: string; confirmText?: string; cancelText?: string; variant?: Variant }
interface PromptOpts { title: string; message?: string; label?: string; placeholder?: string; defaultValue?: string; confirmText?: string; multiline?: boolean }
interface AlertOpts { title: string; message?: string; variant?: Variant }
type Toast = { id: number; msg: string; kind: 'info' | 'success' | 'error' }

interface DialogApi {
  confirm: (o: ConfirmOpts) => Promise<boolean>
  prompt: (o: PromptOpts) => Promise<string | null>
  alert: (o: AlertOpts) => Promise<void>
  toast: (msg: string, kind?: Toast['kind']) => void
}

const Ctx = createContext<DialogApi | null>(null)
export const useDialog = (): DialogApi => {
  const c = useContext(Ctx)
  if (!c) throw new Error('useDialog must be used within <OverlayProvider>')
  return c
}

type ActiveKind = 'confirm' | 'prompt' | 'alert'
interface Active { kind: ActiveKind; opts: any; resolve: (v: any) => void }

export function OverlayProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState<Active | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastId = useRef(1)

  const close = useCallback((val: any) => { setActive((a) => { a?.resolve(val); return null }) }, [])

  const api: DialogApi = {
    confirm: (opts) => new Promise((resolve) => setActive({ kind: 'confirm', opts, resolve })),
    prompt: (opts) => new Promise((resolve) => setActive({ kind: 'prompt', opts, resolve })),
    alert: (opts) => new Promise((resolve) => setActive({ kind: 'alert', opts, resolve })),
    toast: (msg, kind = 'info') => {
      const id = toastId.current++
      setToasts((t) => [...t, { id, msg, kind }])
      setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
    },
  }

  return (
    <Ctx.Provider value={api}>
      {children}
      {active && <DialogModal active={active} onClose={close} />}
      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </Ctx.Provider>
  )
}

function DialogModal({ active, onClose }: { active: Active; onClose: (v: any) => void }) {
  const { kind, opts } = active
  const [value, setValue] = useState(opts.defaultValue || '')
  const inputRef = useRef<HTMLInputElement & HTMLTextAreaElement>(null)
  const cancelValue = kind === 'confirm' ? false : kind === 'prompt' ? null : undefined
  const danger = opts.variant === 'danger'

  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 60)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose(cancelValue)
      if (e.key === 'Enter' && kind !== 'prompt') onClose(kind === 'confirm' ? true : undefined)
      if (e.key === 'Enter' && kind === 'prompt' && !opts.multiline && (e.metaKey || !e.shiftKey)) {
        e.preventDefault(); onClose(value)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => { clearTimeout(t); window.removeEventListener('keydown', onKey) }
  }, [kind, value]) // eslint-disable-line

  return (
    <div className="fixed inset-0 z-[100] grid place-items-center p-4">
      <div className="absolute inset-0 bg-ink/45 backdrop-blur-[2px] animate-[fade_.15s_ease-out]"
        onClick={() => onClose(cancelValue)} />
      <div role="dialog" aria-modal="true"
        className="relative w-full max-w-md bg-surface border border-grid rounded-2xl shadow-float
                   p-5 animate-[pop_.16s_cubic-bezier(.16,1,.3,1)]">
        <div className="flex items-start gap-3">
          <span className={`mt-0.5 grid place-items-center w-8 h-8 rounded-xl shrink-0
            ${danger ? 'bg-danger/10 text-danger' : 'bg-accent/10 text-accent'}`}>
            {danger ? <IconAlertTriangle size={17} stroke={2} /> : <IconInfoCircle size={17} stroke={2} />}
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-[15px] text-ink leading-snug">{opts.title}</h3>
            {opts.message && <p className="text-[13px] text-inksec mt-1 leading-relaxed">{opts.message}</p>}
            {kind === 'prompt' && (
              <label className="block mt-3">
                {opts.label && <span className="block text-[12px] text-inksec mb-1">{opts.label}</span>}
                {opts.multiline ? (
                  <textarea ref={inputRef as any} rows={4} value={value} placeholder={opts.placeholder}
                    onChange={(e) => setValue(e.target.value)}
                    className="w-full border border-grid rounded-xl px-3 py-2 text-sm bg-white
                               focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
                ) : (
                  <input ref={inputRef as any} value={value} placeholder={opts.placeholder}
                    onChange={(e) => setValue(e.target.value)}
                    className="w-full border border-grid rounded-xl px-3 py-2 text-sm bg-white
                               focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent" />
                )}
              </label>
            )}
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 mt-5">
          {kind !== 'alert' && (
            <button onClick={() => onClose(cancelValue)}
              className="px-3.5 py-2 rounded-xl text-sm text-inksec hover:bg-plane transition active:scale-[0.98]">
              {opts.cancelText || 'Cancel'}
            </button>
          )}
          <button
            onClick={() => onClose(kind === 'confirm' ? true : kind === 'prompt' ? value : undefined)}
            disabled={kind === 'prompt' && !value.trim()}
            className={`px-4 py-2 rounded-xl text-sm font-medium text-white transition active:scale-[0.98]
              disabled:opacity-40 ${danger ? 'bg-danger hover:brightness-110' : 'bg-accent hover:brightness-110'}`}>
            {opts.confirmText || (kind === 'alert' ? 'OK' : kind === 'prompt' ? 'Save' : 'Confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}

const TOAST_STYLE: Record<Toast['kind'], { cls: string; Icon: any }> = {
  info: { cls: 'text-accent', Icon: IconInfoCircle },
  success: { cls: 'text-positive', Icon: IconCheck },
  error: { cls: 'text-danger', Icon: IconAlertTriangle },
}

function ToastStack({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="fixed z-[110] bottom-4 right-4 flex flex-col gap-2 max-w-[calc(100vw-2rem)]">
      {toasts.map((t) => {
        const s = TOAST_STYLE[t.kind]
        return (
          <div key={t.id} role="status"
            className="flex items-start gap-2.5 bg-surface border border-grid rounded-xl shadow-float
                       px-3.5 py-2.5 w-80 max-w-full animate-[slidein_.2s_cubic-bezier(.16,1,.3,1)]">
            <s.Icon size={16} stroke={2} className={`mt-0.5 shrink-0 ${s.cls}`} />
            <span className="text-[13px] text-ink leading-snug flex-1">{t.msg}</span>
            <button onClick={() => onDismiss(t.id)} className="text-muted hover:text-ink shrink-0"><IconX size={14} stroke={2} /></button>
          </div>
        )
      })}
    </div>
  )
}
