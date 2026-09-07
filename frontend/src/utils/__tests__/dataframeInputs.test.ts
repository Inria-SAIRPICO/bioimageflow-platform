import { describe, expect, it } from 'vitest'
import type { WorkflowInput } from '@/api/types'
import { dataframePositions, isPublishedDataframe, nextDataframePosition } from '../dataframeInputs'
import { encodeEndpointHandle } from '../endpointHandles'

const inputs: WorkflowInput[] = [{
  id: 'public-table', name: 'Table', kind: 'dataframe', schema: { type: 'DataFrame' },
  targets: [
    { node: 'tool', port: { kind: 'positional', index: 1 } },
    { node: 'child', port: { kind: 'workflow', id: 'child-table' } },
  ],
}]

describe('DataFrame publication slots', () => {
  it('counts both connections and publications without reserving other nodes or fields', () => {
    const connected = {
      [encodeEndpointHandle({ kind: 'dataframe-position', index: 0 })]: 'Source',
      [encodeEndpointHandle({ kind: 'tool-input', name: 'parameter' })]: 'Value',
    }
    expect(dataframePositions('tool', connected, inputs)).toEqual([0, 1])
    expect(nextDataframePosition(dataframePositions('tool', connected, inputs))).toBe(2)
    expect(dataframePositions('other', {}, inputs)).toEqual([])
    expect(nextDataframePosition([0, 2])).toBe(1)
  })

  it('recognizes positional and forwarded child publications, not ordinary fields', () => {
    expect(isPublishedDataframe('tool', encodeEndpointHandle({ kind: 'dataframe-position', index: 1 }), inputs)).toBe(true)
    expect(isPublishedDataframe('tool', encodeEndpointHandle({ kind: 'dataframe-position', index: 0 }), inputs)).toBe(false)
    expect(isPublishedDataframe('child', encodeEndpointHandle({ kind: 'workflow-input', id: 'child-table' }), inputs)).toBe(true)
    expect(isPublishedDataframe('tool', encodeEndpointHandle({ kind: 'tool-input', name: 'number' }), inputs)).toBe(false)
  })
})
