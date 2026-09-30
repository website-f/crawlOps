import { createContext, useCallback, useContext, useState } from 'react'
import { PostHit } from '../lib/api'

/* Leaf context (imports no card components) so shared.tsx can open the detail
   panel without a circular import. The panel UI lives in PostDetailPanel.tsx. */
interface PostDetailApi { active: PostHit | null; open: (p: PostHit) => void; close: () => void }
const Ctx = createContext<PostDetailApi | null>(null)

export const usePostDetail = (): PostDetailApi => {
  const c = useContext(Ctx)
  if (!c) throw new Error('usePostDetail must be used within <PostDetailProvider>')
  return c
}

export function PostDetailProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState<PostHit | null>(null)
  const open = useCallback((p: PostHit) => setActive(p), [])
  const close = useCallback(() => setActive(null), [])
  return <Ctx.Provider value={{ active, open, close }}>{children}</Ctx.Provider>
}
