import { IconX } from '@tabler/icons-react'
import { useEffect } from 'react'

/* Right-side slide-in panel. Backdrop + Escape close, scroll-locked body,
   reduced-motion friendly (animation is disabled globally under the media query). */
export function Offcanvas({ open, onClose, title, subtitle, width = '40rem', children }: {
  open: boolean; onClose: () => void; title?: React.ReactNode; subtitle?: React.ReactNode
  width?: string; children: React.ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-[90]">
      <div className="absolute inset-0 bg-ink/45 backdrop-blur-[2px] animate-[fade_.15s_ease-out]" onClick={onClose} />
      <div role="dialog" aria-modal="true"
        className="absolute inset-y-0 right-0 bg-plane border-l border-grid shadow-float flex flex-col
                   w-full max-w-[95vw] animate-[canvasin_.24s_cubic-bezier(.16,1,.3,1)]"
        style={{ width }}>
        <div className="flex items-start gap-3 px-5 h-16 shrink-0 border-b border-grid bg-surface/80 backdrop-blur">
          <div className="min-w-0 flex-1 self-center">
            {title && <div className="font-semibold text-[15px] text-ink leading-tight truncate">{title}</div>}
            {subtitle && <div className="text-[12.5px] text-inksec truncate">{subtitle}</div>}
          </div>
          <button onClick={onClose} aria-label="Close"
            className="self-center p-1.5 rounded-lg text-inksec hover:bg-plane hover:text-ink transition active:scale-95">
            <IconX size={18} stroke={2} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}
