import type { CSSProperties, ReactNode } from 'react'
import { useSession } from '../lib/session'

export const card: CSSProperties = {
  backgroundColor: 'var(--panel)',
  border: '1px solid var(--line)',
  borderRadius: 10,
}

export const label: CSSProperties = {
  fontSize: 11,
  letterSpacing: '0.8px',
  textTransform: 'uppercase',
  color: 'var(--muted)',
}

export const primaryBtn: CSSProperties = {
  backgroundColor: 'var(--accent)',
  color: 'var(--accent-ink)',
  border: 'none',
  padding: '8px 16px',
  borderRadius: 6,
  fontWeight: 600,
  cursor: 'pointer',
  fontSize: 13,
}

export function PageHeader({ title, subtitle }: { title: string; subtitle: ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontWeight: 400, fontSize: 28, margin: 0 }}>{title}</h1>
      <p style={{ color: 'var(--muted)', maxWidth: 760, marginTop: 4, fontSize: 14 }}>{subtitle}</p>
    </div>
  )
}

/** Honest data-source banner: demo data is always labelled, failures are never hidden. */
export function SourceNotice({ error }: { error?: string | null }) {
  const { demo, setDemo } = useSession()
  if (demo) {
    return (
      <div role="status" style={{ ...notice, borderColor: 'var(--warn-line)', color: 'var(--warn-ink)' }}>
        Showing recorded demo data, not your graph. Switch to the live backend in the top bar.
      </div>
    )
  }
  if (error) {
    return (
      <div role="alert" style={{ ...notice, borderColor: 'var(--bad-line)', color: 'var(--bad-ink)' }}>
        {error}{' '}
        <button
          onClick={() => setDemo(true)}
          style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', textDecoration: 'underline', fontSize: 13 }}
        >
          Use demo data instead
        </button>
      </div>
    )
  }
  return null
}

const notice: CSSProperties = {
  border: '1px solid',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 13,
  marginBottom: 12,
  backgroundColor: 'var(--panel)',
}

export function Page({ children }: { children: ReactNode }) {
  return <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '24px 28px' }}>{children}</div>
}

export function StatusDot({ status }: { status: string }) {
  const color = status === 'active' ? 'var(--ok)' : status === 'reversed' ? 'var(--bad)' : 'var(--warn)'
  return <span aria-hidden style={{ width: 8, height: 8, borderRadius: 2, background: color, display: 'inline-block' }} />
}

export function Skeleton({ w = '100%', h = 12, style }: { w?: number | string; h?: number; style?: CSSProperties }) {
  return <span className="skeleton" style={{ width: w, height: h, ...style }} aria-hidden />
}

export function SkeletonBlock({ lines = 3 }: { lines?: number }) {
  return (
    <div role="status" aria-label="Loading" style={{ display: 'grid', gap: 8 }}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} w={i === lines - 1 ? '62%' : '100%'} />
      ))}
    </div>
  )
}

export const JUDGE: Record<string, { text: string; tip: string; bg: string; fg: string }> = {
  llm: { text: 'Judged by the LLM', tip: 'A model compared the proposal with each related decision.', bg: 'var(--ok-bg)', fg: 'var(--ok-ink)' },
  mixed: { text: 'Mixed judge', tip: 'Some decisions were judged by the model, others by the built-in rules.', bg: 'var(--warn-bg)', fg: 'var(--warn-ink)' },
  heuristic: {
    text: 'Keyword rules, not an LLM',
    tip: 'No usable model response. The built-in rules are tuned to the Flask demo and may miss conflicts elsewhere.',
    bg: 'var(--warn-bg)',
    fg: 'var(--warn-ink)',
  },
}
