import { useState } from 'react'
import { hrefFor, navigate } from '../lib/router'
import type { Route } from '../lib/router'
import { useSession } from '../lib/session'
import { primaryBtn } from './ui'

const STEPS: Array<{ route: Route; title: string; body: string }> = [
  {
    route: 'app',
    title: '1. Ask the archive',
    body: 'Type a question like “Why was Python 3.6 dropped?” or use a shortcut button. The graph on the left lights up the path the agent walked, and each citation links to the exact quote.',
  },
  {
    route: 'time',
    title: '2. Travel in time',
    body: 'Drag the slider or press play. Diamonds mark when decisions were made or replaced. Click one to jump there.',
  },
  {
    route: 'guard',
    title: '3. Guard a pull request',
    body: 'Paste a GitHub PR link. Conflicts with past decisions are shown with quotes, plus the people who made them. The badge says whether a model or simple keyword rules did the judging.',
  },
  {
    route: 'risk',
    title: '4. Find fragile knowledge',
    body: 'Red and orange modules depend on one or two people. Click a module to see who those people are and when they were last active.',
  },
]

const STORAGE_KEY = 'dig_tour_seen'

export function tourSeen(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function markSeen() {
  try {
    window.localStorage.setItem(STORAGE_KEY, '1')
  } catch {
    // storage unavailable: the tour simply may show again
  }
}

export function Tour({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0)
  const { demo, setDemo, backendUp } = useSession()
  const step = STEPS[i]
  const last = i === STEPS.length - 1

  const go = (next: number) => {
    setI(next)
    navigate(STEPS[next].route)
  }
  const close = () => {
    markSeen()
    onClose()
  }

  return (
    <div
      role="dialog"
      aria-label="Guided tour"
      style={{
        position: 'fixed',
        right: 20,
        bottom: 20,
        width: 'min(380px, calc(100vw - 40px))',
        zIndex: 50,
        background: 'var(--panel-2)',
        border: '1px solid var(--line-2)',
        borderRadius: 12,
        padding: 18,
        boxShadow: '0 16px 40px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', letterSpacing: '0.8px', textTransform: 'uppercase' }}>
        <span>
          Guided tour · {i + 1} of {STEPS.length}
        </span>
        <button onClick={close} aria-label="Close tour" style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 16 }}>
          ✕
        </button>
      </div>
      <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 400, fontSize: 20, margin: '6px 0' }}>{step.title}</h3>
      <p style={{ fontSize: 14, color: 'var(--muted)' }}>{step.body}</p>
      {!demo && !backendUp && (
        <p style={{ fontSize: 12, color: 'var(--warn-ink)', marginTop: 8 }}>
          The backend is not reachable.{' '}
          <button onClick={() => setDemo(true)} style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', textDecoration: 'underline', fontSize: 12 }}>
            Try the tour with demo data
          </button>
        </p>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 14 }}>
        <button
          onClick={() => go(i - 1)}
          disabled={i === 0}
          style={{ background: 'none', border: '1px solid var(--line-2)', color: 'var(--text)', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', opacity: i === 0 ? 0.4 : 1 }}
        >
          Back
        </button>
        {last ? (
          <a href={hrefFor('app')} onClick={close} style={{ ...primaryBtn, textDecoration: 'none' }}>
            Done
          </a>
        ) : (
          <button onClick={() => go(i + 1)} style={primaryBtn}>
            Next
          </button>
        )}
      </div>
    </div>
  )
}
