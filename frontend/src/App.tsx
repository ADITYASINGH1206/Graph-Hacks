import { useEffect, useRef, useState } from 'react'
import { GraphCanvas } from './components/GraphCanvas'
import {
  MOCK_DECISION_DETAIL,
  MOCK_DECISIONS,
  MOCK_GUARD_RESPONSE,
  MOCK_HEALTH,
  replayMockAskStream,
} from './mock/server'
import type {
  Citation,
  DecisionDetail,
  DecisionTimelineItem,
  GraphElements,
  GuardResponse,
  HealthData,
  Verification,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text?: string
  toolCalls?: Array<{ id: string; name: string; input: any; summary?: string }>
  citations?: Citation[]
  verification?: Verification
}

export function App() {
  const [useMock, setUseMock] = useState<boolean>(import.meta.env.VITE_MOCK === '1')
  const [health, setHealth] = useState<HealthData>(MOCK_HEALTH)
  const [centerTab, setCenterTab] = useState<'graph' | 'timeline'>('graph')
  const [rightTab, setRightTab] = useState<'evidence' | 'guard'>('evidence')

  // Graph state
  const [graphElements, setGraphElements] = useState<GraphElements>({ nodes: [], edges: [] })
  const [highlightedPath, setHighlightedPath] = useState<GraphElements | null>(null)

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  // Timeline & Detail state
  const [decisions, setDecisions] = useState<DecisionTimelineItem[]>([])
  const [selectedDecision, setSelectedDecision] = useState<DecisionDetail | null>(null)
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null)

  // Guard state
  const [guardDescription, setGuardDescription] = useState('Re-add Python 3.6 compatibility helpers')
  const [guardPaths, setGuardPaths] = useState('src/flask/compat.py')
  const [guardLoading, setGuardLoading] = useState(false)
  const [guardResult, setGuardResult] = useState<GuardResponse | null>(null)

  const chatScrollRef = useRef<HTMLDivElement>(null)
  const evidenceRef = useRef<HTMLDivElement>(null)
  const msgCounterRef = useRef(0)

  useEffect(() => {
    let isCancelled = false
    const loadData = async () => {
      if (useMock) {
        if (!isCancelled) {
          setHealth(MOCK_HEALTH)
          setDecisions(MOCK_DECISIONS)
        }
        return
      }
      try {
        const [healthRes, decsRes] = await Promise.all([
          fetch(`${API_BASE}/health`),
          fetch(`${API_BASE}/decisions?limit=50`),
        ])
        if (!isCancelled && healthRes.ok) {
          const hData = await healthRes.json()
          setHealth(hData)
        }
        if (!isCancelled && decsRes.ok) {
          const dData = await decsRes.json()
          setDecisions(dData.items || [])
        }
      } catch {
        if (!isCancelled) {
          setDecisions(MOCK_DECISIONS)
        }
      }
    }
    loadData()
    return () => {
      isCancelled = true
    }
  }, [useMock])

  // Scroll chat
  useEffect(() => {
    chatScrollRef.current?.scrollTo({
      top: chatScrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  // Ask question SSE handler
  const handleAsk = async (question: string) => {
    if (!question.trim() || isStreaming) return

    msgCounterRef.current += 1
    const userMsgId = `usr_${msgCounterRef.current}`
    const userMsg: ChatMessage = {
      id: userMsgId,
      role: 'user',
      text: question,
    }

    msgCounterRef.current += 1
    const assistantMsgId = `ast_${msgCounterRef.current}`
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      text: '',
      toolCalls: [],
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInputText('')
    setIsStreaming(true)

    // Stream generator: either mock generator or real SSE fetch
    if (useMock) {
      const stream = replayMockAskStream()
      for await (const event of stream) {
        processEvent(assistantMsgId, event.event, event.data)
      }
      setIsStreaming(false)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

      if (!res.ok || !res.body) {
        throw new Error(`Server returned ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          const lines = part.split('\n')
          let eventName = 'message'
          let dataStr = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventName = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6).trim()
            }
          }

          if (dataStr) {
            try {
              const data = JSON.parse(dataStr)
              processEvent(assistantMsgId, eventName, data)
            } catch (err) {
              console.error('SSE JSON parse error:', err)
            }
          }
        }
      }
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, text: `Error connecting to backend: ${err.message}` }
            : m
        )
      )
    } finally {
      setIsStreaming(false)
    }
  }

  // Handle incoming stream events
  const processEvent = (msgId: string, event: string, data: any) => {
    if (event === 'tool_call') {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== msgId) return m
          const existing = m.toolCalls || []
          return {
            ...m,
            toolCalls: [...existing, { id: data.id, name: data.name, input: data.input }],
          }
        })
      )
    } else if (event === 'tool_result') {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== msgId) return m
          const existing = m.toolCalls || []
          const updated = existing.map((tc) =>
            tc.id === data.id ? { ...tc, summary: data.summary } : tc
          )
          return { ...m, toolCalls: updated }
        })
      )

      if (data.graph_elements) {
        setGraphElements((prev) => {
          const nodeMap = new Map(prev.nodes.map((n) => [n.id, n]))
          const edgeMap = new Map(prev.edges.map((e) => [e.id, e]))
          for (const n of data.graph_elements.nodes || []) nodeMap.set(n.id, n)
          for (const e of data.graph_elements.edges || []) edgeMap.set(e.id, e)
          return {
            nodes: Array.from(nodeMap.values()),
            edges: Array.from(edgeMap.values()),
          }
        })
      }
    } else if (event === 'token') {
      setMessages((prev) =>
        prev.map((m) => (m.id === msgId ? { ...m, text: (m.text || '') + data.text } : m))
      )
    } else if (event === 'answer') {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? {
                ...m,
                text: data.markdown,
                citations: data.citations,
                verification: data.verification,
              }
            : m
        )
      )
      if (data.path) {
        setHighlightedPath(data.path)
      }
    }
  }

  // Node click: expand neighbors via /subgraph or load decision
  const handleNodeClick = async (nodeId: string) => {
    if (nodeId.startsWith('Decision:')) {
      const decId = nodeId.replace('Decision:', '')
      loadDecisionDetail(decId)
    }

    if (useMock) return

    try {
      const res = await fetch(`${API_BASE}/subgraph?center=${encodeURIComponent(nodeId)}&depth=1`)
      if (res.ok) {
        const sub: GraphElements = await res.json()
        setGraphElements((prev) => {
          const nodeMap = new Map(prev.nodes.map((n) => [n.id, n]))
          const edgeMap = new Map(prev.edges.map((e) => [e.id, e]))
          for (const n of sub.nodes) nodeMap.set(n.id, n)
          for (const e of sub.edges) edgeMap.set(e.id, e)
          return {
            nodes: Array.from(nodeMap.values()),
            edges: Array.from(edgeMap.values()),
          }
        })
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadDecisionDetail = async (decId: string) => {
    setSelectedCitationId(null)
    setRightTab('evidence')
    if (useMock) {
      setSelectedDecision(MOCK_DECISION_DETAIL)
      return
    }
    try {
      const res = await fetch(`${API_BASE}/decisions/${decId}`)
      if (res.ok) {
        const data: DecisionDetail = await res.json()
        setSelectedDecision(data)
      }
    } catch {
      setSelectedDecision(MOCK_DECISION_DETAIL)
    }
  }

  // Run Decision Guard check
  const handleRunGuard = async () => {
    setGuardLoading(true)
    if (useMock) {
      await new Promise((r) => setTimeout(r, 600))
      setGuardResult(MOCK_GUARD_RESPONSE)
      setGuardLoading(false)
      return
    }

    try {
      const paths = guardPaths
        .split(',')
        .map((p) => p.trim())
        .filter(Boolean)
      const res = await fetch(`${API_BASE}/guard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: guardDescription,
          paths,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setGuardResult(data)
      }
    } catch {
      setGuardResult(MOCK_GUARD_RESPONSE)
    } finally {
      setGuardLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw' }}>
      {/* Top Health Header */}
      <header
        style={{
          height: 48,
          backgroundColor: '#0f172a',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          fontSize: '13px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 700, letterSpacing: '0.5px', color: '#38bdf8' }}>
            DECISION ARCHAEOLOGIST
          </span>
          <span
            style={{
              backgroundColor: '#1e293b',
              padding: '2px 8px',
              borderRadius: 4,
              color: '#94a3b8',
              fontSize: '11px',
            }}
          >
            {health.graph}
          </span>
          {!useMock && health.llm_mode && health.llm_mode !== 'live' && (
            <span
              title={
                health.llm_mode === 'offline'
                  ? 'DIG_OFFLINE=1: answers are canned demo replies, not a live model.'
                  : 'No GEMINI_API_KEY set: questions will return an error.'
              }
              style={{
                backgroundColor: health.llm_mode === 'offline' ? '#78350f' : '#7f1d1d',
                padding: '2px 8px',
                borderRadius: 4,
                color: '#fde68a',
                fontSize: '11px',
              }}
            >
              {health.llm_mode === 'offline' ? 'OFFLINE DEMO MODE' : 'NO API KEY'}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: '#94a3b8' }}>
            <strong style={{ color: '#10b981' }}>{health.counts.Decision}</strong> Decisions
          </span>
          <span style={{ color: '#94a3b8' }}>
            <strong style={{ color: '#3b82f6' }}>{health.counts.Person}</strong> People
          </span>
          <span style={{ color: '#94a3b8' }}>
            <strong style={{ color: '#a855f7' }}>{health.counts.Evidence}</strong> Evidence
          </span>
          <span style={{ color: '#94a3b8' }}>
            <strong style={{ color: '#f59e0b' }}>
              {health.counts.PullRequest + health.counts.Issue}
            </strong>{' '}
            Threads
          </span>
          <button
            onClick={() => setUseMock(!useMock)}
            style={{
              backgroundColor: useMock ? '#3b82f6' : '#1e293b',
              color: '#f8fafc',
              border: '1px solid #334155',
              padding: '3px 10px',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: '11px',
            }}
          >
            {useMock ? 'Mode: Mock Replay' : 'Mode: Live Backend'}
          </button>
        </div>
      </header>

      {/* Main 3-Pane Body */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left Pane: Chat */}
        <div
          style={{
            width: '32%',
            minWidth: 340,
            maxWidth: 460,
            backgroundColor: '#0d1322',
            borderRight: '1px solid #1e293b',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Quick Questions Header */}
          <div
            style={{
              padding: '10px 14px',
              borderBottom: '1px solid #1e293b',
              display: 'flex',
              gap: 6,
              overflowX: 'auto',
            }}
          >
            <button
              onClick={() => handleAsk('Why was Python 3.6 dropped?')}
              style={{
                backgroundColor: '#1e293b',
                color: '#94a3b8',
                border: '1px solid #334155',
                padding: '4px 8px',
                borderRadius: 4,
                fontSize: '11px',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Why drop Py3.6?
            </button>
            <button
              onClick={() => handleAsk('Who knows flask/compat module?')}
              style={{
                backgroundColor: '#1e293b',
                color: '#94a3b8',
                border: '1px solid #334155',
                padding: '4px 8px',
                borderRadius: 4,
                fontSize: '11px',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Who knows compat?
            </button>
            <button
              onClick={() => handleAsk('Who are the most central engineers?')}
              style={{
                backgroundColor: '#1e293b',
                color: '#94a3b8',
                border: '1px solid #334155',
                padding: '4px 8px',
                borderRadius: 4,
                fontSize: '11px',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Central people
            </button>
          </div>

          {/* Messages list */}
          <div
            ref={chatScrollRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '14px',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            {messages.length === 0 && (
              <div
                style={{
                  textAlign: 'center',
                  marginTop: 80,
                  color: '#64748b',
                  fontSize: '13px',
                }}
              >
                <div style={{ fontSize: '28px', marginBottom: 8 }}>🏛️</div>
                Ask any question about repository decisions, deprecated APIs, or code ownership.
              </div>
            )}

            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '92%',
                }}
              >
                {m.role === 'user' ? (
                  <div
                    style={{
                      backgroundColor: '#2563eb',
                      padding: '8px 14px',
                      borderRadius: '12px 12px 2px 12px',
                      fontSize: '13px',
                      color: '#ffffff',
                    }}
                  >
                    {m.text}
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {/* Tool Calls Chips */}
                    {m.toolCalls && m.toolCalls.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {m.toolCalls.map((tc) => (
                          <div
                            key={tc.id}
                            style={{
                              backgroundColor: '#1e293b',
                              border: '1px solid #334155',
                              padding: '5px 10px',
                              borderRadius: 6,
                              fontSize: '11px',
                              color: '#cbd5e1',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                            }}
                          >
                            <span style={{ fontWeight: 600, color: '#38bdf8' }}>
                              ⚡ {tc.name}
                            </span>
                            <span style={{ color: '#94a3b8' }}>
                              {tc.summary || 'Executing...'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Answer Markdown / Text */}
                    {m.text && (
                      <div
                        style={{
                          backgroundColor: '#1e293b',
                          padding: '12px 14px',
                          borderRadius: '4px 12px 12px 12px',
                          fontSize: '13px',
                          lineHeight: '1.6',
                          color: '#e2e8f0',
                          border: '1px solid #334155',
                        }}
                      >
                        {m.text}
                      </div>
                    )}

                    {/* Verification Trust Badge */}
                    {m.verification && (
                      <div
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          backgroundColor:
                            m.verification.invalid === 0
                              ? 'rgba(16, 185, 129, 0.15)'
                              : 'rgba(239, 68, 68, 0.15)',
                          border: `1px solid ${
                            m.verification.invalid === 0 ? '#10b981' : '#ef4444'
                          }`,
                          borderRadius: 4,
                          padding: '3px 8px',
                          fontSize: '11px',
                          color: m.verification.invalid === 0 ? '#10b981' : '#ef4444',
                        }}
                      >
                        <span>{m.verification.invalid === 0 ? '✓' : '⚠'}</span>
                        <span>
                          {m.verification.invalid === 0
                            ? 'All citations verified against graph'
                            : 'Unverified claims detected'}
                        </span>
                        {m.verification.repaired && <span>(Repaired)</span>}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Chat Input */}
          <div
            style={{
              padding: 12,
              borderTop: '1px solid #1e293b',
              display: 'flex',
              gap: 8,
              backgroundColor: '#0f172a',
            }}
          >
            <input
              type="text"
              placeholder="Ask about why choices were made..."
              value={inputText}
              disabled={isStreaming}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAsk(inputText)}
              style={{
                flex: 1,
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 6,
                padding: '8px 12px',
                color: '#f8fafc',
                fontSize: '13px',
                outline: 'none',
              }}
            />
            <button
              disabled={isStreaming || !inputText.trim()}
              onClick={() => handleAsk(inputText)}
              style={{
                backgroundColor: '#2563eb',
                border: 'none',
                borderRadius: 6,
                padding: '8px 16px',
                color: '#ffffff',
                fontWeight: 600,
                fontSize: '13px',
                cursor: isStreaming ? 'not-allowed' : 'pointer',
                opacity: isStreaming ? 0.6 : 1,
              }}
            >
              Ask
            </button>
          </div>
        </div>

        {/* Center Pane: Graph Canvas & Timeline */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#090d16',
          }}
        >
          {/* Center Tabs Header */}
          <div
            style={{
              height: 40,
              backgroundColor: '#0f172a',
              borderBottom: '1px solid #1e293b',
              display: 'flex',
              alignItems: 'center',
              padding: '0 12px',
              gap: 8,
            }}
          >
            <button
              onClick={() => setCenterTab('graph')}
              style={{
                backgroundColor: centerTab === 'graph' ? '#1e293b' : 'transparent',
                color: centerTab === 'graph' ? '#38bdf8' : '#94a3b8',
                border: 'none',
                padding: '6px 12px',
                borderRadius: 4,
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
              }}
            >
              Graph Canvas
            </button>
            <button
              onClick={() => setCenterTab('timeline')}
              style={{
                backgroundColor: centerTab === 'timeline' ? '#1e293b' : 'transparent',
                color: centerTab === 'timeline' ? '#38bdf8' : '#94a3b8',
                border: 'none',
                padding: '6px 12px',
                borderRadius: 4,
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
              }}
            >
              Decision Timeline ({decisions.length})
            </button>
          </div>

          <div style={{ flex: 1, position: 'relative' }}>
            {centerTab === 'graph' ? (
              <GraphCanvas
                elements={graphElements}
                highlightedPath={highlightedPath}
                onNodeClick={handleNodeClick}
              />
            ) : (
              <div style={{ padding: 16, overflowY: 'auto', height: '100%' }}>
                <h3 style={{ fontSize: '15px', color: '#f1f5f9', marginBottom: 16 }}>
                  Chronological Decision History
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {decisions.map((dec) => (
                    <div
                      key={dec.id}
                      onClick={() => loadDecisionDetail(dec.id)}
                      style={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: 8,
                        padding: '12px 16px',
                        cursor: 'pointer',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: 6,
                        }}
                      >
                        <span style={{ fontWeight: 600, color: '#f8fafc', fontSize: '14px' }}>
                          {dec.title}
                        </span>
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: 4,
                            backgroundColor:
                              dec.status === 'active'
                                ? 'rgba(16, 185, 129, 0.2)'
                                : dec.status === 'superseded'
                                ? 'rgba(245, 158, 11, 0.2)'
                                : 'rgba(239, 68, 68, 0.2)',
                            color:
                              dec.status === 'active'
                                ? '#10b981'
                                : dec.status === 'superseded'
                                ? '#f59e0b'
                                : '#ef4444',
                          }}
                        >
                          {dec.status.toUpperCase()}
                        </span>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          gap: 12,
                          color: '#94a3b8',
                          fontSize: '12px',
                        }}
                      >
                        <span>Date: {dec.decided_at?.slice(0, 10) || 'Unknown'}</span>
                        <span>Type: {dec.type}</span>
                        <span>Modules: {dec.modules.join(', ') || 'N/A'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Pane: Evidence & Decision Guard */}
        <div
          style={{
            width: '28%',
            minWidth: 320,
            maxWidth: 440,
            backgroundColor: '#0d1322',
            borderLeft: '1px solid #1e293b',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Right Tab Header */}
          <div
            style={{
              height: 40,
              backgroundColor: '#0f172a',
              borderBottom: '1px solid #1e293b',
              display: 'flex',
              alignItems: 'center',
              padding: '0 12px',
              gap: 8,
            }}
          >
            <button
              onClick={() => setRightTab('evidence')}
              style={{
                backgroundColor: rightTab === 'evidence' ? '#1e293b' : 'transparent',
                color: rightTab === 'evidence' ? '#38bdf8' : '#94a3b8',
                border: 'none',
                padding: '6px 12px',
                borderRadius: 4,
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
              }}
            >
              Evidence & Context
            </button>
            <button
              onClick={() => setRightTab('guard')}
              style={{
                backgroundColor: rightTab === 'guard' ? '#1e293b' : 'transparent',
                color: rightTab === 'guard' ? '#38bdf8' : '#94a3b8',
                border: 'none',
                padding: '6px 12px',
                borderRadius: 4,
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '12px',
              }}
            >
              Decision Guard
            </button>
          </div>

          <div ref={evidenceRef} style={{ flex: 1, overflowY: 'auto', padding: 14 }}>
            {rightTab === 'evidence' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Active Message Citations */}
                {messages.length > 0 &&
                  messages[messages.length - 1]?.citations &&
                  messages[messages.length - 1].citations!.length > 0 && (
                    <div>
                      <h4
                        style={{
                          fontSize: '12px',
                          textTransform: 'uppercase',
                          color: '#38bdf8',
                          letterSpacing: '0.5px',
                          marginBottom: 10,
                        }}
                      >
                        Verified Citations ({messages[messages.length - 1].citations!.length})
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {messages[messages.length - 1].citations!.map((cit) => (
                          <div
                            key={cit.evidence_id}
                            style={{
                              backgroundColor: '#1e293b',
                              border:
                                selectedCitationId === cit.evidence_id
                                  ? '1px solid #38bdf8'
                                  : '1px solid #334155',
                              borderRadius: 6,
                              padding: '10px 12px',
                            }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                marginBottom: 6,
                              }}
                            >
                              <span
                                style={{
                                  backgroundColor: '#3b82f6',
                                  color: '#fff',
                                  fontSize: '10px',
                                  padding: '1px 6px',
                                  borderRadius: 3,
                                  fontWeight: 600,
                                }}
                              >
                                [{cit.n}]
                              </span>
                              <a
                                href={cit.url}
                                target="_blank"
                                rel="noreferrer"
                                style={{
                                  color: '#38bdf8',
                                  fontSize: '11px',
                                  textDecoration: 'none',
                                }}
                              >
                                View on GitHub ↗
                              </a>
                            </div>
                            <blockquote
                              style={{
                                fontStyle: 'italic',
                                color: '#cbd5e1',
                                fontSize: '12px',
                                borderLeft: '2px solid #a855f7',
                                paddingLeft: 8,
                                margin: '6px 0',
                              }}
                            >
                              "{cit.quote}"
                            </blockquote>
                            <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                              By @{cit.author} on {cit.ts?.slice(0, 10)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Selected Decision Detail */}
                {selectedDecision && (
                  <div
                    style={{
                      borderTop: '1px solid #1e293b',
                      paddingTop: 16,
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: 6,
                      }}
                    >
                      <h4 style={{ fontSize: '14px', color: '#f8fafc' }}>
                        {selectedDecision.decision.title}
                      </h4>
                    </div>
                    <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: 12 }}>
                      {selectedDecision.decision.summary}
                    </p>

                    <h5 style={{ fontSize: '11px', color: '#38bdf8', marginBottom: 6 }}>
                      Engineers who decided:
                    </h5>
                    <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                      {selectedDecision.people.map((p) => (
                        <span
                          key={p.login}
                          style={{
                            backgroundColor: '#1e293b',
                            padding: '3px 8px',
                            borderRadius: 4,
                            fontSize: '11px',
                            color: '#93c5fd',
                          }}
                        >
                          @{p.login} ({p.role})
                        </span>
                      ))}
                    </div>

                    <h5 style={{ fontSize: '11px', color: '#38bdf8', marginBottom: 6 }}>
                      Affected Files:
                    </h5>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {selectedDecision.impact.files.map((f) => (
                        <code
                          key={f}
                          style={{
                            backgroundColor: '#090d16',
                            padding: '3px 6px',
                            borderRadius: 3,
                            fontSize: '11px',
                            color: '#e2e8f0',
                          }}
                        >
                          {f}
                        </code>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Decision Guard Tab */
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: '1.4' }}>
                  Check planned architecture or PR proposals against past recorded decisions to
                  prevent regressions and conflicts.
                </p>

                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '11px',
                      color: '#cbd5e1',
                      marginBottom: 4,
                    }}
                  >
                    Proposed Change Description:
                  </label>
                  <textarea
                    rows={3}
                    value={guardDescription}
                    onChange={(e) => setGuardDescription(e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: 6,
                      padding: 8,
                      color: '#f8fafc',
                      fontSize: '12px',
                    }}
                  />
                </div>

                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '11px',
                      color: '#cbd5e1',
                      marginBottom: 4,
                    }}
                  >
                    Affected File Paths (comma separated):
                  </label>
                  <input
                    type="text"
                    value={guardPaths}
                    onChange={(e) => setGuardPaths(e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: 6,
                      padding: '6px 8px',
                      color: '#f8fafc',
                      fontSize: '12px',
                    }}
                  />
                </div>

                <button
                  disabled={guardLoading}
                  onClick={handleRunGuard}
                  style={{
                    backgroundColor: '#dc2626',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: 6,
                    padding: '8px 12px',
                    fontWeight: 600,
                    fontSize: '12px',
                    cursor: guardLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {guardLoading ? 'Analyzing Conflicts...' : 'Check Against Past Decisions'}
                </button>

                {guardResult && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                    {guardResult.conflicts.map((conf) => (
                      <div
                        key={conf.decision_id}
                        style={{
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          border: '1px solid #ef4444',
                          borderRadius: 6,
                          padding: 10,
                        }}
                      >
                        <div
                          style={{
                            fontWeight: 600,
                            color: '#ef4444',
                            fontSize: '12px',
                            marginBottom: 4,
                          }}
                        >
                          ⚠️ Conflict: {conf.title}
                        </div>
                        <p style={{ fontSize: '11px', color: '#fca5a5', marginBottom: 6 }}>
                          {conf.why}
                        </p>
                        <div style={{ fontSize: '10px', color: '#cbd5e1' }}>
                          Suggested Reviewers: {conf.people.map((p) => `@${p}`).join(', ')}
                        </div>
                      </div>
                    ))}

                    {guardResult.alignments.map((align) => (
                      <div
                        key={align.decision_id}
                        style={{
                          backgroundColor: 'rgba(16, 185, 129, 0.1)',
                          border: '1px solid #10b981',
                          borderRadius: 6,
                          padding: 10,
                        }}
                      >
                        <div
                          style={{
                            fontWeight: 600,
                            color: '#10b981',
                            fontSize: '12px',
                            marginBottom: 4,
                          }}
                        >
                          ✓ Aligns: {align.title}
                        </div>
                        <p style={{ fontSize: '11px', color: '#6ee7b7' }}>{align.why}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
