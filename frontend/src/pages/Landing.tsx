import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { HowItWorks } from '../components/HowItWorks'
import { Logo } from '../components/Logo'
import { useReveal } from '../lib/reveal'
import { hrefFor } from '../lib/router'
import type { Route } from '../lib/router'
import { useSession } from '../lib/session'

/** Example decisions from the bundled Flask demo graph; shown as an illustration, labelled as such. */
const FOSSILS = [
  {
    year: '2022',
    depth: 'Surface',
    title: 'Drop Python 3.6 support',
    quote: 'Python 3.6 and 3.7 are now EOL, bump minimum Python version to 3.8.',
    source: 'Sample data · PR #4400 · davidism',
    note: 'Supersedes the older "Drop Python 2" decision.',
  },
  {
    year: '2021',
    depth: 'One layer down',
    title: 'Adopt async views and route handlers',
    quote: 'Add support for async route handlers and views using asgiref.',
    source: 'Sample data · PR #3900 · pgjones',
    note: 'Still in force: new code that fights it gets flagged by PR Guard.',
  },
  {
    year: '2020',
    depth: 'Deepest layer',
    title: 'Drop Python 2 support',
    quote: 'Python 2 has reached end of life, dropping Python 2 compatibility code across the codebase.',
    source: 'Sample data · PR #3500 · davidism',
    note: 'Replaced in 2022. Time Machine shows it in force until then.',
  },
]

const BANDS = ['var(--layer-1)', 'var(--layer-2)', 'var(--layer-3)', 'var(--layer-4)', 'var(--layer-5)']

const FEATURES: Array<{ title: string; body: string; route: Route; cta: string }> = [
  { title: 'Ask the archive', body: 'Why was this dropped? Who knows this module? What changed since the last release? Answers cite their sources.', route: 'app', cta: 'Open the workspace' },
  { title: 'Time Machine', body: 'Slide back to any date and see what the project had decided by then, and what had not yet been replaced.', route: 'time', cta: 'Travel in time' },
  { title: 'PR Guard', body: 'Paste a pull request link. We check it against past decisions and name the people who should review it.', route: 'guard', cta: 'Check a PR' },
  { title: 'Knowledge-risk map', body: 'See which modules rest on one or two people, and whether those people are still around.', route: 'risk', cta: 'See the map' },
]

const section: CSSProperties = { maxWidth: 1120, margin: '0 auto', padding: '96px 24px' }
const h2: CSSProperties = { fontFamily: 'var(--font-display)', fontWeight: 400, fontSize: 'clamp(30px, 4vw, 44px)', lineHeight: 1.1, letterSpacing: '-0.01em', margin: 0 }
const eyebrow: CSSProperties = { fontSize: 12, letterSpacing: '1.4px', textTransform: 'uppercase', color: 'var(--layer-5)', fontWeight: 600, marginBottom: 12 }

export function Landing() {
  useReveal()
  const { health, backendUp, demo } = useSession()
  const stageRef = useRef<HTMLDivElement>(null)
  const [p, setP] = useState(0)

  // Scroll progress through the tall "dig" section (0 at its top, 1 at its end).
  useEffect(() => {
    let raf = 0
    const update = () => {
      raf = 0
      const el = stageRef.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const span = r.height - window.innerHeight
      const next = span <= 0 ? 0 : Math.min(1, Math.max(0, -r.top / span))
      setP(Math.round(next * 500) / 500)
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  const active = p < 0.34 ? 0 : p < 0.67 ? 1 : 2
  const live = backendUp && !demo

  return (
    <div style={{ background: 'var(--paper)', color: 'var(--ink)', fontFamily: 'var(--font-ui)', minHeight: '100vh' }}>
      <nav
        aria-label="Primary"
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 24px',
          background: 'rgba(244,239,230,0.88)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid var(--rule)',
        }}
      >
        <a href={hrefFor('home')} style={{ fontFamily: 'var(--font-display)', fontSize: 19, color: 'var(--ink)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 10 }}>
          <Logo size={28} />
          Decision Archaeologist
        </a>
        <div style={{ display: 'flex', gap: 20, alignItems: 'center', fontSize: 14 }}>
          <a href="#how" onClick={scrollTo('how')} style={navLink}>How it works</a>
          <a href="#features" onClick={scrollTo('features')} style={navLink}>Features</a>
          <a href={hrefFor('app')} style={ctaDark}>Start digging</a>
        </div>
      </nav>

      {/* Hero */}
      <header style={{ ...section, paddingTop: 88, paddingBottom: 56, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 48, alignItems: 'center' }}>
        <div className="fade-up">
          <div style={eyebrow}>For open-source maintainers and new contributors</div>
          <h1 style={{ ...h2, fontSize: 'clamp(40px, 6vw, 68px)' }}>
            Every codebase is a pile of old decisions. <em style={{ color: 'var(--layer-4)' }}>Dig them up.</em>
          </h1>
          <p style={{ fontSize: 18, color: 'var(--ink-soft)', maxWidth: 520, margin: '20px 0 28px' }}>
            Ask why something is the way it is. You get an answer that links to the exact words someone wrote when they decided it, not a guess.
          </p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <a href={hrefFor('app')} style={{ ...ctaDark, padding: '12px 22px', fontSize: 15 }}>Start digging</a>
            <a href="#dig" onClick={scrollTo('dig')} style={{ ...ctaLight, padding: '12px 22px', fontSize: 15 }}>See how it works ↓</a>
          </div>
        </div>
        <HeroStrata />
      </header>

      {/* Scroll-driven dig */}
      <section id="dig" ref={stageRef} style={{ height: '320vh', position: 'relative' }} aria-label="Digging down through decisions">
        <div style={{ position: 'sticky', top: 56, height: 'calc(100vh - 56px)', display: 'flex', alignItems: 'center' }}>
          <div style={{ ...section, padding: '0 24px', width: '100%', display: 'grid', gridTemplateColumns: 'minmax(120px, 170px) 1fr', gap: 'clamp(20px, 5vw, 64px)', alignItems: 'stretch', height: '78%' }}>
            <div style={{ position: 'relative', borderRadius: 10, overflow: 'hidden', border: '1px solid var(--rule)' }} aria-hidden>
              {BANDS.map((c, i) => {
                const dug = p >= i / BANDS.length
                return (
                  <div
                    key={c}
                    style={{
                      height: `${100 / BANDS.length}%`,
                      background: dug ? c : 'repeating-linear-gradient(45deg, var(--paper-2), var(--paper-2) 6px, var(--paper) 6px, var(--paper) 12px)',
                      transition: 'background 0.5s ease',
                    }}
                  />
                )
              })}
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  right: 0,
                  top: `${p * 100}%`,
                  height: 3,
                  background: 'var(--ink)',
                  boxShadow: '0 0 0 3px rgba(22,19,15,0.15)',
                }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <div style={eyebrow}>Scroll to dig down</div>
              <h2 style={h2}>The deeper you go, the older the reason.</h2>
              <div style={{ display: 'grid', marginTop: 28 }}>
                {FOSSILS.map((f, i) => (
                  <article
                    key={f.title}
                    aria-hidden={i !== active}
                    style={{
                      gridArea: '1 / 1',
                      opacity: i === active ? 1 : 0,
                      transform: i === active ? 'none' : 'translateY(16px)',
                      transition: 'opacity 0.45s ease, transform 0.45s ease',
                      pointerEvents: i === active ? 'auto' : 'none',
                      background: '#fffaf0',
                      border: '1px solid var(--rule)',
                      borderLeft: '4px solid var(--layer-4)',
                      borderRadius: 10,
                      padding: '20px 22px',
                      maxWidth: 560,
                    }}
                  >
                    <div style={{ fontSize: 12, color: 'var(--ink-soft)', letterSpacing: '0.6px', textTransform: 'uppercase' }}>
                      {f.year} · {f.depth}
                    </div>
                    <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 24, margin: '6px 0 10px' }}>{f.title}</h3>
                    <blockquote style={{ fontFamily: 'var(--font-display)', fontSize: 17, lineHeight: 1.4, color: 'var(--ink)', margin: 0 }}>“{f.quote}”</blockquote>
                    <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 8 }}>{f.source}</div>
                    <div style={{ fontSize: 13, marginTop: 10, color: 'var(--layer-5)' }}>{f.note}</div>
                  </article>
                ))}
              </div>
              <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 14 }}>Illustration from the bundled sample graph. Run the ingest on a real repository to get your own.</p>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" style={section}>
        <div className="reveal">
          <div style={eyebrow}>How it works</div>
          <h2 style={{ ...h2, maxWidth: 640 }}>From a thousand threads to one answer you can check.</h2>
        </div>
        <div className="reveal" style={{ marginTop: 40 }}>
          <HowItWorks />
        </div>
        <p className="reveal" style={{ marginTop: 40, maxWidth: 680, fontSize: 15, color: 'var(--ink-soft)', borderLeft: '3px solid var(--layer-3)', paddingLeft: 16 }}>
          <strong style={{ color: 'var(--ink)' }}>What it will not do:</strong> invent a source. If a quote cannot be matched to the original text, the decision is dropped. With no API key the app says so instead of replaying canned answers.
        </p>
      </section>

      {/* Features */}
      <section id="features" style={{ background: 'var(--paper-2)' }}>
        <div style={section}>
          <div className="reveal">
            <div style={eyebrow}>What you can do</div>
            <h2 style={h2}>Four ways into the same graph.</h2>
          </div>
          <div style={{ marginTop: 40, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 20 }}>
            {FEATURES.map((f, i) => (
              <a
                key={f.title}
                href={hrefFor(f.route)}
                className="reveal"
                style={{ transitionDelay: `${i * 90}ms`, background: 'var(--paper)', border: '1px solid var(--rule)', borderRadius: 12, padding: 22, color: 'var(--ink)', textDecoration: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}
              >
                <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 22 }}>{f.title}</h3>
                <p style={{ color: 'var(--ink-soft)', fontSize: 14, flex: 1 }}>{f.body}</p>
                <span style={{ color: 'var(--layer-5)', fontWeight: 600, fontSize: 14 }}>{f.cta} →</span>
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* Graph facts */}
      <section style={{ ...section, paddingTop: 72, paddingBottom: 72 }}>
        <div className="reveal" style={{ display: 'flex', flexWrap: 'wrap', gap: 40, alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div>
            <div style={eyebrow}>{live ? 'Your graph, live' : 'Sample graph'}</div>
            <h2 style={h2}>{health.graph}</h2>
            {!live && <p style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 6 }}>Backend not connected: these are the bundled demo numbers.</p>}
          </div>
          <div style={{ display: 'flex', gap: 36, flexWrap: 'wrap' }}>
            {[
              ['Decisions', health.counts.Decision],
              ['Evidence quotes', health.counts.Evidence],
              ['People', health.counts.Person],
              ['Threads', health.counts.PullRequest + health.counts.Issue],
            ].map(([k, v]) => (
              <div key={k as string}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 40, lineHeight: 1 }}>{v}</div>
                <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{k}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA: the "underground" */}
      <section style={{ background: 'var(--night)', color: 'var(--night-text)' }}>
        <div style={{ ...section, textAlign: 'center' }}>
          <div className="reveal">
            <h2 style={{ ...h2, color: 'var(--night-text)' }}>Ready to go underground?</h2>
            <p style={{ color: 'var(--night-muted)', margin: '14px auto 28px', maxWidth: 480 }}>Open the workspace and ask your first question. The guided tour takes under a minute.</p>
            <a href={hrefFor('app')} style={{ ...ctaDark, background: 'var(--accent-bright)', color: '#1a0f08', padding: '13px 26px', fontSize: 15 }}>Start digging</a>
          </div>
        </div>
        <footer style={{ borderTop: '1px solid #2a241d', padding: '20px 24px', textAlign: 'center', fontSize: 12, color: 'var(--night-muted)' }}>
          Built for Graph Hacks 2026 on FalkorDB · Track 3, Company Brain
        </footer>
      </section>
    </div>
  )
}

function HeroStrata() {
  return (
    <div aria-hidden className="fade-up" style={{ borderRadius: 14, overflow: 'hidden', border: '1px solid var(--rule)', boxShadow: '0 20px 50px -24px rgba(22,19,15,0.35)' }}>
      {BANDS.map((c, i) => (
        <div
          key={c}
          style={{
            background: c,
            height: 62,
            display: 'flex',
            alignItems: 'center',
            padding: '0 18px',
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: i > 2 ? 'var(--paper)' : 'var(--ink)',
            borderTop: i ? '1px dashed rgba(22,19,15,0.25)' : 'none',
          }}
        >
          {['“why did we drop 3.6?”', 'PR #4400 · EOL notice', 'decision · verified quote', 'SUPERSEDES → older decision', 'FalkorDB graph'][i]}
        </div>
      ))}
    </div>
  )
}

function scrollTo(id: string) {
  return (e: React.MouseEvent) => {
    e.preventDefault()
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }
}

const navLink: CSSProperties = { color: 'var(--ink-soft)', textDecoration: 'none' }
const ctaDark: CSSProperties = { background: 'var(--ink)', color: 'var(--paper)', padding: '8px 16px', borderRadius: 8, textDecoration: 'none', fontWeight: 600, display: 'inline-block' }
const ctaLight: CSSProperties = { border: '1px solid var(--ink)', color: 'var(--ink)', borderRadius: 8, textDecoration: 'none', fontWeight: 600, display: 'inline-block' }
