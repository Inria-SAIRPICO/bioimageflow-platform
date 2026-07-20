import { describe, expect, it } from 'vitest'
import {
  decodeEndpointHandle,
  encodeEndpointHandle,
  type EndpointHandle,
} from '../endpointHandles'

describe('endpoint handle codec', () => {
  const endpoints: EndpointHandle[] = [
    { kind: 'dataframe-output' },
    { kind: 'dataframe-position', index: 2 },
    { kind: 'dataframe-input', name: 'left table' },
    { kind: 'tool-input', name: 'image/path' },
    { kind: 'tool-output', name: 'mask:final' },
    { kind: 'workflow-input', id: 'input-018f' },
    { kind: 'workflow-output', id: 'output-018f' },
  ]

  it.each(endpoints)('round-trips $kind', (endpoint) => {
    expect(decodeEndpointHandle(encodeEndpointHandle(endpoint))).toEqual(endpoint)
  })

  it('rejects untyped and malformed handles', () => {
    expect(() => decodeEndpointHandle('raw-field-name')).toThrow()
    expect(() => decodeEndpointHandle('bif:v1:dataframe-position:-1')).toThrow()
    expect(() => encodeEndpointHandle({ kind: 'workflow-input', id: '' })).toThrow()
  })
})
