import { describe, expect, it } from 'vitest'
import type { GraphState, WorkflowInput, WorkflowOutput } from '@/api/types'
import {
  changedNestedWorkflowPortIds,
  enclosingWorkflowInterfaceEffects,
  parentGraphReflectsNestedWorkflowEffects,
  reconcileEnclosingWorkflowInterface,
} from '../nestedWorkflowInterfaceReconciliation'
import type { NestedWorkflowApplyEffects } from '../nestedWorkflowApplyCoordinator'

const childInput: WorkflowInput = {
  id: 'child-input', name: 'Child input', kind: 'field', default: null,
  schema: { type: 'object', properties: { alpha: { type: 'string' }, beta: { type: 'number' } } },
  targets: [{ node: 'tool', port: { kind: 'field', name: 'value' } }],
}
const childOutput: WorkflowOutput = {
  id: 'child-output', name: 'Child output', schema: { type: 'string' },
  source: { node: 'tool', column: 'value' },
}

describe('nested workflow interface reconciliation', () => {
  it('treats schema key reordering as compatible', () => {
    const reordered = {
      ...childInput,
      schema: { properties: { beta: { type: 'number' }, alpha: { type: 'string' } }, type: 'object' },
    }
    expect(changedNestedWorkflowPortIds(
      [childInput], [childOutput], [reordered], [{ ...childOutput, schema: { type: 'string' } }],
    )).toEqual({ inputIds: [], outputIds: [] })
  })

  it('removes only the affected forwarded target and removes a forwarded output', () => {
    const enclosingInputs: WorkflowInput[] = [{
      id: 'forwarded-input', name: 'Forwarded input', kind: 'field', default: null,
      schema: { type: 'string' },
      targets: [
        { node: 'child', port: { kind: 'workflow', id: 'child-input' } },
        { node: 'sibling', port: { kind: 'field', name: 'value' } },
      ],
    }]
    const enclosingOutputs: WorkflowOutput[] = [{
      id: 'forwarded-output', name: 'Forwarded output', schema: { type: 'string' },
      source: { node: 'child', column: 'child-output' },
    }]
    expect(enclosingWorkflowInterfaceEffects(
      enclosingInputs, enclosingOutputs, 'child', ['child-input'], ['child-output'],
    )).toEqual({
      enclosingInputIds: ['forwarded-input'],
      enclosingOutputIds: ['forwarded-output'],
    })
    const effects: NestedWorkflowApplyEffects = {
      inputIds: ['child-input'], outputIds: ['child-output'], edgeIds: [], bindingIds: [],
      enclosingInputIds: ['forwarded-input'], enclosingOutputIds: ['forwarded-output'],
    }
    expect(reconcileEnclosingWorkflowInterface(
      enclosingInputs, enclosingOutputs, 'child', effects,
    )).toEqual({
      inputs: [{
        ...enclosingInputs[0],
        targets: [{ node: 'sibling', port: { kind: 'field', name: 'value' } }],
      }],
      outputs: [],
    })
  })

  it('permits unrelated parent edits only while all removed-port references stay absent', () => {
    const child: GraphState['nodes'][number] = {
      type: 'workflow' as const, id: 'child', name: 'Child', position: [0, 0] as [number, number],
      workflow: {
        schema_version: 1, name: 'child', display_name: 'Child', nodes: [], edges: [],
        interface: { inputs: [], outputs: [] },
        config: { engine: 'wetlands', execution: 'parallel' },
      },
      bindings: {}, enabled: true, collapsed: false,
    }
    const unrelated: GraphState['nodes'][number] = {
      type: 'tool' as const, id: 'sibling', name: 'Edited sibling', tool_name: 'Tool',
      position: [1, 1] as [number, number], parameters: { value: 'preserved' },
      enabled: true, collapsed: false,
    }
    const graph: GraphState = {
      schema_version: 1, name: 'parent', display_name: 'Parent', nodes: [child, unrelated], edges: [],
      interface: { inputs: [], outputs: [] },
      config: { engine: 'wetlands', execution: 'parallel' },
    }
    const effects: NestedWorkflowApplyEffects = {
      inputIds: ['removed-input'], outputIds: ['removed-output'], edgeIds: ['old-edge'],
      bindingIds: ['removed-input'], enclosingInputIds: [], enclosingOutputIds: [],
    }
    expect(parentGraphReflectsNestedWorkflowEffects(graph, 'child', effects)).toBe(true)
    expect(parentGraphReflectsNestedWorkflowEffects({
      ...graph,
      edges: [{
        type: 'column', id: 'new-reference', source_node: 'sibling', source_output: 'value',
        target_node: 'child', target_input: 'removed-input',
      }],
    }, 'child', effects)).toBe(false)
    expect(parentGraphReflectsNestedWorkflowEffects({
      ...graph,
      interface: { ...graph.interface, outputs: [{
        id: 'new-forward', name: 'New forward', schema: { type: 'string' },
        source: { node: 'child', column: 'removed-output' },
      }] },
    }, 'child', effects)).toBe(false)
  })
})
