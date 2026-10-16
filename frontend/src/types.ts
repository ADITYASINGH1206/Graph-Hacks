/**
 * Shared types matching docs/API_CONTRACT.md
 */

export interface GraphNode {
  id: string
  label: string
  title: string
  props: Record<string, any>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  props: Record<string, any>
}

export interface GraphElements {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface Citation {
  n: number
  evidence_id: string
  quote: string
  url: string
  author: string
  ts: string
  decision_id: string | null
}

export interface Verification {
  valid: number
  invalid: number
  repaired: boolean
}

export interface HealthData {
  ok: boolean
  graph: string
  counts: {
    Decision: number
    Evidence: number
    Person: number
    Issue: number
    PullRequest: number
  }
  last_synced: string | null
  /** "live" = real model, "offline" = canned demo answers, "no_key" = /ask will fail. */
  llm_mode?: 'live' | 'offline' | 'no_key'
}

export interface DecisionTimelineItem {
  id: string
  title: string
  type: string
  status: string
  decided_at: string | null
  modules: string[]
  confidence: number
}

export interface DecisionDetail {
  decision: {
    id: string
    title: string
    summary: string
    type: string
    status: string
    decided_at: string
    valid_from: string
    valid_to: string | null
    confidence: number
    extracted_at: string
  }
  evidence: Citation[]
  people: Array<{
    login: string
    name: string
    avatar_url: string
    role: string
  }>
  lineage: GraphElements
  impact: {
    modules: string[]
    files: string[]
    downstream: Array<{ id: string; title: string; relation: string }>
    releases: string[]
  }
  stale: boolean
}

export interface GuardConflict {
  decision_id: string
  title: string
  status: string
  confidence: number
  why: string
  evidence: Citation[]
  people: string[]
}

export interface GuardAlignment {
  decision_id: string
  title: string
  why: string
}

export interface GuardResponse {
  conflicts: GuardConflict[]
  alignments: GuardAlignment[]
  reversed_before: GuardAlignment[]
  graph: GraphElements
  /** "llm" = model judged each pair, "heuristic" = built-in keyword rules (demo-tuned). */
  judge?: 'llm' | 'heuristic' | 'mixed'
}

// ---- Time Machine / risk / PR Guard (backend: dig/api/insights.py) ----

export interface TimelineEvent {
  date: string
  kind: 'decided' | 'ended'
  decision_id: string
  title: string
}

export interface TimelineRange {
  min_date: string | null
  max_date: string | null
  events: TimelineEvent[]
  undated_count: number
}

export interface SnapshotDecision {
  id: string
  title: string
  type: string
  summary: string
  status: string
  decided_at: string | null
  ended_at: string | null
  modules: string[]
}

export interface Snapshot {
  as_of: string
  active: SnapshotDecision[]
  ended: SnapshotDecision[]
  upcoming_count: number
  undated_count: number
  graph: GraphElements
}

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface ModuleExpert {
  login: string
  score: number
  share: number
  last_active: string | null
  active: boolean
}

export interface ModuleRisk {
  module: string
  risk: RiskLevel
  risk_score: number
  reasons: string[]
  bus_factor: number
  active_experts: number
  experts: ModuleExpert[]
  decisions_total: number
  decisions_active: number
}

export interface RiskReport {
  as_of: string
  as_of_source: 'graph_latest' | 'requested' | 'now'
  window_days: number
  modules: ModuleRisk[]
}

export interface PRInfo {
  owner: string
  repo: string
  number: number
  title: string
  state: string
  author: string
  url: string
  additions: number
  deletions: number
  changed_files: number
  files_checked: number
  truncated_files: boolean
}

export interface PRGuardResponse {
  pr: PRInfo
  graph_repo: string
  repo_matches_graph: boolean
  guard: GuardResponse
  suggested_reviewers: string[]
}
