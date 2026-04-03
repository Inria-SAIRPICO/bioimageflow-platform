import { describe, it, expect } from 'vitest'
import type { ClipboardNode, ClipboardEdge } from '../clipboard'
import { serializeSelection, deserializeSelection } from '../clipboard'

const makeNode = (id: string, x = 0, y = 0): ClipboardNode => ({
  id,
  name: `Node ${id}`,
  tool_name: `tool_${id}`,
  position: [x, y],
  parameters: { a: 1 },
})

const makeEdge = (id: string, source: string, target: string): ClipboardEdge => ({
  id,
  source_node: source,
  target_node: target,
  source_output: 'output',
  target_input: 'input',
})

describe('serializeSelection', () => {
  it('serializes only selected nodes', () => {
    const nodes = [makeNode('a'), makeNode('b'), makeNode('c')]
    const edges: ClipboardEdge[] = []
    const selected = new Set(['a', 'c'])

    const result = serializeSelection(nodes, edges, selected)

    expect(result.nodes).toHaveLength(2)
    expect(result.nodes.map(n => n.id)).toEqual(['a', 'c'])
  })

  it('excludes edges where one endpoint is outside the selection', () => {
    const nodes = [makeNode('a'), makeNode('b'), makeNode('c')]
    const edges = [
      makeEdge('e1', 'a', 'b'), // a selected, b not -> excluded
      makeEdge('e2', 'a', 'c'), // both selected -> included
    ]
    const selected = new Set(['a', 'c'])

    const result = serializeSelection(nodes, edges, selected)

    expect(result.edges).toHaveLength(1)
    expect(result.edges[0].id).toBe('e2')
  })
})

describe('deserializeSelection', () => {
  it('generates new unique IDs for nodes', () => {
    const clipboard = {
      nodes: [makeNode('a', 10, 20), makeNode('b', 30, 40)],
      edges: [],
    }

    const result = deserializeSelection(clipboard, ['existing_1'], [])

    // New IDs should not be the original
    expect(result.nodes[0].id).not.toBe('a')
    expect(result.nodes[1].id).not.toBe('b')
    // Should be unique
    expect(result.nodes[0].id).not.toBe(result.nodes[1].id)
  })

  it('remaps edge references to new node IDs', () => {
    const clipboard = {
      nodes: [makeNode('a'), makeNode('b')],
      edges: [makeEdge('e1', 'a', 'b')],
    }

    const result = deserializeSelection(clipboard, [], [])

    const newIds = new Set(result.nodes.map(n => n.id))
    expect(newIds.has(result.edges[0].source_node)).toBe(true)
    expect(newIds.has(result.edges[0].target_node)).toBe(true)
    expect(result.edges[0].source_node).not.toBe('a')
    expect(result.edges[0].target_node).not.toBe('b')
  })

  it('offsets positions by PASTE_OFFSET (50px)', () => {
    const clipboard = {
      nodes: [makeNode('a', 100, 200)],
      edges: [],
    }

    const result = deserializeSelection(clipboard, [], [])

    expect(result.nodes[0].position).toEqual([150, 250])
  })

  it('generates new edge IDs', () => {
    const clipboard = {
      nodes: [makeNode('a'), makeNode('b')],
      edges: [makeEdge('e1', 'a', 'b')],
    }

    const result = deserializeSelection(clipboard, [], [])

    expect(result.edges[0].id).not.toBe('e1')
  })

  it('generates new unique names', () => {
    const clipboard = {
      nodes: [makeNode('a')],
      edges: [],
    }

    const result = deserializeSelection(clipboard, [], ['Node a 1'])

    expect(result.nodes[0].name).not.toBe('Node a')
    // Should have a numeric suffix
    expect(result.nodes[0].name).toMatch(/.+ \d+$/)
  })
})
