import type { ReactNode } from 'react'
import { hrefFor } from '../lib/router'
import type { Route } from '../lib/router'
import { useSession } from '../lib/session'

const NAV: Array<{ route: Route; label: string }> = [
  { route: 'app', label: 'Ask' },
  { route: 'time', label: 'Time Machine' },
  { route: 'guard', label: 'PR Guard' },
  { route: 'risk', label: 'Risk map' },
]

interface ShellProps {
  route: Route
  onOpenPalette: () => void
  onStartTour: () => void
  children: ReactNode
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

export function Shell({ route, onOpenPalette, onStartTour, children }: ShellProps) {
  const { demo, setDemo, health, backendUp } = useSession()
  const llm = health.llm_mode
  const status = demo
    ? { text: 'DEMO DATA', bg: '#3a2a12', fg: '#f3d28a', tip: 'Recorded sample data. No backend calls.' }
    : !backendUp
      ? { text: 'BACKEND OFFLINE', bg: '#4a1c1c', fg: '#fecaca', tip: 'Cannot reach the API. Start it with `dig serve`, or switch to Demo data.' }
      : llm === 'offline'
        ? { text: 'OFFLINE DEMO MODE', bg: '#3a2a12', fg: '#f3d28a', tip: 'DIG_OFFLINE=1: answers are canned demo replies, not a live model.' }
        : llm === 'no_key'
          ? { text: 'NO API KEY', bg: '#4a1c1c', fg: '#fecaca', tip: 'No GEMINI_API_KEY set: questions will return an error.' }
          : { text: 'LIVE', bg: '#10301f', fg: '#86efac', tip: 'Connected to the backend with a live model.' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100%' }}>
      <header
        style={{
          minHeight: 52,
          backgroundColor: 'var(--panel)',
          borderBottom: '1px solid var(--line)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          padding: '0 16px',
          fontSize: 13,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <a
            href={hrefFor('home')}
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 17,
              color: 'var(--text)',
              textDecoration: 'none',
              letterSpacing: '0.2px',
            }}
          >
            Decision <span style={{ color: 'var(--accent)' }}>Archaeologist</span>
          </a>
          <nav aria-label="Pages" style={{ display: 'flex', gap: 4 }}>
            {NAV.map((n) => {
              const on = n.route === route
              return (
                <a
                  key={n.route}
                  href={hrefFor(n.route)}
                  aria-current={on ? 'page' : undefined}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 6,
                    textDecoration: 'none',
                    color: on ? 'var(--accent-ink)' : 'var(--muted)',
                    backgroundColor: on ? 'var(--accent)' : 'transparent',
                    fontWeight: on ? 600 : 500,
                  }}
                >
                  {n.label}
                </a>
              )
            })}
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--muted)',
              backgroundColor: 'var(--line)',
              padding: '2px 8px',
              borderRadius: 4,
            }}
          >
            {health.graph}
          </span>
          <span
            title={status.tip}
            style={{
              backgroundColor: status.bg,
              color: status.fg,
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: '0.4px',
            }}
          >
            {status.text}
          </span>
          <span style={{ color: 'var(--muted)' }}>
            <strong style={{ color: 'var(--ok)' }}>{health.counts.Decision}</strong> decisions
          </span>
          <button onClick={() => setDemo(!demo)} style={ghostBtn} title="Switch between the real backend and recorded sample data">
            {demo ? 'Use live backend' : 'Use demo data'}
          </button>
          <button onClick={onStartTour} style={ghostBtn}>
            Tour
          </button>
          <button onClick={onOpenPalette} style={ghostBtn} aria-label="Open command palette">
            {isMac ? '⌘K' : 'Ctrl K'}
          </button>
        </div>
      </header>
      <main style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>{children}</main>
    </div>
  )
}

const ghostBtn: React.CSSProperties = {
  backgroundColor: 'var(--line)',
  color: 'var(--text)',
  border: '1px solid var(--line-2)',
  padding: '4px 10px',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: 12,
}
