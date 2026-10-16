import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Answer } from '../components/Answer'
import { GraphCanvas } from '../components/GraphCanvas'
import { GuardResult } from '../components/GuardResult'
import { SceneGraph } from '../components/HowItWorks'
import { Skeleton, SkeletonBlock } from '../components/ui'
import { ApiError, formatDate, getJson, postJson } from '../lib/api'
import { streamAsk } from '../lib/askStream'
import type { AskEvent } from '../lib/askStream'
import { normalizeDetail } from '../lib/normalize'
import { useSession } from '../lib/session'
import {
  MOCK_DECISION_DETAIL,
  MOCK_DECISIONS,
  MOCK_GUARD_RESPONSE,
  replayMockAskStream,
} from '../mock/server'
import type {
  Citation,
  DecisionDetail,
  DecisionTimelineItem,
  GraphElements,
  GuardResponse,
  Verification,
} from '../types'
import './ask.css'

// ---------------------------------------------------------------------------------------------
// Types and small helpers
// ---------------------------------------------------------------------------------------------

interface Step {
  id: string
  name: string
  input: Record<string, unknown>
  summary?: string
  done: boolean
}

type Phase = 'thinking' | 'verifying' | 'done' | 'error' | 'stopped'

interface AnswerData {
  markdown: string
  citations: Citation[]
  verification: Verification
}

interface Turn {
  id: number
  question: string
  phase: Phase
  steps: Step[]
  answer?: AnswerData
  error?: string
  recalled: number
  offline: boolean
  startedAt: number
  seconds?: number
  animate: boolean
  stepsOpen: boolean
}

const STEP_LABEL: Record<string, string> = {
  search_decisions: 'Searching decisions',
  get_decision: 'Reading a decision',
  trace_to_source: 'Tracing to source quotes',
  decision_lineage: 'Following the lineage',
  who_knows: 'Finding who knows the module',
  who_decided: 'Finding who decided',
  impact_of: 'Measuring the impact',
  find_path: 'Finding a path in the graph',
  central_people: 'Ranking people by influence',
  recent_changes: 'Listing recent changes',
  draft_adr: 'Drafting a decision record',
  check_proposal: 'Checking a proposal',
  recall: 'Recalling earlier sessions',
  pin: 'Pinning a decision',
}

const SUGGESTIONS: Array<[string, string]> = [
  ['why', 'Why was Python 3.6 dropped?'],
  ['who', 'Who knows flask/compat?'],
  ['impact', 'What was the impact of dropping Python 2?'],
  ['people', 'Who are the most central maintainers?'],
]

const MAX_QUESTION = 2000

function briefInput(input: Record<string, unknown>): string {
  const parts = Object.entries(input)
    .filter(([, v]) => v !== '' && v !== null && v !== undefined)
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
  const joined = parts.join(' · ')
  return joined.length > 70 ? `${joined.slice(0, 67)}…` : joined
}

function mergeGraph(prev: GraphElements, next?: Partial<GraphElements>): GraphElements {
  if (!next) return prev
  const nodes = new Map(prev.nodes.map((n) => [n.id, n]))
  const edges = new Map(prev.edges.map((e) => [e.id, e]))
  for (const n of next.nodes ?? []) nodes.set(n.id, n)
  for (const e of next.edges ?? []) edges.set(e.id, e)
  return { nodes: [...nodes.values()], edges: [...edges.values()] }
}

function demoDetail(id: string): DecisionDetail {
  if (id === MOCK_DECISION_DETAIL.decision.id) return MOCK_DECISION_DETAIL
  const d = MOCK_DECISIONS.find((x) => x.id === id)
  return {
    decision: {
      id,
      title: d?.title ?? id,
      summary: 'Recorded demo data: no further detail is bundled for this decision.',
      type: d?.type ?? '',
      status: d?.status ?? 'active',
      decided_at: d?.decided_at ?? '',
      valid_from: d?.decided_at ?? '',
      valid_to: null,
      confidence: d?.confidence ?? 1,
      extracted_at: '',
    },
    evidence: [],
    people: [],
    lineage: { nodes: [], edges: [] },
    impact: { modules: d?.modules ?? [], files: [], downstream: [], releases: [] },
    stale: false,
  }
}

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [active])
  return now
}

// ---------------------------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------------------------

export function Ask() {
  const { demo, health, backendUp } = useSession()

  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [graph, setGraph] = useState<GraphElements>({ nodes: [], edges: [] })
  const [path, setPath] = useState<GraphElements | null>(null)
  const [centerTab, setCenterTab] = useState<'graph' | 'timeline'>('graph')
  const [rightTab, setRightTab] = useState<'evidence' | 'guard'>('evidence')

  const [decisions, setDecisions] = useState<DecisionTimelineItem[] | null>(null)
  const [decisionsError, setDecisionsError] = useState<string | null>(null)

  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [activeCite, setActiveCite] = useState<number | null>(null)

  const [guardText, setGuardText] = useState('Re-add Python 3.6 compatibility helpers')
  const [guardPaths, setGuardPaths] = useState('src/flask/compat.py')
  const [guardBusy, setGuardBusy] = useState(false)
  const [guardError, setGuardError] = useState<string | null>(null)
  const [guardResult, setGuardResult] = useState<GuardResponse | null>(null)

  const counter = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const sessionRef = useRef<string | undefined>(undefined)
  const scrollRef = useRef<HTMLDivElement>(null)
  const citeRefs = useRef<Record<number, HTMLDivElement | null>>({})

  const last = turns[turns.length - 1]
  const busy = !!last && (last.phase === 'thinking' || last.phase === 'verifying')
  const now = useNow(busy)

  // The newest answer's citations drive the evidence list.
  const citations = useMemo(() => {
    for (let i = turns.length - 1; i >= 0; i--) {
      const a = turns[i].answer
      if (a) return a.citations
    }
    return [] as Citation[]
  }, [turns])

  // ----- data -----

  useEffect(() => {
    const ctrl = new AbortController()
    setDecisions(null)
    setDecisionsError(null)
    if (demo) {
      setDecisions(MOCK_DECISIONS)
      return
    }
    getJson<{ items: DecisionTimelineItem[] }>('/decisions?limit=50', ctrl.signal)
      .then((r) => setDecisions(r.items ?? []))
      .catch((e) => {
        if (!ctrl.signal.aborted) setDecisionsError(e instanceof Error ? e.message : 'Failed to load decisions')
      })
    return () => ctrl.abort()
  }, [demo])

  // Switching between demo and live must not mix their data.
  useEffect(() => {
    abortRef.current?.abort()
    setTurns([])
    setGraph({ nodes: [], edges: [] })
    setPath(null)
    setDetail(null)
    setGuardResult(null)
    sessionRef.current = undefined
  }, [demo])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns])

  useEffect(
    () => () => {
      abortRef.current?.abort()
    },
    [],
  )

  // ----- asking -----

  const patchTurn = useCallback((id: number, fn: (t: Turn) => Turn) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? fn(t) : t)))
  }, [])

  const applyEvent = useCallback(
    (id: number, ev: AskEvent): 'answer' | 'error' | null => {
      const d = ev.data
      switch (ev.event) {
        case 'status':
          patchTurn(id, (t) => (t.phase === 'thinking' || t.phase === 'verifying' ? { ...t, phase: d.phase === 'verifying' ? 'verifying' : 'thinking' } : t))
          return null
        case 'recall':
          patchTurn(id, (t) => ({ ...t, recalled: Array.isArray(d.findings) ? d.findings.length : 0 }))
          return null
        case 'tool_call':
          patchTurn(id, (t) => ({
            ...t,
            steps: [...t.steps, { id: String(d.id), name: String(d.name), input: (d.input as Record<string, unknown>) ?? {}, done: false }],
          }))
          return null
        case 'tool_result':
          patchTurn(id, (t) => ({
            ...t,
            steps: t.steps.map((s) => (s.id === String(d.id) ? { ...s, done: true, summary: String(d.summary ?? '') } : s)),
          }))
          if (d.graph_elements) setGraph((g) => mergeGraph(g, d.graph_elements))
          return null
        case 'answer':
          patchTurn(id, (t) => ({
            ...t,
            phase: 'done',
            seconds: Math.max(1, Math.round((Date.now() - t.startedAt) / 1000)),
            answer: {
              markdown: String(d.markdown ?? ''),
              citations: (d.citations as Citation[]) ?? [],
              verification: (d.verification as Verification) ?? { valid: 0, invalid: 0, repaired: false },
            },
          }))
          if (d.path) setPath(d.path as GraphElements)
          setActiveCite(null)
          setDetail(null)
          setRightTab('evidence')
          return 'answer'
        case 'error':
          patchTurn(id, (t) => ({ ...t, phase: 'error', error: String(d.message ?? 'Something went wrong.') }))
          return 'error'
        case 'done':
          if (d.session_id) sessionRef.current = String(d.session_id)
          if (d.offline) patchTurn(id, (t) => ({ ...t, offline: true }))
          return null
        default:
          return null
      }
    },
    [patchTurn],
  )

  const ask = useCallback(
    async (raw: string) => {
      const question = raw.trim()
      if (!question || busy || question.length > MAX_QUESTION) return
      const id = ++counter.current
      setTurns((prev) => [
        ...prev.map((t) => ({ ...t, animate: false })),
        { id, question, phase: 'thinking', steps: [], recalled: 0, offline: false, startedAt: Date.now(), animate: true, stepsOpen: true },
      ])
      setInput('')
      setPath(null)
      setCenterTab('graph')

      const ctrl = new AbortController()
      abortRef.current = ctrl
      let outcome: 'answer' | 'error' | null = null
      try {
        const stream = demo ? replayMockAskStream() : streamAsk(question, ctrl.signal, sessionRef.current)
        for await (const ev of stream) {
          if (ctrl.signal.aborted) break
          outcome = applyEvent(id, ev) ?? outcome
        }
        if (ctrl.signal.aborted) {
          patchTurn(id, (t) => (t.phase === 'thinking' || t.phase === 'verifying' ? { ...t, phase: 'stopped' } : t))
        } else if (!outcome) {
          patchTurn(id, (t) => ({ ...t, phase: 'error', error: 'The connection closed before an answer arrived.' }))
        }
      } catch (err) {
        if (ctrl.signal.aborted) {
          patchTurn(id, (t) => ({ ...t, phase: 'stopped' }))
        } else {
          const message = err instanceof ApiError || err instanceof Error ? err.message : 'Request failed'
          patchTurn(id, (t) => ({ ...t, phase: 'error', error: message }))
        }
      }
    },
    [applyEvent, busy, demo, patchTurn],
  )

  const stop = () => abortRef.current?.abort()

  const newChat = () => {
    abortRef.current?.abort()
    setTurns([])
    setGraph({ nodes: [], edges: [] })
    setPath(null)
    setDetail(null)
    sessionRef.current = undefined
  }

  // ----- decision detail and graph expansion -----

  const loadDetail = useCallback(
    async (decId: string) => {
      setRightTab('evidence')
      setActiveCite(null)
      setDetailError(null)
      setDetailLoading(true)
      try {
        setDetail(demo ? demoDetail(decId) : normalizeDetail(await getJson<Record<string, unknown>>(`/decisions/${encodeURIComponent(decId)}`)))
      } catch (e) {
        setDetail(null)
        setDetailError(e instanceof Error ? e.message : 'Could not load the decision')
      } finally {
        setDetailLoading(false)
      }
    },
    [demo],
  )

  const onNodeClick = useCallback(
    async (nodeId: string) => {
      if (nodeId.startsWith('Decision:')) void loadDetail(nodeId.slice('Decision:'.length))
      if (demo) return
      try {
        const sub = await getJson<GraphElements>(`/subgraph?center=${encodeURIComponent(nodeId)}&depth=1`)
        setGraph((g) => mergeGraph(g, sub))
      } catch {
        // Expanding neighbours is a bonus; failing quietly is fine.
      }
    },
    [demo, loadDetail],
  )

  const onCite = (n: number) => {
    setActiveCite(n)
    setDetail(null)
    setRightTab('evidence')
    window.setTimeout(() => citeRefs.current[n]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 60)
  }

  // ----- guard -----

  const runGuard = async () => {
    if (!guardText.trim() || guardBusy) return
    setGuardBusy(true)
    setGuardError(null)
    try {
      if (demo) {
        await new Promise((r) => setTimeout(r, 700))
        setGuardResult({ ...MOCK_GUARD_RESPONSE, judge: 'heuristic' })
      } else {
        const paths = guardPaths.split(',').map((p) => p.trim()).filter(Boolean)
        setGuardResult(await postJson<GuardResponse>('/guard', { description: guardText, paths }))
      }
    } catch (e) {
      setGuardResult(null)
      setGuardError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setGuardBusy(false)
    }
  }

  // ----- render -----

  const mode = demo ? 'demo' : !backendUp ? 'down' : health.llm_mode === 'no_key' ? 'no_key' : health.llm_mode === 'offline' ? 'offline' : 'live'

  return (
    <div className="ask">
      {/* ---------------- chat ---------------- */}
      <section aria-label="Chat">
        <div className="panel-head">
          <span className="panel-title">Ask the archive</span>
          {turns.length > 0 && (
            <button className="link-btn" onClick={newChat}>
              New chat
            </button>
          )}
        </div>

        <div className="chat-scroll" ref={scrollRef} aria-live="polite">
          {turns.length === 0 && (
            <div className="empty">
              <SceneGraph compact />
              <h2>Why is the code the way it is?</h2>
              <p>Ask about a decision, its history, or who knows a module. Every claim links to a verified quote.</p>
              <div className="sugg-grid">
                {SUGGESTIONS.map(([tag, q]) => (
                  <button key={q} className="sugg" onClick={() => void ask(q)}>
                    <b>{tag}</b>
                    <span>{q}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, idx) => (
            <TurnView
              key={t.id}
              turn={t}
              now={now}
              isLast={idx === turns.length - 1}
              activeCite={activeCite}
              onCite={onCite}
              onToggleSteps={() => patchTurn(t.id, (x) => ({ ...x, stepsOpen: !x.stepsOpen }))}
              onRetry={() => void ask(t.question)}
              mode={mode}
            />
          ))}
        </div>

        <div className="composer">
          {mode === 'no_key' && (
            <div className="notice bad" role="alert">
              No API key is set, so questions will fail. Add <code>GEMINI_API_KEY</code> to <code>.env</code>, or run the API with{' '}
              <code>DIG_OFFLINE=1</code> for canned demo answers.
            </div>
          )}
          {mode === 'offline' && (
            <div className="notice warn">Offline demo mode: answers are canned examples from the sample graph, not a live model.</div>
          )}
          {mode === 'down' && (
            <div className="notice bad" role="alert">
              Cannot reach the backend. Start it with <code>dig serve</code>, or switch to demo data in the top bar.
            </div>
          )}
          <div className="composer-row">
            <textarea
              value={input}
              rows={1}
              maxLength={MAX_QUESTION}
              placeholder="Ask why a choice was made…"
              aria-label="Your question"
              onChange={(e) => {
                setInput(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = `${Math.min(120, e.target.scrollHeight)}px`
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault()
                  void ask(input)
                }
              }}
            />
            {busy ? (
              <button className="btn ghost" onClick={stop}>
                Stop
              </button>
            ) : (
              <button className="btn" onClick={() => void ask(input)} disabled={!input.trim()}>
                Ask
              </button>
            )}
          </div>
          <div className="hint">Enter to send · Shift+Enter for a new line{input.length > 1600 ? ` · ${input.length}/${MAX_QUESTION}` : ''}</div>
        </div>
      </section>

      {/* ---------------- graph / timeline ---------------- */}
      <section aria-label="Graph">
        <div className="panel-head">
          <div className="tabs" role="tablist">
            <button className="tab" role="tab" aria-selected={centerTab === 'graph'} onClick={() => setCenterTab('graph')}>
              Graph
            </button>
            <button className="tab" role="tab" aria-selected={centerTab === 'timeline'} onClick={() => setCenterTab('timeline')}>
              Timeline{decisions ? ` (${decisions.length})` : ''}
            </button>
          </div>
          <span className="hint">
            {busy ? 'The agent is walking the graph…' : graph.nodes.length ? `${graph.nodes.length} nodes · click one to inspect` : ''}
          </span>
        </div>
        {busy ? <div className="busy-bar" /> : <div style={{ height: 3 }} />}

        {centerTab === 'graph' ? (
          <div style={{ flex: 1, minHeight: 0 }}>
            <GraphCanvas
              elements={graph}
              highlightedPath={path}
              onNodeClick={onNodeClick}
              busy={busy}
              empty={
                <div className="graph-empty">
                  {busy ? (
                    <>
                      <span className="typing-dots" style={{ marginBottom: 10 }}>
                        <i />
                        <i />
                        <i />
                      </span>
                      <b>Searching the graph</b>
                      Nodes appear here as the agent finds them.
                    </>
                  ) : (
                    <>
                      <b>The graph builds as you ask</b>
                      Each tool the agent uses adds the decisions, people and quotes it touched.
                    </>
                  )}
                </div>
              }
            />
          </div>
        ) : (
          <DecisionTimeline items={decisions} error={decisionsError} selected={detail?.decision.id} onSelect={(id) => void loadDetail(id)} />
        )}
      </section>

      {/* ---------------- evidence / guard ---------------- */}
      <section aria-label="Evidence">
        <div className="panel-head">
          <div className="tabs" role="tablist">
            <button className="tab" role="tab" aria-selected={rightTab === 'evidence'} onClick={() => setRightTab('evidence')}>
              Evidence
            </button>
            <button className="tab" role="tab" aria-selected={rightTab === 'guard'} onClick={() => setRightTab('guard')}>
              Decision Guard
            </button>
          </div>
        </div>

        {rightTab === 'evidence' ? (
          <div className="side-scroll">
            {detailLoading && (
              <div className="card">
                <Skeleton w="70%" h={18} style={{ marginBottom: 10 }} />
                <SkeletonBlock lines={3} />
              </div>
            )}
            {detailError && (
              <div className="notice bad" role="alert">
                {detailError}
              </div>
            )}
            {detail && !detailLoading && <DecisionCard detail={detail} onClose={() => setDetail(null)} />}

            {citations.length > 0 ? (
              <div>
                <div className="sec-label">Sources for the latest answer ({citations.length})</div>
                <div style={{ display: 'grid', gap: 8 }}>
                  {citations.map((c) => (
                    <div
                      key={c.evidence_id}
                      ref={(el) => {
                        citeRefs.current[c.n] = el
                      }}
                      className={`card${activeCite === c.n ? ' sel' : ''}`}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className="cite" style={{ cursor: 'default' }}>
                          {c.n}
                        </span>
                        <a href={c.url} target="_blank" rel="noreferrer noopener" className="link-btn">
                          View on GitHub ↗
                        </a>
                      </div>
                      <blockquote className="quote">“{c.quote}”</blockquote>
                      <div className="hint">
                        @{c.author} · {formatDate(c.ts)}
                        {c.decision_id && (
                          <>
                            {' · '}
                            <button className="link-btn" style={{ fontSize: 12, padding: 0 }} onClick={() => void loadDetail(c.decision_id!)}>
                              open decision
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              !detail &&
              !detailLoading && (
                <p className="hint" style={{ fontSize: 13.5 }}>
                  {busy ? 'Quotes appear here once the answer is verified.' : 'Citations from the answer and details of any decision you click will show up here.'}
                </p>
              )
            )}
          </div>
        ) : (
          <div className="side-scroll">
            <label className="form-label">
              Proposed change
              <textarea className="input" rows={3} value={guardText} maxLength={4000} onChange={(e) => setGuardText(e.target.value)} />
            </label>
            <label className="form-label">
              Files touched (comma separated)
              <input className="input" value={guardPaths} onChange={(e) => setGuardPaths(e.target.value)} />
            </label>
            <button className="btn" onClick={() => void runGuard()} disabled={guardBusy || !guardText.trim()}>
              {guardBusy ? 'Checking…' : 'Check against past decisions'}
            </button>
            {demo && <div className="notice warn">Demo data: this result is a recorded example.</div>}
            {guardBusy && <SkeletonBlock lines={4} />}
            {guardError && (
              <div className="notice bad" role="alert">
                {guardError}
              </div>
            )}
            {guardResult && !guardBusy && <GuardResult result={guardResult} />}
          </div>
        )}
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
// Parts
// ---------------------------------------------------------------------------------------------

function TurnView({
  turn,
  now,
  isLast,
  activeCite,
  onCite,
  onToggleSteps,
  onRetry,
  mode,
}: {
  turn: Turn
  now: number
  isLast: boolean
  activeCite: number | null
  onCite: (n: number) => void
  onToggleSteps: () => void
  onRetry: () => void
  mode: string
}) {
  const working = turn.phase === 'thinking' || turn.phase === 'verifying'
  const elapsed = Math.max(0, Math.round(((working ? now : turn.startedAt + (turn.seconds ?? 0) * 1000) - turn.startedAt) / 1000))
  const v = turn.answer?.verification

  return (
    <div>
      <div className="bubble-user">{turn.question}</div>
      <div className="turn" style={{ marginTop: 10 }}>
        {(turn.steps.length > 0 || working) && (
          <div className="work">
            <div className="work-head">
              <span>
                {working
                  ? turn.phase === 'verifying'
                    ? 'Checking every citation…'
                    : turn.steps.length
                      ? 'Working…'
                      : 'Thinking…'
                  : `Used ${turn.steps.length} tool${turn.steps.length === 1 ? '' : 's'}${turn.seconds ? ` · ${turn.seconds}s` : ''}`}
                {turn.recalled > 0 && ` · recalled ${turn.recalled} earlier finding${turn.recalled === 1 ? '' : 's'}`}
              </span>
              {working ? (
                <span style={{ fontFamily: 'var(--font-mono)' }}>{elapsed}s</span>
              ) : (
                turn.steps.length > 0 && (
                  <button className="link-btn" style={{ fontSize: 12 }} onClick={onToggleSteps}>
                    {turn.stepsOpen ? 'Hide' : 'Show'}
                  </button>
                )
              )}
            </div>
            {(turn.stepsOpen || working) &&
              turn.steps.map((s) => (
                <div className="step" key={s.id}>
                  <span className="mark">{s.done ? <span className="ok">✓</span> : <span className="spinner" />}</span>
                  <div>
                    <div>
                      <span className="name">{STEP_LABEL[s.name] ?? s.name}</span>{' '}
                      <span className="arg">{briefInput(s.input)}</span>
                    </div>
                    {s.summary && <div className="sum">{s.summary}</div>}
                  </div>
                </div>
              ))}
            {working && turn.phase === 'thinking' && (
              <div className="step" style={{ alignItems: 'center' }}>
                <span className="mark">
                  <span className="spinner" />
                </span>
                <span className="typing-dots">
                  <i />
                  <i />
                  <i />
                </span>
              </div>
            )}
          </div>
        )}

        {working && !turn.answer && (
          <div className="answer-card" aria-hidden>
            <SkeletonBlock lines={3} />
          </div>
        )}

        {turn.answer && (
          <div className="answer-card">
            <Answer markdown={turn.answer.markdown} animate={turn.animate && isLast} onCite={onCite} activeCite={activeCite} />
            {v && v.invalid === 0 && v.valid > 0 && (
              <span className="badge ok" title="Each citation was matched to a quote stored in the graph.">
                ✓ {v.valid} citation{v.valid === 1 ? '' : 's'} verified against the graph{v.repaired ? ' (after one correction)' : ''}
              </span>
            )}
            {v && v.valid === 0 && v.invalid === 0 && (
              <span className="badge warn" title="The answer cited no quotes, so nothing could be checked.">
                No sources cited: treat as unverified
              </span>
            )}
            {v && v.invalid > 0 && (
              <span className="badge bad">
                {v.invalid} citation{v.invalid === 1 ? '' : 's'} could not be verified
              </span>
            )}
            {(turn.offline || mode === 'offline') && (
              <span className="badge warn" style={{ marginLeft: 6 }}>
                canned demo answer
              </span>
            )}
          </div>
        )}

        {turn.phase === 'error' && (
          <div className="errcard" role="alert">
            <div>
              <strong>Could not answer.</strong> {turn.error}
            </div>
            <div>
              <button className="btn ghost" style={{ padding: '5px 12px' }} onClick={onRetry}>
                Try again
              </button>
            </div>
          </div>
        )}
        {turn.phase === 'stopped' && <div className="hint">Stopped.</div>}
      </div>
    </div>
  )
}

function DecisionTimeline({
  items,
  error,
  selected,
  onSelect,
}: {
  items: DecisionTimelineItem[] | null
  error: string | null
  selected?: string
  onSelect: (id: string) => void
}) {
  if (error)
    return (
      <div className="tl">
        <div className="notice bad" role="alert">
          {error}
        </div>
      </div>
    )
  if (!items)
    return (
      <div className="tl" style={{ display: 'grid', gap: 18 }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ display: 'grid', gap: 6 }}>
            <Skeleton w={90} h={10} />
            <Skeleton w="60%" h={14} />
          </div>
        ))}
      </div>
    )
  if (items.length === 0)
    return (
      <div className="tl">
        <p className="hint" style={{ fontSize: 14 }}>
          No decisions in the graph yet. Run <code>dig extract</code> first.
        </p>
      </div>
    )
  const sorted = [...items].sort((a, b) => (b.decided_at ?? '').localeCompare(a.decided_at ?? ''))
  const color = (s: string) => (s === 'active' ? 'var(--ok)' : s === 'reversed' ? 'var(--bad)' : 'var(--warn)')
  return (
    <div className="tl" style={{ flex: 1 }}>
      {sorted.map((d) => (
        <div
          key={d.id}
          className="tl-item"
          style={{ ['--dot' as string]: color(d.status), outline: selected === d.id ? '2px solid var(--accent)' : 'none', outlineOffset: 4, borderRadius: 4 }}
          onClick={() => onSelect(d.id)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onSelect(d.id)}
        >
          <div className="tl-date">
            {formatDate(d.decided_at)} · <span className={`pill ${d.status}`}>{d.status}</span>
          </div>
          <div className="tl-title">{d.title}</div>
          <div className="hint">{d.modules.join(', ')}</div>
        </div>
      ))}
    </div>
  )
}

function DecisionCard({ detail, onClose }: { detail: DecisionDetail; onClose: () => void }) {
  const d = detail.decision
  return (
    <div className="card sel page-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 8 }}>
        <div>
          <div className="sec-label" style={{ marginBottom: 2 }}>
            Decision
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 600, lineHeight: 1.2 }}>{d.title}</div>
        </div>
        <button className="link-btn" onClick={onClose} aria-label="Close decision">
          ✕
        </button>
      </div>
      <div style={{ margin: '8px 0' }}>
        <span className={`pill ${d.status}`}>{d.status}</span>{' '}
        <span className="hint">
          decided {formatDate(d.decided_at)}
          {d.valid_to ? ` · ended ${formatDate(d.valid_to)}` : ''}
        </span>
      </div>
      {detail.stale && <div className="notice warn" style={{ marginBottom: 8 }}>This decision may be out of date.</div>}
      <p style={{ fontSize: 13.5 }}>{d.summary}</p>
      <div className="hint" style={{ margin: '8px 0 4px' }}>
        Confidence {Math.round(d.confidence * 100)}%
      </div>
      <div style={{ height: 5, background: 'var(--line)', borderRadius: 3 }}>
        <div style={{ width: `${Math.round(d.confidence * 100)}%`, height: '100%', background: 'var(--accent)', borderRadius: 3 }} />
      </div>

      {detail.evidence.map((c) => (
        <blockquote className="quote" key={c.evidence_id}>
          “{c.quote}”
          <div className="hint" style={{ fontFamily: 'var(--font-ui)' }}>
            @{c.author} ·{' '}
            <a href={c.url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
              source
            </a>
          </div>
        </blockquote>
      ))}

      {detail.people.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div className="sec-label">People</div>
          {detail.people.map((p) => (
            <span className="chip" key={p.login}>
              @{p.login} · {p.role}
            </span>
          ))}
        </div>
      )}
      {(detail.impact.modules.length > 0 || detail.impact.files.length > 0 || detail.impact.releases.length > 0) && (
        <div style={{ marginTop: 8 }}>
          <div className="sec-label">Impact</div>
          {detail.impact.modules.map((m) => (
            <span className="chip mono" key={m}>
              {m}
            </span>
          ))}
          {detail.impact.files.map((f) => (
            <span className="chip mono" key={f}>
              {f}
            </span>
          ))}
          {detail.impact.releases.map((r) => (
            <span className="chip" key={r}>
              release {r}
            </span>
          ))}
        </div>
      )}
      {d.decided_at && (
        <a className="link-btn" style={{ display: 'inline-block', marginTop: 8 }} href={`#/time?date=${d.decided_at.slice(0, 10)}`}>
          See the project on that day →
        </a>
      )}
    </div>
  )
}
