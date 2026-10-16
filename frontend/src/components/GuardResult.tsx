import { GraphCanvas } from './GraphCanvas'
import { JUDGE, card, label } from './ui'
import type { GuardResponse } from '../types'

/** Conflicts, alignments and reversals from Decision Guard (used by the Ask side panel and PR Guard). */
export function GuardResult({ result, showGraph = false }: { result: GuardResponse; showGraph?: boolean }) {
  const judge = JUDGE[result.judge ?? 'heuristic']
  return (
    <div style={{ display: 'grid', gap: 12 }} className="page-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <div style={label}>Conflicts ({result.conflicts.length})</div>
        <span title={judge.tip} style={{ background: judge.bg, color: judge.fg, fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4 }}>
          {judge.text}
        </span>
      </div>
      {result.conflicts.length === 0 && (
        <div style={{ ...card, padding: 14, color: 'var(--ok-ink)', fontSize: 14 }}>No conflicts found with past decisions.</div>
      )}
      {result.conflicts.map((c) => (
        <div key={c.decision_id} style={{ ...card, padding: 14, borderColor: 'var(--bad-line)', background: 'var(--panel-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <strong style={{ color: 'var(--bad-ink)' }}>⚠ {c.title}</strong>
            <span style={{ fontSize: 12, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{Math.round(c.confidence * 100)}% sure</span>
          </div>
          <p style={{ fontSize: 14, margin: '6px 0' }}>{c.why}</p>
          {c.evidence.map((ev) => (
            <blockquote key={ev.evidence_id} className="quote">
              “{ev.quote}”
              <div style={{ fontSize: 11, marginTop: 2, fontFamily: 'var(--font-ui)' }}>
                {ev.author} ·{' '}
                <a href={ev.url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
                  source
                </a>
              </div>
            </blockquote>
          ))}
        </div>
      ))}
      {result.alignments.map((a) => (
        <div key={a.decision_id} style={{ ...card, padding: 12, fontSize: 13, color: 'var(--ok-ink)' }}>
          ✓ Aligns with {a.title}
          <div style={{ color: 'var(--muted)' }}>{a.why}</div>
        </div>
      ))}
      {result.reversed_before.map((r) => (
        <div key={r.decision_id} style={{ ...card, padding: 12, fontSize: 13, color: 'var(--warn-ink)' }}>
          ↺ Reversed before: {r.title}
          <div style={{ color: 'var(--muted)' }}>{r.why}</div>
        </div>
      ))}
      {showGraph && result.graph.nodes.length > 0 && (
        <div style={{ ...card, height: 300, overflow: 'hidden' }}>
          <GraphCanvas elements={result.graph} mode="replace" />
        </div>
      )}
    </div>
  )
}
