import { describe, expect, it } from 'vitest'
import type { ToolMetadata } from '@/api/types'
import { emptyGraph } from '@/sessions/graphDocument'
import {
  normalizeClipboardPayload,
  prepareClipboardPaste,
  serializeGraphSelection,
} from '../clipboard'

const tool: ToolMetadata = {
  name: 'tool', display_name: 'Tool', package: 'pkg', package_version: '2',
  tool_type: 'ProcessingTool', accepts_upstream: true, dynamic_outputs: false,
  dataframe_output: true, source_kind: 'package', editable: false,
  documentation: '', tags: [], categories: [], environment: null,
  inputs: { sigma: { type: 'float', required: false, nullable: false, connectable: 'by_default', default: 1 } },
  outputs: { result: { type: 'float' } },
}

describe('recursive workflow clipboard', () => {
  it('copies and pastes a complete workflow node while changing only parent identities', () => {
    const child = emptyGraph('child', 'Child')
    child.nodes.push({
      type: 'tool', id: 'inner', name: 'Inner', tool_name: 'tool',
      position: [0, 0], parameters: { sigma: 2 }, enabled: true, collapsed: false,
    })
    const root = emptyGraph('root', 'Root')
    root.nodes.push({
      type: 'workflow', id: 'child-node', name: 'Child node', workflow: child,
      bindings: {}, source: null, position: [10, 20], enabled: true, collapsed: false,
    })

    const payload = serializeGraphSelection(
      root,
      new Set(['child-node']),
      () => tool,
      { sourceWorkflowId: 'root' },
    )
    const pasted = prepareClipboardPaste(payload, {
      existingIds: ['child-node'], existingNames: ['Child node'], getToolByName: () => tool,
    })

    expect(pasted.nodes[0].id).not.toBe('child-node')
    expect(pasted.nodes[0].type).toBe('workflow')
    if (pasted.nodes[0].type !== 'workflow') throw new Error('expected workflow node')
    expect(pasted.nodes[0].workflow).toEqual(child)
    expect(pasted.nodes[0].workflow.nodes[0].id).toBe('inner')
  })

  it('rejects records without the current strict discriminator envelope', () => {
    expect(() => normalizeClipboardPayload({ nodes: [], edges: [] })).toThrow()
    expect(() => normalizeClipboardPayload({
      bioimageflow_clipboard: true,
      clipboard_version: 2,
      created_at: new Date().toISOString(),
      nodes: [],
      edges: [],
    })).toThrow(/Unsupported/)
  })
})
