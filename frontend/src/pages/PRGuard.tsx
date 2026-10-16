import { useState } from 'react'
import type { FormEvent } from 'react'
import { GraphCanvas } from '../components/GraphCanvas'
import { Page, PageHeader, SourceNotice, card, label, primaryBtn } from '../components/ui'
import { postJson } from '../lib/api'
import { useSession } from '../lib/session'
import { DEMO_PR } from '../mock/insights'
import type { PRGuardResponse } from '../types'

const PR_RE = /^https:\/\/github\.com\/[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9._-]{1,100}\/pull\/\d{1,7}(\/(files|commits|checks))?\/?([?#].*)?$/

const JUDGE_TEXT: Record<string, { text: string; tip: string; bg: string; fg: string }> = {
  llm: { text: 'Judged by the LLM', tip: 'A model compared the PR with each related decision.', bg: '#10301f', fg: '#86efac' },
  mixed: { text: 'Mixed judge', tip: 'Some decisions were judged by the model, others by the built-in rules.', bg: '#3a2a12', fg: '#f3d28a' },
  heuristic: {
    text: 'Keyword rules, not an LLM',
    tip: 'No usable model response. The built-in rules are tuned to the Flask demo and may miss conflicts elsewhere.',
    bg: '#3a2a12',
    fg: '#f3d28a',
  },
}

export function PRGuard() {
  const { demo } = useSession()
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PRGuardResponse | null>(null)
  const [fromDemo, setFromDemo] = useState(false)

  const valid = PR_RE.test(url.trim())

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!valid || busy) return
    setBusy(true)
    setError(null)
    try {
      if (demo) {
        setResult(DEMO_PR)
        setFromDemo(true)
      } else {
        setResult(await postJson<PRGuardResponse>('/guard/pr', { url: url.trim() }))
        setFromDemo(false)
      }
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  const judge = result ? JUDGE_TEXT[result.guard.judge ?? 'heuristic'] : null

  return (
    <Page>
      <PageHeader
        title="PR Guard"
        subtitle="Paste a GitHub pull request link. We read its title, description and changed files, and check them against what the project already decided."
      />
      <SourceNotice error={null} />

      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/pallets/flask/pull/1234"
          aria-label="Pull request URL"
          spellCheck={false}
          style={{
            flex: '1 1 420px',
            backgroundColor: 'var(--panel)',
            color: 'var(--text)',
            border: `1px solid ${url && !valid ? '#6b2323' : 'var(--line-2)'}`,
            borderRadius: 6,
            padding: '9px 12px',
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
          }}
        />
        <button type="submit" disabled={!valid || busy} style={{ ...primaryBtn, opacity: !valid || busy ? 0.5 : 1 }}>
          {busy ? 'Checking…' : 'Check this PR'}
        </button>
      </form>
      <p style={{ fontSize: 12, color: url && !valid ? '#fca5a5' : 'var(--muted)', marginBottom: 16 }}>
        {url && !valid
          ? 'Use a link like https://github.com/<owner>/<repo>/pull/<number>.'
          : demo
            ? 'Demo mode shows a recorded example whatever link you enter.'
            : 'Only github.com pull request links are accepted. Private repositories are not supported.'}
      </p>

      {error && (
        <div role="alert" style={{ ...card, borderColor: '#6b2323', color: '#fecaca', padding: 12, fontSize: 14 }}>
          {error}
        </div>
      )}

      {result && judge && (
        <div className="fade-up" style={{ display: 'grid', gap: 16 }}>
          {fromDemo && (
            <div role="status" style={{ ...card, padding: 10, fontSize: 13, color: '#f3d28a' }}>
              Recorded example. Turn off demo data to check a real pull request.
            </div>
          )}
          <div style={{ ...card, padding: 16 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <a href={result.pr.url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)', fontWeight: 600 }}>
                {result.pr.owner}/{result.pr.repo}#{result.pr.number}
              </a>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                {result.pr.state} · by {result.pr.author} · +{result.pr.additions} −{result.pr.deletions} ·{' '}
                {result.pr.files_checked} files checked{result.pr.truncated_files ? ` of ${result.pr.changed_files}` : ''}
              </span>
              <span
                title={judge.tip}
                style={{ marginLeft: 'auto', background: judge.bg, color: judge.fg, fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4 }}
              >
                {judge.text}
              </span>
            </div>
            <p style={{ marginTop: 8, fontSize: 15 }}>{result.pr.title}</p>
            {!result.repo_matches_graph && (
              <p role="alert" style={{ marginTop: 10, fontSize: 13, color: '#f3d28a' }}>
                This PR is not from {result.graph_repo}, the project in your graph. Results compare it with {result.graph_repo}'s
                decisions and may not apply.
              </p>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(260px, 2fr)', gap: 16 }}>
            <div style={{ display: 'grid', gap: 12, alignContent: 'start' }}>
              <div style={label}>Conflicts ({result.guard.conflicts.length})</div>
              {result.guard.conflicts.length === 0 && (
                <div style={{ ...card, padding: 14, color: '#86efac', fontSize: 14 }}>
                  No conflicts found with past decisions.
                </div>
              )}
              {result.guard.conflicts.map((c) => (
                <div key={c.decision_id} style={{ ...card, padding: 14, borderColor: '#6b2323' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <strong style={{ color: '#fca5a5' }}>⚠ {c.title}</strong>
                    <span style={{ fontSize: 12, color: 'var(--muted)' }}>{Math.round(c.confidence * 100)}% sure</span>
                  </div>
                  <p style={{ fontSize: 14, margin: '6px 0' }}>{c.why}</p>
                  {c.evidence.map((ev) => (
                    <blockquote
                      key={ev.evidence_id}
                      style={{ borderLeft: '3px solid var(--accent)', paddingLeft: 10, margin: '8px 0', fontSize: 13, color: 'var(--muted)' }}
                    >
                      “{ev.quote}”
                      <div style={{ fontSize: 11, marginTop: 2 }}>
                        {ev.author} ·{' '}
                        <a href={ev.url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
                          source
                        </a>
                      </div>
                    </blockquote>
                  ))}
                </div>
              ))}
              {result.guard.alignments.map((a) => (
                <div key={a.decision_id} style={{ ...card, padding: 12, fontSize: 13, color: '#86efac' }}>
                  ✓ Aligns with {a.title}
                  <div style={{ color: 'var(--muted)' }}>{a.why}</div>
                </div>
              ))}
              {result.guard.reversed_before.map((r) => (
                <div key={r.decision_id} style={{ ...card, padding: 12, fontSize: 13, color: '#f3d28a' }}>
                  ↺ Reversed before: {r.title}
                  <div style={{ color: 'var(--muted)' }}>{r.why}</div>
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gap: 12, alignContent: 'start' }}>
              <div style={{ ...card, padding: 14 }}>
                <div style={{ ...label, marginBottom: 6 }}>Suggested reviewers</div>
                {result.suggested_reviewers.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--muted)' }}>None. No conflicting decision has a known author.</p>
                ) : (
                  result.suggested_reviewers.map((r) => (
                    <div key={r} style={{ fontSize: 14 }}>
                      @{r}
                    </div>
                  ))
                )}
              </div>
              {result.guard.graph.nodes.length > 0 && (
                <div style={{ ...card, height: 300, overflow: 'hidden' }}>
                  <GraphCanvas elements={result.guard.graph} mode="replace" />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Page>
  )
}
