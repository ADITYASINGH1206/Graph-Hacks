import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import cytoscape from 'cytoscape'
import type { Core, EventObject, StylesheetJson } from 'cytoscape'
import type { GraphElements } from '../types'

interface GraphCanvasProps {
  elements: GraphElements
  onNodeClick?: (nodeId: string) => void
  /** Edges and nodes of the agent's answer path. They light up one hop at a time. */
  highlightedPath?: GraphElements | null
  /** "accumulate" (default) only adds; "replace" makes the canvas show exactly `elements`. */
  mode?: 'accumulate' | 'replace'
  /** Shown over the canvas while there is nothing to draw. */
  empty?: ReactNode
  /** Dim the canvas and show a pulse while the agent is still working. */
  busy?: boolean
}

// Cytoscape cannot read CSS variables, so the paper palette is mirrored here.
const C = {
  ink: '#16130f',
  muted: '#5c554a',
  edge: '#b9ad97',
  paper: '#fffaf0',
  accent: '#a8552b',
  active: '#2f8f6b',
  superseded: '#d08a2e',
  reversed: '#c4473a',
  person: '#3b6fb6',
  module: '#8a7b66',
  evidence: '#7c4dbd',
}

const STYLE: StylesheetJson = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      color: C.ink,
      'font-family': 'Inter, system-ui, sans-serif',
      'font-size': 11,
      'font-weight': 500,
      'text-valign': 'bottom',
      'text-margin-y': 7,
      'text-wrap': 'ellipsis',
      'text-max-width': '120px',
      'text-background-color': C.paper,
      'text-background-opacity': 0.85,
      'text-background-padding': '2px',
      'text-background-shape': 'roundrectangle',
      'background-color': C.module,
      width: 30,
      height: 30,
      'border-width': 3,
      'border-color': C.paper,
      'overlay-opacity': 0,
      'transition-property': 'background-color, border-color, border-width, width, height',
      'transition-duration': 200,
    },
  },
  {
    selector: 'node[type = "Decision"]',
    style: { 'background-color': C.active, shape: 'round-rectangle', width: 44, height: 32 },
  },
  { selector: 'node[status = "superseded"]', style: { 'background-color': C.superseded } },
  { selector: 'node[status = "reversed"]', style: { 'background-color': C.reversed } },
  {
    selector: 'node[type = "Person"]',
    style: { 'background-color': C.person, shape: 'ellipse', width: 30, height: 30 },
  },
  {
    selector: 'node[type = "Module"]',
    style: { 'background-color': C.module, shape: 'hexagon', width: 34, height: 30 },
  },
  {
    selector: 'node[type = "Evidence"]',
    style: {
      'background-color': C.paper,
      'border-color': C.evidence,
      'border-width': 3,
      shape: 'ellipse',
      width: 22,
      height: 22,
    },
  },
  {
    selector: 'node[type = "PullRequest"], node[type = "Issue"]',
    style: { 'background-color': '#c9bea8', shape: 'round-diamond', width: 24, height: 24 },
  },
  {
    selector: 'edge',
    style: {
      width: 1.6,
      'line-color': C.edge,
      'target-arrow-color': C.edge,
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.9,
      'curve-style': 'bezier',
      label: 'data(label)',
      'font-family': 'JetBrains Mono, ui-monospace, monospace',
      'font-size': 8,
      color: C.muted,
      'text-rotation': 'autorotate',
      'text-background-opacity': 0.9,
      'text-background-color': C.paper,
      'text-background-padding': '2px',
      'text-background-shape': 'roundrectangle',
      'overlay-opacity': 0,
      'transition-property': 'line-color, target-arrow-color, width, opacity',
      'transition-duration': 250,
    },
  },
  { selector: 'edge[label = "SUPERSEDES"], edge[label = "REVERSES"]', style: { 'line-style': 'dashed' } },
  {
    selector: '.dim',
    style: { opacity: 0.28 },
  },
  {
    selector: 'edge.highlighted',
    style: { width: 3.2, 'line-color': C.accent, 'target-arrow-color': C.accent, opacity: 1 },
  },
  {
    selector: 'node.highlighted',
    style: { 'border-color': C.accent, 'border-width': 4, opacity: 1 },
  },
  { selector: 'node:selected', style: { 'border-color': C.ink, 'border-width': 4 } },
]

const PATH_STEP_MS = 280

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  elements,
  onNodeClick,
  highlightedPath,
  mode = 'accumulate',
  empty,
  busy = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const layoutRef = useRef<{ stop: () => unknown } | null>(null)
  const pathTimers = useRef<number[]>([])
  const onNodeClickRef = useRef(onNodeClick)
  const [tip, setTip] = useState<{ x: number; y: number; title: string; sub: string } | null>(null)

  useEffect(() => {
    onNodeClickRef.current = onNodeClick
  }, [onNodeClick])

  useEffect(() => {
    if (!containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      style: STYLE,
      maxZoom: 1.5,
      minZoom: 0.25,
      wheelSensitivity: 0.25,
    })

    cy.on('tap', 'node', (evt: EventObject) => onNodeClickRef.current?.(evt.target.id()))
    cy.on('mouseover', 'node', (evt: EventObject) => {
      const n = evt.target
      const pos = n.renderedPosition()
      const d = n.data()
      setTip({
        x: pos.x,
        y: pos.y,
        title: d.fullTitle || d.label,
        sub: [d.type, d.status && d.type === 'Decision' ? d.status : ''].filter(Boolean).join(' · '),
      })
      containerRef.current!.style.cursor = 'pointer'
    })
    cy.on('mouseout', 'node', () => {
      setTip(null)
      if (containerRef.current) containerRef.current.style.cursor = 'default'
    })
    cy.on('pan zoom drag', () => setTip(null))

    cyRef.current = cy
    return () => {
      // Stop layout and animations first, or they fire on a destroyed instance.
      layoutRef.current?.stop()
      layoutRef.current = null
      pathTimers.current.forEach((t) => window.clearTimeout(t))
      pathTimers.current = []
      cy.stop()
      cy.destroy()
      cyRef.current = null
    }
  }, [])

  // Sync elements into the Cytoscape instance
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    const added: string[] = []
    cy.batch(() => {
      if (mode === 'replace') {
        const keepNodes = new Set(elements.nodes.map((n) => n.id))
        const keepEdges = new Set(elements.edges.map((e) => e.id))
        cy.edges().forEach((e) => {
          if (!keepEdges.has(e.id())) e.remove()
        })
        cy.nodes().forEach((n) => {
          if (!keepNodes.has(n.id())) n.remove()
        })
      }
      const existing = new Set(cy.nodes().map((n) => n.id()))
      for (const node of elements.nodes) {
        const status = node.props?.status || 'active'
        const quote = node.label === 'Evidence' && typeof node.props?.quote === 'string' ? node.props.quote : ''
        const label = quote ? `“${quote.slice(0, 26)}${quote.length > 26 ? '…' : ''}”` : node.label === 'Evidence' ? 'Source quote' : node.title || node.id
        if (!existing.has(node.id)) {
          cy.add({
            group: 'nodes',
            data: { id: node.id, label, fullTitle: label, type: node.label, status },
          })
          added.push(node.id)
        } else {
          // Status can change between snapshots (active -> superseded).
          cy.getElementById(node.id).data('status', status)
        }
      }
      const existingEdges = new Set(cy.edges().map((e) => e.id()))
      for (const edge of elements.edges) {
        if (existingEdges.has(edge.id)) continue
        if (cy.getElementById(edge.source).length && cy.getElementById(edge.target).length) {
          cy.add({
            group: 'edges',
            data: { id: edge.id, source: edge.source, target: edge.target, label: edge.type },
          })
        }
      }
    })

    if (elements.nodes.length === 0) return

    // New nodes fade and grow in, so tool results visibly "arrive" on the canvas.
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (!reduce) {
      for (const id of added) {
        const n = cy.getElementById(id)
        n.style('opacity', 0)
        n.animate({ style: { opacity: 1 } }, { duration: 450, easing: 'ease-out' })
      }
    }

    layoutRef.current?.stop()
    // Replace mode redraws often (slider drags); animated layouts would run on removed nodes.
    const layout = cy.layout({
      name: 'cose',
      animate: mode !== 'replace' && !reduce,
      animationDuration: 500,
      nodeDimensionsIncludeLabels: true,
      nodeRepulsion: () => 14000,
      idealEdgeLength: () => 110,
      padding: 36,
      randomize: false,
    })
    layoutRef.current = layout
    layout.run()
    cy.fit(undefined, 48)
  }, [elements, mode])

  // Light up the answer path one hop at a time.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    pathTimers.current.forEach((t) => window.clearTimeout(t))
    pathTimers.current = []
    cy.elements().removeClass('highlighted dim')
    if (!highlightedPath || highlightedPath.nodes.length === 0) return

    const nodeIds = new Set(highlightedPath.nodes.map((n) => n.id))
    cy.elements().addClass('dim')

    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const steps: Array<() => void> = []
    // Order: each edge together with its endpoints, so the path visibly travels.
    const seenNodes = new Set<string>()
    const reveal = (id: string) => {
      const n = cy.getElementById(id)
      if (n.length) n.removeClass('dim').addClass('highlighted')
    }
    for (const e of highlightedPath.edges) {
      steps.push(() => {
        for (const id of [e.source, e.target]) reveal(id)
        const edge = cy.getElementById(e.id)
        if (edge.length) edge.removeClass('dim').addClass('highlighted')
      })
      seenNodes.add(e.source)
      seenNodes.add(e.target)
    }
    for (const id of nodeIds) if (!seenNodes.has(id)) steps.push(() => reveal(id))

    steps.forEach((step, i) => {
      if (reduce) step()
      else pathTimers.current.push(window.setTimeout(step, i * PATH_STEP_MS))
    })
  }, [highlightedPath])

  const zoomBy = (factor: number) => {
    const cy = cyRef.current
    if (!cy) return
    cy.animate({ zoom: Math.min(1.5, Math.max(0.25, cy.zoom() * factor)), duration: 180 })
  }
  const fit = () => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 48 }, duration: 250 })

  const nothing = elements.nodes.length === 0

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: 'var(--panel-2)' }}>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          backgroundImage: 'radial-gradient(circle, #d8cdb8 1px, transparent 1.2px)',
          backgroundSize: '22px 22px',
          opacity: busy && nothing ? 0.5 : 1,
          transition: 'opacity 0.3s',
        }}
      />

      {nothing && empty && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none' }}>
          {empty}
        </div>
      )}

      {tip && (
        <div
          style={{
            position: 'absolute',
            left: tip.x,
            top: tip.y - 44,
            transform: 'translateX(-50%)',
            background: C.ink,
            color: C.paper,
            padding: '5px 9px',
            borderRadius: 6,
            fontSize: 12,
            maxWidth: 240,
            pointerEvents: 'none',
            boxShadow: '0 6px 16px rgba(0,0,0,0.25)',
          }}
        >
          <div style={{ fontWeight: 600 }}>{tip.title}</div>
          {tip.sub && <div style={{ opacity: 0.7, fontSize: 10.5 }}>{tip.sub}</div>}
        </div>
      )}

      {!nothing && (
        <div style={{ position: 'absolute', top: 12, right: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {[
            ['+', () => zoomBy(1.3), 'Zoom in'],
            ['−', () => zoomBy(1 / 1.3), 'Zoom out'],
            ['⤢', fit, 'Fit to view'],
          ].map(([glyph, fn, label]) => (
            <button
              key={label as string}
              onClick={fn as () => void}
              aria-label={label as string}
              title={label as string}
              style={{
                width: 30,
                height: 30,
                border: '1px solid var(--line-2)',
                borderRadius: 8,
                background: 'var(--panel)',
                color: 'var(--text)',
                cursor: 'pointer',
                fontSize: 15,
                lineHeight: 1,
              }}
            >
              {glyph as string}
            </button>
          ))}
        </div>
      )}

      <Legend />
    </div>
  )
}

function Legend() {
  const dot = (bg: string, extra?: React.CSSProperties): React.CSSProperties => ({
    width: 10,
    height: 10,
    background: bg,
    borderRadius: 3,
    display: 'inline-block',
    ...extra,
  })
  const item = (swatch: React.CSSProperties, text: string) => (
    <span key={text} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={swatch} />
      {text}
    </span>
  )
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 12,
        left: 12,
        background: 'rgba(251, 247, 239, 0.92)',
        backdropFilter: 'blur(6px)',
        border: '1px solid var(--line)',
        borderRadius: 8,
        padding: '6px 10px',
        fontSize: 11,
        color: 'var(--muted)',
        display: 'flex',
        gap: 12,
        flexWrap: 'wrap',
        pointerEvents: 'none',
      }}
    >
      {item(dot(C.active), 'Active')}
      {item(dot(C.superseded), 'Superseded')}
      {item(dot(C.reversed), 'Reversed')}
      {item(dot(C.person, { borderRadius: '50%' }), 'Person')}
      {item(dot(C.paper, { border: `2px solid ${C.evidence}`, borderRadius: '50%', width: 9, height: 9 }), 'Evidence')}
      {item(dot(C.module, { borderRadius: 2 }), 'Module')}
    </div>
  )
}
