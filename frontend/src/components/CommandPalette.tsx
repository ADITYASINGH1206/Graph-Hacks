import { useEffect, useMemo, useRef, useState } from 'react'
import { getJson } from '../lib/api'
import { navigate } from '../lib/router'
import { useSession } from '../lib/session'
import { MOCK_DECISIONS } from '../mock/server'
import type { DecisionTimelineItem } from '../types'

interface Command {
  id: string
  label: string
  hint: string
  run: () => void
}

interface Props {
  open: boolean
  onClose: () => void
  onStartTour: () => void
}

export function CommandPalette({ open, onClose, onStartTour }: Props) {
  const { demo, setDemo } = useSession()
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const [decisions, setDecisions] = useState<DecisionTimelineItem[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  // Load decisions when opened, so they can be jumped to in Time Machine.
  useEffect(() => {
    if (!open) return
    setQuery('')
    setCursor(0)
    inputRef.current?.focus()
    if (demo) {
      setDecisions(MOCK_DECISIONS)
      return
    }
    const ctrl = new AbortController()
    getJson<{ items: DecisionTimelineItem[] }>('/decisions?limit=50', ctrl.signal)
      .then((r) => setDecisions(r.items ?? []))
      .catch(() => setDecisions([]))
    return () => ctrl.abort()
  }, [open, demo])

  const commands = useMemo<Command[]>(() => {
    const go = (r: Parameters<typeof navigate>[0]) => () => navigate(r)
    const base: Command[] = [
      { id: 'home', label: 'Home', hint: 'Page', run: go('home') },
      { id: 'app', label: 'Ask the archive', hint: 'Page', run: go('app') },
      { id: 'time', label: 'Time Machine', hint: 'Page', run: go('time') },
      { id: 'guard', label: 'PR Guard', hint: 'Page', run: go('guard') },
      { id: 'risk', label: 'Knowledge-risk map', hint: 'Page', run: go('risk') },
      { id: 'tour', label: 'Start guided tour', hint: 'Action', run: onStartTour },
      { id: 'demo', label: demo ? 'Switch to live backend' : 'Switch to demo data', hint: 'Action', run: () => setDemo(!demo) },
    ]
    const dated = decisions
      .filter((d) => d.decided_at && /^\d{4}-\d{2}-\d{2}/.test(d.decided_at))
      .map<Command>((d) => ({
        id: `dec_${d.id}`,
        label: d.title,
        hint: `Decision · ${d.decided_at!.slice(0, 10)}`,
        run: () => {
          window.location.hash = `#/time?date=${d.decided_at!.slice(0, 10)}`
        },
      }))
    return [...base, ...dated]
  }, [decisions, demo, setDemo, onStartTour])

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? commands.filter((c) => c.label.toLowerCase().includes(q)) : commands
  }, [commands, query])

  if (!open) return null

  const choose = (c: Command | undefined) => {
    if (!c) return
    onClose()
    c.run()
  }

  return (
    <div
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.55)', display: 'flex', justifyContent: 'center', alignItems: 'flex-start', paddingTop: '14vh' }}
    >
      <div
        role="dialog"
        aria-label="Command palette"
        style={{ width: 'min(560px, calc(100vw - 32px))', background: 'var(--panel-2)', border: '1px solid var(--line-2)', borderRadius: 12, overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,0.6)' }}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setCursor(0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setCursor((c) => Math.min(c + 1, shown.length - 1))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setCursor((c) => Math.max(c - 1, 0))
            } else if (e.key === 'Enter') {
              choose(shown[cursor])
            } else if (e.key === 'Escape') {
              onClose()
            }
          }}
          placeholder="Go to a page, run an action, or jump to a decision…"
          aria-label="Search commands"
          style={{ width: '100%', background: 'transparent', border: 'none', borderBottom: '1px solid var(--line)', color: 'var(--text)', padding: '14px 16px', fontSize: 15, outline: 'none' }}
        />
        <ul role="listbox" style={{ listStyle: 'none', maxHeight: 340, overflowY: 'auto' }}>
          {shown.length === 0 && <li style={{ padding: 16, color: 'var(--muted)', fontSize: 14 }}>No matches.</li>}
          {shown.map((c, i) => (
            <li
              key={c.id}
              role="option"
              aria-selected={i === cursor}
              onMouseEnter={() => setCursor(i)}
              onClick={() => choose(c)}
              style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '10px 16px', cursor: 'pointer', fontSize: 14, background: i === cursor ? 'var(--line)' : 'transparent' }}
            >
              <span>{c.label}</span>
              <span style={{ color: 'var(--muted)', fontSize: 12 }}>{c.hint}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
