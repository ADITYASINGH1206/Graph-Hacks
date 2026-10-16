import { useEffect, useState } from 'react'
import { Page, PageHeader, SourceNotice, card, label } from '../components/ui'
import { formatDate, getJson } from '../lib/api'
import { useSession } from '../lib/session'
import { DEMO_RISK } from '../mock/insights'
import type { ModuleRisk, RiskLevel, RiskReport } from '../types'

const COLORS: Record<RiskLevel, { bg: string; fg: string }> = {
  critical: { bg: '#7f1d1d', fg: '#fecaca' },
  high: { bg: '#8a3a12', fg: '#fed7aa' },
  medium: { bg: '#6b5614', fg: '#fde68a' },
  low: { bg: '#14532d', fg: '#bbf7d0' },
}

const SOURCE_TEXT = {
  graph_latest: 'the newest activity in the graph, so old snapshots are not all marked inactive',
  requested: 'the date you requested',
  now: "today's date",
} as const

export function RiskMap() {
  const { demo } = useSession()
  const [report, setReport] = useState<RiskReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [windowDays, setWindowDays] = useState(365)
  const [picked, setPicked] = useState<string | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    setError(null)
    const run = async () => {
      try {
        const r = demo ? { ...DEMO_RISK, window_days: windowDays } : await getJson<RiskReport>(`/risk/modules?window_days=${windowDays}`, ctrl.signal)
        if (!ctrl.signal.aborted) setReport(r)
      } catch (e) {
        if (!ctrl.signal.aborted) {
          setReport(null)
          setError(e instanceof Error ? e.message : 'Failed to load risk report')
        }
      }
    }
    void run()
    return () => ctrl.abort()
  }, [demo, windowDays])

  const selected: ModuleRisk | undefined = report?.modules.find((m) => m.module === picked) ?? report?.modules[0]

  return (
    <Page>
      <PageHeader
        title="Knowledge-risk map"
        subtitle="Which parts of the code does only a few people understand? Modules are ranked by how few experts they have, how concentrated the knowledge is, and whether those experts are still active."
      />
      <SourceNotice error={error} />

      {report && (
        <>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16, fontSize: 13, color: 'var(--muted)' }}>
            <label>
              Count someone as active if seen within{' '}
              <select
                value={windowDays}
                onChange={(e) => setWindowDays(Number(e.target.value))}
                style={{ background: 'var(--panel)', color: 'var(--text)', border: '1px solid var(--line-2)', borderRadius: 4, padding: '2px 6px' }}
              >
                <option value={180}>6 months</option>
                <option value={365}>1 year</option>
                <option value={730}>2 years</option>
              </select>
            </label>
            <span>
              Measured as of {formatDate(report.as_of)}, using {SOURCE_TEXT[report.as_of_source]}.
            </span>
          </div>

          {report.modules.length === 0 ? (
            <div style={{ ...card, padding: 20, color: 'var(--muted)' }}>
              No module expertise in this graph yet. Run <code>dig score</code> first.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(280px, 2fr)', gap: 16 }}>
              <div
                role="list"
                style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10, alignContent: 'start' }}
              >
                {report.modules.map((m) => {
                  const c = COLORS[m.risk]
                  const on = m.module === selected?.module
                  return (
                    <button
                      key={m.module}
                      role="listitem"
                      onClick={() => setPicked(m.module)}
                      aria-pressed={on}
                      style={{
                        textAlign: 'left',
                        background: c.bg,
                        color: c.fg,
                        border: `2px solid ${on ? 'var(--text)' : 'transparent'}`,
                        borderRadius: 10,
                        padding: 14,
                        cursor: 'pointer',
                        minHeight: 96,
                      }}
                    >
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, wordBreak: 'break-all' }}>{m.module}</div>
                      <div style={{ fontSize: 22, fontFamily: 'var(--font-display)', marginTop: 4 }}>{m.risk}</div>
                      <div style={{ fontSize: 11, opacity: 0.85 }}>
                        {m.active_experts} active · bus factor {m.bus_factor}
                      </div>
                    </button>
                  )
                })}
              </div>

              {selected && (
                <div style={{ ...card, padding: 16, alignSelf: 'start' }}>
                  <div style={label}>Selected module</div>
                  <h2 style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 500, margin: '2px 0 8px' }}>{selected.module}</h2>
                  {selected.reasons.map((r) => (
                    <p key={r} style={{ fontSize: 14, marginBottom: 6 }}>
                      {r}
                    </p>
                  ))}
                  <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
                    Bus factor {selected.bus_factor} = people needed to cover 60% of the module's expertise. {selected.decisions_active} of{' '}
                    {selected.decisions_total} decisions here are still active.
                  </p>
                  <div style={{ ...label, marginBottom: 6 }}>Experts</div>
                  {selected.experts.length === 0 && <p style={{ fontSize: 13, color: 'var(--muted)' }}>Nobody has recorded expertise.</p>}
                  {selected.experts.map((x) => (
                    <div key={x.login} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                        <span>
                          @{x.login} {!x.active && <span style={{ color: '#fca5a5' }}>(inactive)</span>}
                        </span>
                        <span style={{ color: 'var(--muted)' }}>{Math.round(x.share * 100)}% · last seen {formatDate(x.last_active)}</span>
                      </div>
                      <div style={{ height: 6, background: 'var(--line)', borderRadius: 3 }}>
                        <div
                          style={{
                            width: `${Math.round(x.share * 100)}%`,
                            height: '100%',
                            borderRadius: 3,
                            background: x.active ? 'var(--accent)' : '#6b5d4a',
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </Page>
  )
}
