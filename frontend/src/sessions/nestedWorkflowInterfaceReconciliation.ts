import type { WorkflowInput, WorkflowOutput } from '@/api/types'
import { jsonDocumentsEqual } from './graphDocument'
import type { NestedWorkflowApplyEffects } from './nestedWorkflowApplyCoordinator'

export function changedNestedWorkflowPortIds(
  previousInputs: WorkflowInput[],
  previousOutputs: WorkflowOutput[],
  nextInputs: WorkflowInput[],
  nextOutputs: WorkflowOutput[],
): Pick<NestedWorkflowApplyEffects, 'inputIds' | 'outputIds'> {
  const nextInputById = new Map(nextInputs.map(input => [input.id, input]))
  const nextOutputById = new Map(nextOutputs.map(output => [output.id, output]))
  return {
    inputIds: previousInputs.filter((input) => {
      const next = nextInputById.get(input.id)
      return next === undefined
        || input.kind !== next.kind
        || !jsonDocumentsEqual(input.schema, next.schema)
    }).map(input => input.id).sort(),
    outputIds: previousOutputs.filter((output) => {
      const next = nextOutputById.get(output.id)
      return next === undefined || !jsonDocumentsEqual(output.schema, next.schema)
    }).map(output => output.id).sort(),
  }
}

export function enclosingWorkflowInterfaceEffects(
  inputs: WorkflowInput[],
  outputs: WorkflowOutput[],
  parentNodeId: string,
  removedInputIds: string[],
  removedOutputIds: string[],
): Pick<NestedWorkflowApplyEffects, 'enclosingInputIds' | 'enclosingOutputIds'> {
  const inputIds = new Set(removedInputIds)
  const outputIds = new Set(removedOutputIds)
  return {
    enclosingInputIds: inputs.filter(input => input.targets.some(target => (
      target.node === parentNodeId
      && target.port.kind === 'workflow'
      && inputIds.has(target.port.id)
    ))).map(input => input.id).sort(),
    enclosingOutputIds: outputs.filter(output => (
      output.source.node === parentNodeId && outputIds.has(output.source.column)
    )).map(output => output.id).sort(),
  }
}

export function reconcileEnclosingWorkflowInterface(
  inputs: WorkflowInput[],
  outputs: WorkflowOutput[],
  parentNodeId: string,
  effects: NestedWorkflowApplyEffects,
): { inputs: WorkflowInput[]; outputs: WorkflowOutput[] } {
  const removedInputIds = new Set(effects.inputIds)
  const removedOutputIds = new Set(effects.enclosingOutputIds)
  return {
    inputs: inputs.flatMap((input) => {
      const targets = input.targets.filter(target => !(
        target.node === parentNodeId
        && target.port.kind === 'workflow'
        && removedInputIds.has(target.port.id)
      ))
      return targets.length === 0 ? [] : [{ ...input, targets }]
    }),
    outputs: outputs.filter(output => !removedOutputIds.has(output.id)),
  }
}
