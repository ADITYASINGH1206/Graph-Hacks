import type { DecisionDetail } from '../types'

type Raw = Record<string, any>

/**
 * GET /decisions/{id} returns `impact` as {decision_id, affected: [{label, name}], downstream,
 * releases}, while the UI works with {modules, files, downstream, releases}. This maps one to
 * the other and fills every missing field, so a sparse response can never crash the page.
 */
export function normalizeDetail(raw: Raw): DecisionDetail {
  const d: Raw = raw?.decision ?? {}
  const impact: Raw = raw?.impact ?? {}
  const affected: Raw[] = Array.isArray(impact.affected) ? impact.affected : []
  const names = (label: string) =>
    affected
      .filter((a) => a?.label === label)
      .map((a) => String(a.name ?? a.path ?? ''))
      .filter(Boolean)

  const strings = (v: unknown): string[] => (Array.isArray(v) ? v.map(String) : [])

  return {
    decision: {
      id: String(d.id ?? ''),
      title: String(d.title ?? d.id ?? 'Untitled decision'),
      summary: String(d.summary ?? ''),
      type: String(d.type ?? ''),
      status: String(d.status ?? 'active'),
      decided_at: String(d.decided_at ?? ''),
      valid_from: String(d.valid_from ?? ''),
      valid_to: d.valid_to ? String(d.valid_to) : null,
      confidence: typeof d.confidence === 'number' ? d.confidence : 1,
      extracted_at: String(d.extracted_at ?? ''),
    },
    evidence: Array.isArray(raw?.evidence) ? raw.evidence : [],
    people: Array.isArray(raw?.people) ? raw.people : [],
    lineage: { nodes: raw?.lineage?.nodes ?? [], edges: raw?.lineage?.edges ?? [] },
    impact: {
      modules: strings(impact.modules).length ? strings(impact.modules) : names('Module'),
      files: strings(impact.files).length ? strings(impact.files) : names('File'),
      downstream: Array.isArray(impact.downstream) ? impact.downstream : [],
      releases: strings(impact.releases),
    },
    stale: Boolean(raw?.stale),
  }
}
