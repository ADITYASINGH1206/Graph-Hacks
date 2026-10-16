import { useEffect, useMemo, useRef, useState } from 'react'
import { GraphCanvas } from '../components/GraphCanvas'
import { Page, PageHeader, SourceNotice, StatusDot, card, label } from '../components/ui'
import { formatDate, getJson } from '../lib/api'
import { useSession } from '../lib/session'
import { DEMO_RANGE, demoSnapshot } from '../mock/insights'
import type { Snapshot, SnapshotDecision, TimelineRange } from '../types'

const DAY = 86_400_000
const toIso = (ms: number) => new Date(ms).toISOString().slice(0, 10)
/** UTC midnight of an ISO timestamp, so the slider steps in whole calendar days. */
const dayStart = (iso: string) => Date.parse(iso.slice(0, 10) + 'T00:00:00Z')

/** Offset in days for a `#/time?date=YYYY-MM-DD` deep link, or null if there is none. */
function offsetFromHash(r: TimelineRange): number | null {
  const wanted = new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('date')
  if (!wanted || !/^\d{4}-\d{2}-\d{2}$/.test(wanted) || !r.min_date || !r.max_date) return null
  const wantedMs = Date.parse(wanted + 'T00:00:00Z')
  if (Number.isNaN(wantedMs)) return null
  const span = Math.round((dayStart(r.max_date) - dayStart(r.min_date)) / DAY)
  return Math.min(span, Math.max(0, Math.round((wantedMs - dayStart(r.min_date)) / DAY)))
}

export function TimeMachine() {
  const { demo } = useSession()
  const [range, setRange] = useState<TimelineRange | null>(null)
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [offset, setOffset] = useState(0) // days from min_date
  const [playing, setPlaying] = useState(false)
  const [loadedFor, setLoadedFor] = useState<boolean | null>(null)

  const minMs = range?.min_date ? dayStart(range.min_date) : 0
  const maxMs = range?.max_date ? dayStart(range.max_date) : 0
  const totalDays = Math.max(0, Math.round((maxMs - minMs) / DAY))
  const date = toIso(minMs + offset * DAY)

  // Load the timeline bounds (reset when the data source changes).
  useEffect(() => {
    const ctrl = new AbortController()
    setError(null)
    setSnap(null)
    setRange(null)
    setPlaying(false)
    const load = async () => {
      try {
        const r = demo ? DEMO_RANGE : await getJson<TimelineRange>('/timeline/range', ctrl.signal)
        if (ctrl.signal.aborted) return
        setRange(r)
        setLoadedFor(demo)
        // start at the newest date: "what is true today"
        const span = r.min_date && r.max_date ? Math.round((dayStart(r.max_date) - dayStart(r.min_date)) / DAY) : 0
        setOffset(offsetFromHash(r) ?? span)
      } catch (e) {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Failed to load timeline')
      }
    }
    void load()
    return () => ctrl.abort()
  }, [demo])

  // A deep link clicked while already on this page (e.g. from the command palette).
  useEffect(() => {
    if (!range) return
    const onHash = () => {
      const o = offsetFromHash(range)
      if (o !== null) {
        setPlaying(false)
        setOffset(o)
      }
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [range])

  // Fetch the snapshot for the chosen date (debounced; stale responses are aborted).
  useEffect(() => {
    if (!range?.min_date || loadedFor !== demo) return
    const ctrl = new AbortController()
    const t = setTimeout(async () => {
      try {
        const endOfDay = `${date}T23:59:59Z`
        const s = demo ? demoSnapshot(endOfDay) : await getJson<Snapshot>(`/timeline/snapshot?date=${endOfDay}`, ctrl.signal)
        if (!ctrl.signal.aborted) {
          setSnap(s)
          setError(null)
        }
      } catch (e) {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : 'Failed to load snapshot')
      }
    }, 120)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [date, range, demo, loadedFor])

  // Play: advance through time, ~8 seconds end to end.
  const offsetRef = useRef(offset)
  useEffect(() => {
    offsetRef.current = offset
  }, [offset])
  useEffect(() => {
    if (!playing) return
    const step = Math.max(1, Math.round(totalDays / 80))
    const id = setInterval(() => {
      const next = offsetRef.current + step
      if (next >= totalDays) {
        setOffset(totalDays)
        setPlaying(false)
      } else {
        setOffset(next)
      }
    }, 100)
    return () => clearInterval(id)
  }, [playing, totalDays])

  const ticks = useMemo(
    () =>
      (range?.events ?? []).map((e) => ({
        ...e,
        pct: totalDays === 0 ? 0 : ((dayStart(e.date) - minMs) / DAY / totalDays) * 100,
      })),
    [range, totalDays, minMs],
  )

  const hasData = !!range?.min_date

  return (
    <Page>
      <PageHeader
        title="Time Machine"
        subtitle="Drag back in time to see what the project had decided by the end of any day, and which decisions had already been replaced by then."
      />
      <SourceNotice error={error} />

      {range && !hasData && !error && (
        <div style={{ ...card, padding: 20, color: 'var(--muted)' }}>
          No dated decisions in this graph yet{range.undated_count ? ` (${range.undated_count} have no date)` : ''}. Run{' '}
          <code>dig extract</code> first.
        </div>
      )}

      {hasData && (
        <>
          <div style={{ ...card, padding: '16px 20px', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
              <button
                onClick={() => {
                  if (!playing && offset >= totalDays) setOffset(0)
                  setPlaying((p) => !p)
                }}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: '50%',
                  border: '1px solid var(--line-2)',
                  background: 'var(--panel-2)',
                  color: 'var(--text)',
                  cursor: 'pointer',
                }}
                aria-label={playing ? 'Pause' : 'Play through time'}
              >
                {playing ? '❚❚' : '▶'}
              </button>
              <div>
                <div style={label}>Viewing the project as of</div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 26 }}>{date}</div>
              </div>
              {snap && (
                <div style={{ marginLeft: 'auto', textAlign: 'right', fontSize: 13, color: 'var(--muted)' }}>
                  <strong style={{ color: 'var(--ok)' }}>{snap.active.length}</strong> active ·{' '}
                  <strong style={{ color: 'var(--warn)' }}>{snap.ended.length}</strong> replaced ·{' '}
                  {snap.upcoming_count} not yet made
                </div>
              )}
            </div>
            <div style={{ position: 'relative', padding: '0 4px' }}>
              <input
                type="range"
                min={0}
                max={totalDays}
                value={offset}
                onChange={(e) => {
                  setPlaying(false)
                  setOffset(Number(e.target.value))
                }}
                aria-label="Date"
                aria-valuetext={date}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
              <div style={{ position: 'relative', height: 22 }}>
                {ticks.map((t) => (
                  <button
                    key={`${t.decision_id}-${t.kind}`}
                    title={`${t.kind === 'decided' ? 'Decided' : 'Replaced'} ${formatDate(t.date)}: ${t.title}`}
                    onClick={() => {
                      setPlaying(false)
                      setOffset(Math.round((dayStart(t.date) - minMs) / DAY))
                    }}
                    style={{
                      position: 'absolute',
                      left: `${t.pct}%`,
                      top: 4,
                      width: 10,
                      height: 10,
                      transform: 'translateX(-50%) rotate(45deg)',
                      border: 'none',
                      cursor: 'pointer',
                      background: t.kind === 'decided' ? 'var(--ok)' : 'var(--warn)',
                    }}
                    aria-label={`${t.kind} ${t.title} ${formatDate(t.date)}`}
                  />
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)' }}>
                <span>{formatDate(range?.min_date)}</span>
                <span>
                  <span style={{ color: 'var(--ok)' }}>◆</span> decided <span style={{ color: 'var(--warn)' }}>◆</span> replaced
                </span>
                <span>{formatDate(range?.max_date)}</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(280px, 2fr)', gap: 16 }}>
            <div style={{ ...card, height: 460, overflow: 'hidden' }}>
              {snap && snap.graph.nodes.length > 0 ? (
                <GraphCanvas elements={snap.graph} mode="replace" />
              ) : (
                <div style={{ height: '100%', display: 'grid', placeItems: 'center', color: 'var(--muted)', fontSize: 14 }}>
                  Nothing had been decided yet on this date.
                </div>
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <DecisionList title="In force" items={snap?.active ?? []} empty="No active decisions." asOf={date} />
              <DecisionList title="Already replaced" items={snap?.ended ?? []} empty="Nothing replaced yet." asOf={date} />
              {snap && snap.undated_count > 0 && (
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {snap.undated_count} decisions have no date and are not shown.
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </Page>
  )
}

function DecisionList({ title, items, empty, asOf }: { title: string; items: SnapshotDecision[]; empty: string; asOf: string }) {
  return (
    <div style={{ ...card, padding: 14 }}>
      <div style={{ ...label, marginBottom: 8 }}>
        {title} ({items.length})
      </div>
      {items.length === 0 && <p style={{ fontSize: 13, color: 'var(--muted)' }}>{empty}</p>}
      {items.map((d) => (
        <div key={d.id} style={{ padding: '8px 0', borderTop: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
            <StatusDot status={d.status} />
            <span>{d.title}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            decided {formatDate(d.decided_at)}
            {d.ended_at ? ` · ${d.ended_at.slice(0, 10) > asOf ? 'replaced later, on' : 'replaced'} ${formatDate(d.ended_at)}` : ''}
            {d.modules.length ? ` · ${d.modules.join(', ')}` : ''}
          </div>
        </div>
      ))}
    </div>
  )
}
