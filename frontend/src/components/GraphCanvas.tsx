import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import type { Core } from 'cytoscape'
import type { GraphElements } from '../types'

interface GraphCanvasProps {
  elements: GraphElements
  onNodeClick?: (nodeId: string) => void
  highlightedPath?: GraphElements | null
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  elements,
  onNodeClick,
  highlightedPath,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onNodeClickRef = useRef(onNodeClick)
  useEffect(() => {
    onNodeClickRef.current = onNodeClick
  }, [onNodeClick])

  useEffect(() => {
    if (!containerRef.current) return

    const cy = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            color: '#f1f5f9',
            'font-size': '11px',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'background-color': '#475569',
            width: 32,
            height: 32,
            'border-width': 2,
            'border-color': '#1e293b',
          },
        },
        // Decision node status colors
        {
          selector: 'node[type = "Decision"]',
          style: {
            'background-color': '#10b981', // active
            shape: 'round-rectangle',
            width: 38,
            height: 30,
          },
        },
        {
          selector: 'node[status = "superseded"]',
          style: {
            'background-color': '#f59e0b', // amber
          },
        },
        {
          selector: 'node[status = "reversed"]',
          style: {
            'background-color': '#ef4444', // red
          },
        },
        // Person
        {
          selector: 'node[type = "Person"]',
          style: {
            'background-color': '#3b82f6', // blue
            shape: 'ellipse',
          },
        },
        // Module
        {
          selector: 'node[type = "Module"]',
          style: {
            'background-color': '#64748b', // grey
            shape: 'hexagon',
          },
        },
        // Evidence (hollow circle)
        {
          selector: 'node[type = "Evidence"]',
          style: {
            'background-color': '#0f172a',
            'border-color': '#a855f7',
            'border-width': 3,
            shape: 'ellipse',
            width: 24,
            height: 24,
          },
        },
        // Edge styling
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': '9px',
            color: '#94a3b8',
            'text-rotation': 'autorotate',
            'text-background-opacity': 0.8,
            'text-background-color': '#0f172a',
            'text-background-padding': '2px',
          },
        },
        // Highlighted / Active Path edges
        {
          selector: 'edge.highlighted',
          style: {
            width: 3.5,
            'line-color': '#38bdf8',
            'target-arrow-color': '#38bdf8',
          },
        },
        {
          selector: 'node.highlighted',
          style: {
            'border-color': '#38bdf8',
            'border-width': 4,
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 500,
        nodeDimensionsIncludeLabels: true,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
    })

    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      onNodeClickRef.current?.(node.id())
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
    }
  }, [])

  // Sync elements into Cytoscape instance
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    cy.batch(() => {
      // Add or update nodes
      const existingNodeIds = new Set(cy.nodes().map((n) => n.id()))
      for (const node of elements.nodes) {
        const status = node.props?.status || 'active'
        const label = node.title || node.id
        if (!existingNodeIds.has(node.id)) {
          cy.add({
            group: 'nodes',
            data: {
              id: node.id,
              label,
              type: node.label,
              status,
            },
          })
        }
      }

      // Add or update edges
      const existingEdgeIds = new Set(cy.edges().map((e) => e.id()))
      for (const edge of elements.edges) {
        if (!existingEdgeIds.has(edge.id)) {
          // Check if both source and target exist
          if (cy.getElementById(edge.source).length > 0 && cy.getElementById(edge.target).length > 0) {
            cy.add({
              group: 'edges',
              data: {
                id: edge.id,
                source: edge.source,
                target: edge.target,
                label: edge.type,
              },
            })
          }
        }
      }

      // Highlight path if provided
      if (highlightedPath) {
        const pathNodeIds = new Set(highlightedPath.nodes.map((n) => n.id))
        const pathEdgeIds = new Set(highlightedPath.edges.map((e) => e.id))
        cy.nodes().forEach((n) => {
          if (pathNodeIds.has(n.id())) {
            n.addClass('highlighted')
          } else {
            n.removeClass('highlighted')
          }
        })
        cy.edges().forEach((e) => {
          if (pathEdgeIds.has(e.id())) {
            e.addClass('highlighted')
          } else {
            e.removeClass('highlighted')
          }
        })
      }
    })

    if (elements.nodes.length > 0) {
      cy.layout({
        name: 'cose',
        animate: true,
        animationDuration: 400,
        nodeDimensionsIncludeLabels: true,
      }).run()
      cy.fit(undefined, 40)
    }
  }, [elements, highlightedPath])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          backgroundColor: '#090d16',
        }}
      />
      {/* Canvas overlay legend */}
      <div
        style={{
          position: 'absolute',
          bottom: 12,
          left: 12,
          backgroundColor: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #1e293b',
          borderRadius: 8,
          padding: '8px 12px',
          fontSize: '11px',
          color: '#94a3b8',
          display: 'flex',
          gap: 12,
          alignItems: 'center',
          pointerEvents: 'none',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, backgroundColor: '#10b981', borderRadius: 2 }} />
          Active
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, backgroundColor: '#f59e0b', borderRadius: 2 }} />
          Superseded
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, backgroundColor: '#ef4444', borderRadius: 2 }} />
          Reversed
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, backgroundColor: '#3b82f6', borderRadius: '50%' }} />
          Person
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, border: '2px solid #a855f7', borderRadius: '50%' }} />
          Evidence
        </span>
      </div>
    </div>
  )
}
