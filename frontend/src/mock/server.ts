/**
 * Mock data and canned SSE streaming replays for offline/mock testing.
 */

import type { DecisionDetail, DecisionTimelineItem, GuardResponse, HealthData } from '../types'

export const MOCK_HEALTH: HealthData = {
  ok: true,
  graph: 'dig_pallets_flask',
  counts: {
    Decision: 3,
    Evidence: 3,
    Person: 4,
    Issue: 32,
    PullRequest: 48,
  },
  last_synced: '2026-10-16T12:00:00Z',
}

export const MOCK_DECISIONS: DecisionTimelineItem[] = [
  {
    id: 'dec_drop_py36',
    title: 'Drop Python 3.6 support',
    type: 'deprecation',
    status: 'active',
    decided_at: '2022-03-20T16:00:00Z',
    modules: ['flask/compat', 'flask/app'],
    confidence: 0.98,
  },
  {
    id: 'dec_drop_py2',
    title: 'Drop Python 2 support',
    type: 'deprecation',
    status: 'superseded',
    decided_at: '2018-04-01T12:00:00Z',
    modules: ['flask/compat'],
    confidence: 0.95,
  },
  {
    id: 'dec_app_ctx',
    title: 'Introduce explicit application context globals',
    type: 'architectural',
    status: 'active',
    decided_at: '2012-06-15T18:00:00Z',
    modules: ['flask/ctx', 'flask/globals'],
    confidence: 0.92,
  },
]

export const MOCK_DECISION_DETAIL: DecisionDetail = {
  decision: {
    id: 'dec_drop_py36',
    title: 'Drop Python 3.6 support',
    summary: 'Dropped Python 3.6 and 3.7 support, requiring Python 3.8+.',
    type: 'deprecation',
    status: 'active',
    decided_at: '2022-03-20T16:00:00Z',
    valid_from: '2022-03-20T16:00:00Z',
    valid_to: null,
    confidence: 0.98,
    extracted_at: '2026-10-16T00:00:00Z',
  },
  evidence: [
    {
      n: 1,
      evidence_id: 'ev_drop_py36',
      quote: 'Python 3.6 and 3.7 are now EOL, bump minimum Python version to 3.8.',
      url: 'https://github.com/pallets/flask/pull/4400',
      author: 'davidism',
      ts: '2022-03-15T09:00:00Z',
      decision_id: 'dec_drop_py36',
    },
  ],
  people: [
    {
      login: 'davidism',
      name: 'David Lord',
      avatar_url: 'https://avatars.githubusercontent.com/u/12428',
      role: 'maintainer',
    },
  ],
  lineage: {
    nodes: [
      {
        id: 'Decision:dec_drop_py36',
        label: 'Decision',
        title: 'Drop Python 3.6 support',
        props: { status: 'active', decided_at: '2022-03-20' },
      },
      {
        id: 'Decision:dec_drop_py2',
        label: 'Decision',
        title: 'Drop Python 2 support',
        props: { status: 'superseded', decided_at: '2018-04-01' },
      },
    ],
    edges: [
      {
        id: 'dec_drop_py36->dec_drop_py2:SUPERSEDES',
        source: 'Decision:dec_drop_py36',
        target: 'Decision:dec_drop_py2',
        type: 'SUPERSEDES',
        props: {},
      },
    ],
  },
  impact: {
    modules: ['flask/compat', 'flask/app'],
    files: ['src/flask/compat.py', 'pyproject.toml'],
    downstream: [],
    releases: ['2.2.0'],
  },
  stale: false,
}

export const MOCK_GUARD_RESPONSE: GuardResponse = {
  conflicts: [
    {
      decision_id: 'dec_drop_py36',
      title: 'Drop Python 3.6 support',
      status: 'active',
      confidence: 0.95,
      why: 'Proposal re-introduces compatibility helpers for Python 3.6 which were explicitly dropped in PR #4400.',
      evidence: [
        {
          n: 1,
          evidence_id: 'ev_drop_py36',
          quote: 'Python 3.6 and 3.7 are now EOL, bump minimum Python version to 3.8.',
          url: 'https://github.com/pallets/flask/pull/4400',
          author: 'davidism',
          ts: '2022-03-15T09:00:00Z',
          decision_id: 'dec_drop_py36',
        },
      ],
      people: ['davidism'],
    },
  ],
  alignments: [
    {
      decision_id: 'dec_app_ctx',
      title: 'Introduce explicit application context globals',
      why: 'Cleanly uses g and current_app conforming to context design.',
    },
  ],
  reversed_before: [],
  graph: {
    nodes: [],
    edges: [],
  },
}

export async function* replayMockAskStream(): AsyncGenerator<{ event: string; data: any }> {
  // Step 1: Tool call
  yield {
    event: 'tool_call',
    data: {
      id: 'call_1',
      name: 'search_decisions',
      input: { query: 'Python 3.6' },
    },
  }
  await new Promise((r) => setTimeout(r, 400))

  // Step 2: Tool result with graph elements
  yield {
    event: 'tool_result',
    data: {
      id: 'call_1',
      name: 'search_decisions',
      summary: "Found 1 active decision 'Drop Python 3.6 support'.",
      graph_elements: {
        nodes: [
          {
            id: 'Decision:dec_drop_py36',
            label: 'Decision',
            title: 'Drop Python 3.6 support',
            props: { status: 'active', type: 'deprecation' },
          },
        ],
        edges: [],
      },
    },
  }
  await new Promise((r) => setTimeout(r, 400))

  // Step 3: Tool call trace_to_source
  yield {
    event: 'tool_call',
    data: {
      id: 'call_2',
      name: 'trace_to_source',
      input: { decision_id: 'dec_drop_py36' },
    },
  }
  await new Promise((r) => setTimeout(r, 400))

  // Step 4: Tool result trace_to_source
  yield {
    event: 'tool_result',
    data: {
      id: 'call_2',
      name: 'trace_to_source',
      summary: 'Traced 1 evidence quotes in PR #4400 by davidism.',
      graph_elements: {
        nodes: [
          {
            id: 'Evidence:ev_drop_py36',
            label: 'Evidence',
            title: 'Evidence:ev_drop_py36',
            props: {},
          },
          {
            id: 'Person:davidism',
            label: 'Person',
            title: 'davidism',
            props: { login: 'davidism' },
          },
        ],
        edges: [
          {
            id: 'dec_drop_py36->ev_drop_py36:SUPPORTED_BY',
            source: 'Decision:dec_drop_py36',
            target: 'Evidence:ev_drop_py36',
            type: 'SUPPORTED_BY',
            props: {},
          },
          {
            id: 'davidism->dec_drop_py36:MADE',
            source: 'Person:davidism',
            target: 'Decision:dec_drop_py36',
            type: 'MADE',
            props: {},
          },
        ],
      },
    },
  }
  await new Promise((r) => setTimeout(r, 300))

  // Step 5: Token stream
  const fullText =
    'Python 3.6 and 3.7 support was officially dropped in March 2022 because both versions reached upstream end-of-life [1]. The change was authored by @davidism and merged in PR #4400, bumping Flask requirement to Python 3.8+.'
  for (const word of fullText.split(' ')) {
    yield {
      event: 'token',
      data: { text: word + ' ' },
    }
    await new Promise((r) => setTimeout(r, 40))
  }

  // Step 6: Final Answer event
  yield {
    event: 'answer',
    data: {
      markdown: fullText,
      citations: [
        {
          n: 1,
          evidence_id: 'ev_drop_py36',
          quote: 'Python 3.6 and 3.7 are now EOL, bump minimum Python version to 3.8.',
          url: 'https://github.com/pallets/flask/pull/4400',
          author: 'davidism',
          ts: '2022-03-15T09:00:00Z',
          decision_id: 'dec_drop_py36',
        },
      ],
      path: {
        nodes: [
          {
            id: 'Decision:dec_drop_py36',
            label: 'Decision',
            title: 'Drop Python 3.6 support',
            props: { status: 'active' },
          },
          {
            id: 'Evidence:ev_drop_py36',
            label: 'Evidence',
            title: 'Evidence:ev_drop_py36',
            props: {},
          },
          {
            id: 'Person:davidism',
            label: 'Person',
            title: 'davidism',
            props: {},
          },
        ],
        edges: [
          {
            id: 'dec_drop_py36->ev_drop_py36:SUPPORTED_BY',
            source: 'Decision:dec_drop_py36',
            target: 'Evidence:ev_drop_py36',
            type: 'SUPPORTED_BY',
            props: {},
          },
          {
            id: 'davidism->dec_drop_py36:MADE',
            source: 'Person:davidism',
            target: 'Decision:dec_drop_py36',
            type: 'MADE',
            props: {},
          },
        ],
      },
      verification: {
        valid: 1,
        invalid: 0,
        repaired: false,
      },
    },
  }

  // Step 7: Done
  yield {
    event: 'done',
    data: {
      session_id: 'sess_mock_123',
      tool_rounds: 2,
    },
  }
}
