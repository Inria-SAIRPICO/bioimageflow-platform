import type { WorkflowInput } from '@/api/types'
import { decodeEndpointHandle } from './endpointHandles'

export function dataframePositions(
  nodeId: string,
  connectedInputs: Record<string, string>,
  inputs: WorkflowInput[],
): number[] {
  const positions = new Set<number>()
  for (const handle of Object.keys(connectedInputs)) {
    try {
      const endpoint = decodeEndpointHandle(handle)
      if (endpoint.kind === 'dataframe-position') positions.add(endpoint.index)
    } catch { /* Ignore unresolved handles while tool metadata is loading. */ }
  }
  for (const input of inputs) {
    for (const target of input.targets) {
      if (target.node === nodeId && target.port.kind === 'positional') {
        positions.add(target.port.index)
      }
    }
  }
  return [...positions].sort((a, b) => a - b)
}

export function isPublishedDataframe(nodeId: string, handle: string, inputs: WorkflowInput[]): boolean {
  const endpoint = decodeEndpointHandle(handle)
  return inputs.some(input => input.kind === 'dataframe' && input.targets.some(target => (
    target.node === nodeId && (
      (target.port.kind === 'positional' && endpoint.kind === 'dataframe-position' && target.port.index === endpoint.index)
      || (target.port.kind === 'workflow' && endpoint.kind === 'workflow-input' && target.port.id === endpoint.id)
    )
  )))
}

export function nextDataframePosition(positions: number[]): number {
  let index = 0
  while (positions.includes(index)) index++
  return index
}
