import { describe, expect, it } from 'vitest'
import type { WorkflowInput, WorkflowOutput } from '@/api/types'
import {
  changedNestedWorkflowPortIds,
  enclosingWorkflowInterfaceEffects,
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
})
