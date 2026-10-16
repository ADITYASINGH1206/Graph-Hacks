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
}
