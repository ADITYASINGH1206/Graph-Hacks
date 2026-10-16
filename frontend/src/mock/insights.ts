/**
 * Recorded demo data for Time Machine, Risk Map and PR Guard.
 * Mirrors the seed graph (see scripts/demo_reset.sh) so Demo mode works with no backend.
 * Pages label this clearly as demo data; it is never presented as live.
 */
import type {
  GraphElements,
  PRGuardResponse,
  RiskReport,
  Snapshot,
  SnapshotDecision,
  TimelineRange,
} from '../types'
import { MOCK_GUARD_RESPONSE } from './server'

interface DemoDecision {
  id: string
  title: string
  type: string
  summary: string
  start: string
  end: string | null
  modules: string[]
  supersedes?: string
}

const DECISIONS: DemoDecision[] = [
  {
    id: 'dec_drop_py2',
    title: 'Drop Python 2 support',
    type: 'deprecation',
    summary: 'Dropped Python 2 and 3.5 support in Flask 2.0 to modernize codebase.',
    start: '2020-05-15T18:00:00Z',
    end: '2022-03-20T16:00:00Z',
    modules: ['flask/compat'],
  },
  {
    id: 'dec_async_views',
    title: 'Adopt async views and route handlers',
    type: 'adoption',
    summary: 'Added first-class async route and view support using asgiref in Flask 2.0.',
    start: '2021-01-10T20:00:00Z',
    end: null,
    modules: ['flask/views', 'flask/app'],
  },
  {
    id: 'dec_drop_py36',
    title: 'Drop Python 3.6 support',
    type: 'deprecation',
    summary: 'Dropped Python 3.6 and 3.7 support, requiring Python 3.8+.',
    start: '2022-03-20T16:00:00Z',
    end: null,
    modules: ['flask/compat', 'flask/app'],
    supersedes: 'dec_drop_py2',
  },
]

const ms = (iso: string) => Date.parse(iso)

export const DEMO_RANGE: TimelineRange = {
  min_date: '2020-05-15T18:00:00Z',
  max_date: '2022-03-20T16:00:00Z',
  undated_count: 0,
  events: DECISIONS.flatMap((d) => [
    { date: d.start, kind: 'decided' as const, decision_id: d.id, title: d.title },
    ...(d.end ? [{ date: d.end, kind: 'ended' as const, decision_id: d.id, title: d.title }] : []),
  ]).sort((a, b) => a.date.localeCompare(b.date) || (a.kind === 'decided' ? -1 : 1) - (b.kind === 'decided' ? -1 : 1)),
}

/** Same rules as the backend: start inclusive, end exclusive. */
export function demoSnapshot(date: string): Snapshot {
  const at = ms(date.length > 10 ? date : date + 'T00:00:00Z')
  const active: SnapshotDecision[] = []
  const ended: SnapshotDecision[] = []
  let upcoming = 0
  for (const d of DECISIONS) {
    if (ms(d.start) > at) {
      upcoming += 1
      continue
    }
    const over = d.end !== null && ms(d.end) <= at
    const row: SnapshotDecision = {
      id: d.id,
      title: d.title,
      type: d.type,
      summary: d.summary,
      status: over ? 'superseded' : 'active',
      decided_at: d.start,
      ended_at: d.end,
      modules: d.modules,
    }
    ;(over ? ended : active).push(row)
  }
  const visible = new Set([...active, ...ended].map((d) => d.id))
  const graph: GraphElements = { nodes: [], edges: [] }
  for (const d of DECISIONS.filter((x) => visible.has(x.id))) {
    const status = ended.some((e) => e.id === d.id) ? 'superseded' : 'active'
    graph.nodes.push({
      id: `Decision:${d.id}`,
      label: 'Decision',
      title: d.title,
      props: { status },
    })
    for (const m of d.modules) {
      if (!graph.nodes.some((n) => n.id === `Module:${m}`)) {
        graph.nodes.push({ id: `Module:${m}`, label: 'Module', title: m, props: {} })
      }
      graph.edges.push({
        id: `${d.id}->${m}:AFFECTS`,
        source: `Decision:${d.id}`,
        target: `Module:${m}`,
        type: 'AFFECTS',
        props: {},
      })
    }
    if (d.supersedes && visible.has(d.supersedes)) {
      graph.edges.push({
        id: `${d.id}->${d.supersedes}:SUPERSEDES`,
        source: `Decision:${d.id}`,
        target: `Decision:${d.supersedes}`,
        type: 'SUPERSEDES',
        props: {},
      })
    }
  }
  return {
    as_of: date.length > 10 ? date : date + 'T00:00:00Z',
    active,
    ended,
    upcoming_count: upcoming,
    undated_count: 0,
    graph,
  }
}

/** Real output of GET /risk/modules on the seeded demo graph. */
/** Real output of GET /risk/modules on the seeded demo graph. */
export const DEMO_RISK: RiskReport = {
  "as_of": "2024-01-15T00:00:00Z",
  "as_of_source": "graph_latest",
  "window_days": 365,
  "modules": [
    {
      "module": "flask/app",
      "risk": "high",
      "risk_score": 76.0,
      "reasons": [
        "Only one active expert: davidism"
      ],
      "bus_factor": 1,
      "active_experts": 1,
      "experts": [
        {
          "login": "davidism",
          "score": 9.5,
          "share": 0.6551724137931034,
          "last_active": "2024-01-15",
          "active": true
        },
        {
          "login": "mitsuhiko",
          "score": 5.0,
          "share": 0.3448275862068966,
          "last_active": "2019-06-01",
          "active": false
        }
      ],
      "decisions_total": 2,
      "decisions_active": 2
    },
    {
      "module": "flask/compat",
      "risk": "high",
      "risk_score": 76.0,
      "reasons": [
        "Only one active expert: davidism"
      ],
      "bus_factor": 1,
      "active_experts": 1,
      "experts": [
        {
          "login": "davidism",
          "score": 7.2,
          "share": 0.6153846153846154,
          "last_active": "2023-09-01",
          "active": true
        },
        {
          "login": "untitaker",
          "score": 4.5,
          "share": 0.38461538461538464,
          "last_active": "2021-04-10",
          "active": false
        }
      ],
      "decisions_total": 2,
      "decisions_active": 1
    },
    {
      "module": "flask/views",
      "risk": "high",
      "risk_score": 69.0,
      "reasons": [
        "Only one active expert: pgjones"
      ],
      "bus_factor": 1,
      "active_experts": 1,
      "experts": [
        {
          "login": "pgjones",
          "score": 8.8,
          "share": 1.0,
          "last_active": "2023-11-20",
          "active": true
        }
      ],
      "decisions_total": 1,
      "decisions_active": 1
    }
  ]
}

export const DEMO_PR: PRGuardResponse = {
  pr: {
    owner: 'pallets',
    repo: 'flask',
    number: 0,
    title: 'Demo: re-add Python 3.6 compatibility helpers',
    state: 'open',
    author: 'example-contributor',
    url: 'https://github.com/pallets/flask',
    additions: 42,
    deletions: 3,
    changed_files: 1,
    files_checked: 1,
    truncated_files: false,
  },
  graph_repo: 'pallets/flask',
  repo_matches_graph: true,
  guard: { ...MOCK_GUARD_RESPONSE, judge: 'heuristic' },
  suggested_reviewers: ['davidism'],
}
