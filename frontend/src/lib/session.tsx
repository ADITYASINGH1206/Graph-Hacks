import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { MOCK_HEALTH } from '../mock/server'
import type { HealthData } from '../types'
import { getJson } from './api'

interface Session {
  /** true = every page uses recorded demo data instead of the backend. */
  demo: boolean
  setDemo: (v: boolean) => void
  health: HealthData
  /** true once /health has answered (so pages can say "live" honestly). */
  backendUp: boolean
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [demo, setDemo] = useState<boolean>(import.meta.env.VITE_MOCK === '1')
  const [health, setHealth] = useState<HealthData>(MOCK_HEALTH)
  const [backendUp, setBackendUp] = useState(false)

  useEffect(() => {
    if (demo) {
      setHealth(MOCK_HEALTH)
      setBackendUp(false)
      return
    }
    const ctrl = new AbortController()
    getJson<HealthData>('/health', ctrl.signal)
      .then((h) => {
        setHealth(h)
        setBackendUp(true)
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setBackendUp(false)
      })
    return () => ctrl.abort()
  }, [demo])

  const value = useMemo(() => ({ demo, setDemo, health, backendUp }), [demo, health, backendUp])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside <SessionProvider>')
  return ctx
}
