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
      <div role="status" style={{ ...notice, borderColor: '#5c4318', color: '#f3d28a' }}>
        Showing recorded demo data, not your graph. Switch to the live backend in the top bar.
      </div>
    )
  }
  if (error) {
    return (
      <div role="alert" style={{ ...notice, borderColor: '#6b2323', color: '#fecaca' }}>
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
  const color = status === 'active' ? '#10b981' : status === 'reversed' ? '#ef4444' : '#f59e0b'
  return <span aria-hidden style={{ width: 8, height: 8, borderRadius: 2, background: color, display: 'inline-block' }} />
}
