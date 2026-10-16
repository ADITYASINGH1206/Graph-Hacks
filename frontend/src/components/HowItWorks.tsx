import { useEffect, useState } from 'react'
import './hiw.css'

const STEPS = [
  { title: 'Ingest', body: 'Pull requests, issues and review threads are fetched from GitHub and cached on disk.' },
  { title: 'Extract', body: 'A model reads each discussion and proposes decisions, with the exact words that justify them.' },
  { title: 'Verify', body: 'A quote is kept only if it appears word for word in the source. Anything else is dropped.' },
  { title: 'Ask', body: 'The agent walks the graph to answer. Every claim links to a verified quote.' },
]

const STEP_MS = 6000

const d = (s: number) => ({ '--d': `${s}s` }) as React.CSSProperties
const len = (n: number, s = 0) => ({ '--len': n, '--d': `${s}s` }) as React.CSSProperties

// ---------------------------------------------------------------------------------------------
// Scenes (one SVG each, remounted per step so the CSS animations replay)
// ---------------------------------------------------------------------------------------------

function Card({ x, y, w, h, style, children }: { x: number; y: number; w: number; h: number; style?: React.CSSProperties; children?: React.ReactNode }) {
  return (
    <g className="hiw-slide" style={style}>
      <rect x={x} y={y} width={w} height={h} rx={10} fill="var(--panel-2)" stroke="var(--line-2)" />
      {children}
    </g>
  )
}

function Lines({ x, y, widths }: { x: number; y: number; widths: number[] }) {
  return (
    <>
      {widths.map((w, i) => (
        <rect key={i} x={x} y={y + i * 12} width={w} height={6} rx={3} fill="var(--line)" />
      ))}
    </>
  )
}

function SceneIngest() {
  const items = [
    ['Pull request #4400', 'davidism · 2022-03-15'],
    ['Issue #3500', 'Python 2 end of life'],
    ['Review comment', 'on PR #3900 · pgjones'],
  ]
  return (
    <svg className="hiw-svg" viewBox="0 0 760 330" role="img" aria-label="GitHub threads are fetched and cached">
      {items.map(([t, s], i) => (
        <Card key={t} x={40} y={30 + i * 95} w={330} h={78} style={d(i * 0.3)}>
          <circle cx={66} cy={55 + i * 95} r={11} fill="var(--accent-soft)" stroke="var(--accent)" />
          <text x={90} y={52 + i * 95} fontSize={14} fontWeight={600}>{t}</text>
          <text x={90} y={70 + i * 95} fontSize={11.5} className="muted">{s}</text>
          <Lines x={90} y={80 + i * 95} widths={[200, 150]} />
        </Card>
      ))}
      {[0, 1, 2].map((i) => (
        <path
          key={i}
          d={`M372 ${69 + i * 95} C 440 ${69 + i * 95}, 450 165, 520 165`}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2}
          className="hiw-draw"
          style={len(220, 0.9 + i * 0.15)}
        />
      ))}
      <g className="hiw-pop" style={d(1.5)}>
        <rect x={520} y={118} width={200} height={94} rx={12} fill="var(--text)" />
        <text x={620} y={152} textAnchor="middle" fontSize={13} fontWeight={600} style={{ fill: 'var(--panel-2)' }}>Local cache</text>
        <text x={620} y={174} textAnchor="middle" fontSize={11.5} className="mono" style={{ fill: 'var(--night-muted)' }}>keyed by content hash</text>
        <text x={620} y={194} textAnchor="middle" fontSize={11.5} style={{ fill: 'var(--night-muted)' }}>re-runs are free</text>
      </g>
    </svg>
  )
}

function SceneExtract() {
  return (
    <svg className="hiw-svg" viewBox="0 0 760 330" role="img" aria-label="A model proposes a decision and the sentence that supports it">
      <Card x={30} y={30} w={440} h={250}>
        <text x={52} y={62} fontSize={14} fontWeight={600}>Pull request #4400</text>
        <text x={52} y={80} fontSize={11.5} className="muted">davidism · 2022-03-15</text>
        <Lines x={52} y={98} widths={[360, 300]} />
        <rect className="hiw-sweep" style={d(0.7)} x={48} y={140} width={396} height={44} rx={6} fill="#f1d9a0" />
        <text x={56} y={158} fontSize={13} className="mono">Python 3.6 and 3.7 are now EOL,</text>
        <text x={56} y={176} fontSize={13} className="mono">bump minimum Python version to 3.8.</text>
        <Lines x={52} y={206} widths={[340, 250, 300]} />
      </Card>
      <path d="M470 160 C 505 160, 505 160, 540 160" fill="none" stroke="var(--accent)" strokeWidth={2} markerEnd="url(#hiw-arrow)" className="hiw-draw" style={len(80, 1.5)} />
      <defs>
        <marker id="hiw-arrow" viewBox="0 0 10 10" refX={8} refY={5} markerWidth={7} markerHeight={7} orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--accent)" />
        </marker>
      </defs>
      <g className="hiw-pop" style={d(1.9)}>
        <rect x={545} y={100} width={190} height={120} rx={12} fill="var(--panel-2)" stroke="var(--ok)" strokeWidth={2} />
        <rect x={545} y={100} width={190} height={26} rx={12} fill="var(--ok-bg)" />
        <text x={560} y={118} fontSize={11.5} fontWeight={600} style={{ fill: 'var(--ok-ink)' }}>DECISION · deprecation</text>
        <text x={560} y={150} fontSize={14} fontWeight={600}>Drop Python 3.6</text>
        <text x={560} y={168} fontSize={14} fontWeight={600}>support</text>
        <text x={560} y={196} fontSize={11.5} className="muted">confidence 0.98 · 2022-03-20</text>
      </g>
    </svg>
  )
}

function SceneVerify() {
  return (
    <svg className="hiw-svg" viewBox="0 0 760 330" role="img" aria-label="Only quotes found word for word in the source are kept">
      <Card x={30} y={30} w={330} h={270}>
        <text x={52} y={62} fontSize={12} fontWeight={600} className="muted">SOURCE TEXT · PR #4400</text>
        <Lines x={52} y={84} widths={[270, 220]} />
        <rect className="hiw-sweep" style={d(0.8)} x={46} y={120} width={300} height={44} rx={6} fill="#cfe5d6" />
        <text x={54} y={138} fontSize={12} className="mono">Python 3.6 and 3.7 are now EOL,</text>
        <text x={54} y={156} fontSize={12} className="mono">bump minimum Python version to 3.8.</text>
        <Lines x={52} y={188} widths={[260, 200, 240, 150]} />
      </Card>

      <g className="hiw-slide" style={d(0.3)}>
        <rect x={400} y={30} width={330} height={108} rx={10} fill="var(--panel-2)" stroke="var(--ok-line)" strokeWidth={2} />
        <text x={418} y={58} fontSize={11.5} className="muted">CANDIDATE QUOTE A</text>
        <text x={418} y={82} fontSize={13} className="mono">“Python 3.6 and 3.7 are now</text>
        <text x={418} y={100} fontSize={13} className="mono">EOL, bump minimum …”</text>
      </g>
      <path d="M400 84 C 380 84, 372 142, 350 142" fill="none" stroke="var(--ok)" strokeWidth={2} className="hiw-draw" style={len(90, 1.2)} />
      <g className="hiw-pop" style={d(1.8)}>
        <rect x={560} y={112} width={158} height={30} rx={15} fill="var(--ok)" />
        <text x={639} y={132} textAnchor="middle" fontSize={12} fontWeight={600} style={{ fill: '#fff' }}>✓ found word for word</text>
      </g>

      <g className="hiw-slide" style={d(0.6)}>
        <g className="hiw-dim" style={d(3)}>
          <rect x={400} y={178} width={330} height={108} rx={10} fill="var(--panel-2)" stroke="var(--bad-line)" strokeWidth={2} />
          <text x={418} y={206} fontSize={11.5} className="muted">CANDIDATE QUOTE B</text>
          <text x={418} y={230} fontSize={13} className="mono">“Everyone agreed 3.6 was</text>
          <text x={418} y={248} fontSize={13} className="mono">too slow to keep.”</text>
          <rect className="hiw-sweep" style={d(3)} x={416} y={225} width={250} height={2} fill="var(--bad)" />
          <rect className="hiw-sweep" style={d(3.15)} x={416} y={243} width={180} height={2} fill="var(--bad)" />
        </g>
      </g>
      <g className="hiw-pop" style={d(3.4)}>
        <rect x={535} y={256} width={185} height={30} rx={15} fill="var(--bad)" />
        <text x={627} y={276} textAnchor="middle" fontSize={12} fontWeight={600} style={{ fill: '#fff' }}>✗ not in source: dropped</text>
      </g>
    </svg>
  )
}

/** The graph scene is also used, scaled down, as the empty state of the Ask page. */
export function SceneGraph({ compact = false }: { compact?: boolean }) {
  const node = (x: number, y: number, kind: 'dec' | 'dec2' | 'person' | 'ev' | 'mod', text: string, delay: number) => {
    const fill = kind === 'dec' ? 'var(--ok)' : kind === 'dec2' ? '#d08a2e' : kind === 'person' ? '#3b6fb6' : kind === 'mod' ? '#8a7b66' : 'var(--panel-2)'
    return (
      <g className="hiw-pop" style={d(delay)} key={text}>
        {kind === 'dec' || kind === 'dec2' ? (
          <rect x={x - 26} y={y - 18} width={52} height={36} rx={9} fill={fill} stroke="var(--panel-2)" strokeWidth={3} />
        ) : kind === 'mod' ? (
          <polygon points={`${x - 18},${y} ${x - 9},${y - 16} ${x + 9},${y - 16} ${x + 18},${y} ${x + 9},${y + 16} ${x - 9},${y + 16}`} fill={fill} stroke="var(--panel-2)" strokeWidth={3} />
        ) : (
          <circle cx={x} cy={y} r={kind === 'ev' ? 12 : 16} fill={fill} stroke={kind === 'ev' ? '#7c4dbd' : 'var(--panel-2)'} strokeWidth={kind === 'ev' ? 3 : 3} />
        )}
        <text x={x} y={y + 36} textAnchor="middle" fontSize={11.5} fontWeight={500}>{text}</text>
      </g>
    )
  }
  const edge = (x1: number, y1: number, x2: number, y2: number, label: string, delay: number, dashed = false, lx = 0, ly = 0) => (
    <g key={label}>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--line-2)" strokeWidth={1.8} strokeDasharray={dashed ? '5 4' : undefined} className={dashed ? 'hiw-fade' : 'hiw-draw'} style={dashed ? d(delay) : len(Math.hypot(x2 - x1, y2 - y1), delay)} />
      <text x={(x1 + x2) / 2 + lx} y={(y1 + y2) / 2 + ly} textAnchor="middle" fontSize={8.5} className="mono muted hiw-fade" style={d(delay + 0.3)}>{label}</text>
    </g>
  )
  return (
    <svg
      className="hiw-svg"
      viewBox={compact ? '170 50 440 250' : '0 0 760 330'}
      role="img"
      aria-label="The agent follows edges in the graph from a decision to its evidence"
      style={compact ? { maxWidth: 400, margin: '0 auto' } : undefined}
    >
      {edge(380, 150, 210, 100, 'SUPERSEDES', 0.9, true, 0, -8)}
      {edge(380, 150, 210, 250, 'AFFECTS', 1.0, false, -6, 14)}
      {edge(560, 70, 380, 150, 'SUPPORTED_BY', 1.1, false, 18, -12)}
      {edge(560, 235, 380, 150, 'MADE', 1.2, false, 18, 16)}
      {node(210, 100, 'dec2', 'Drop Python 2', 0.2)}
      {node(210, 250, 'mod', 'flask/compat', 0.4)}
      {node(380, 150, 'dec', 'Drop Python 3.6', 0.1)}
      {node(560, 70, 'ev', 'quote [1]', 0.6)}
      {node(560, 235, 'person', 'davidism', 0.8)}
      {/* the agent's path lights up last */}
      <line x1={560} y1={70} x2={380} y2={150} stroke="var(--accent)" strokeWidth={3.2} className="hiw-path" style={d(2.2)} />
      {!compact && (
        <>
          <g className="hiw-slide" style={d(0.2)}>
            <rect x={22} y={14} width={236} height={32} rx={16} fill="var(--text)" />
            <text x={140} y={35} textAnchor="middle" fontSize={12.5} style={{ fill: 'var(--panel-2)' }}>Why was Python 3.6 dropped?</text>
          </g>
          <g className="hiw-pop" style={d(2.8)}>
            <rect x={380} y={284} width={350} height={36} rx={10} fill="var(--panel-2)" stroke="var(--accent)" strokeWidth={1.5} />
            <text x={394} y={307} fontSize={12.5}>3.6 reached end of life, so support was dropped</text>
            <circle cx={716} cy={302} r={9} fill="var(--accent)" />
            <text x={716} y={306} textAnchor="middle" fontSize={11} fontWeight={700} style={{ fill: 'var(--accent-ink)' }}>1</text>
          </g>
        </>
      )}
    </svg>
  )
}

const SCENES = [SceneIngest, SceneExtract, SceneVerify, SceneGraph]

// ---------------------------------------------------------------------------------------------

export function HowItWorks() {
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [hover, setHover] = useState(false)
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const running = playing && !hover && !reduce

  useEffect(() => {
    if (!running) return
    const id = window.setTimeout(() => setStep((s) => (s + 1) % STEPS.length), STEP_MS)
    return () => window.clearTimeout(id)
  }, [running, step])

  const Scene = SCENES[step]
  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <div
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--rule)',
          borderRadius: 16,
          padding: 'clamp(12px, 3vw, 28px)',
          boxShadow: '0 24px 60px -34px rgba(22,19,15,0.4)',
        }}
      >
        <div key={step}>
          <Scene />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12, marginTop: 18 }} role="tablist" aria-label="How it works">
        {STEPS.map((s, i) => {
          const on = i === step
          return (
            <button
              key={s.title}
              role="tab"
              aria-selected={on}
              onClick={() => {
                setStep(i)
                setPlaying(false)
              }}
              style={{
                textAlign: 'left',
                background: on ? 'var(--panel-2)' : 'transparent',
                border: `1px solid ${on ? 'var(--ink)' : 'var(--rule)'}`,
                borderRadius: 12,
                padding: '12px 14px 14px',
                cursor: 'pointer',
                color: 'var(--ink)',
                position: 'relative',
                overflow: 'hidden',
                transition: 'background 0.2s, border-color 0.2s',
              }}
            >
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--layer-4)' }}>0{i + 1}</div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 19, margin: '2px 0 4px' }}>{s.title}</div>
              <div style={{ fontSize: 13, color: 'var(--ink-soft)', lineHeight: 1.45 }}>{s.body}</div>
              {on && running && (
                <span
                  key={`${step}-p`}
                  className="hiw-progress"
                  style={{ position: 'absolute', left: 0, bottom: 0, height: 3, width: '100%', background: 'var(--accent)', ['--dur' as string]: `${STEP_MS}ms` }}
                />
              )}
            </button>
          )
        })}
      </div>
      <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={() => setPlaying((p) => !p)}
          style={{ background: 'none', border: 'none', color: 'var(--ink-soft)', cursor: 'pointer', fontSize: 13, textDecoration: 'underline' }}
        >
          {playing && !reduce ? 'Pause animation' : 'Play animation'}
        </button>
      </div>
    </div>
  )
}
