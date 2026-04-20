import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ValidationResult } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    put: vi.fn(),
    patch: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { useGraphSync, serializeGraph } from '../useGraphSync'

const mockedPut = vi.mocked(api.put)
const mockedPatch = vi.mocked(api.patch)

/**
 * Build a Vue Flow-shaped graph (the format emitGraphChanged produces).
 */
const makeVueFlowGraph = (id = '1') => ({
  nodes: [{
    id,
    type: 'tool',
    position: { x: 10, y: 20 },
    data: {
      name: 'n',
      toolName: 't',
      parameters: {},
      enabled: true,
      collapsed: false,
      output_templates: {},
    },
  }],
  edges: [],
})

/**
 * The backend-format graph that the serializer should produce from makeVueFlowGraph.
 */
const expectedBackendGraph = (id = '1') => ({
  nodes: [{
    id,
    name: 'n',
    tool_name: 't',
    position: [10, 20],
    parameters: {},
    output_templates: {},
    enabled: true,
    collapsed: false,
  }],
  edges: [],
})

const makeValidation = (valid = true): ValidationResult => ({
  valid,
  node_statuses: {},
  errors: [],
})

describe('useGraphSync', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockedPut.mockReset()
    mockedPatch.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('debounces multiple rapid syncGraph calls into one PUT', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation() })
    const { syncGraph } = useGraphSync()

    syncGraph(makeVueFlowGraph('1'))
    syncGraph(makeVueFlowGraph('2'))
    syncGraph(makeVueFlowGraph('3'))

    expect(mockedPut).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(300)

    expect(mockedPut).toHaveBeenCalledTimes(1)
    // Should serialize the last graph to backend format
    expect(mockedPut).toHaveBeenCalledWith('/api/v1/graph', expectedBackendGraph('3'))
  })

  it('supersedes in-flight requests', async () => {
    let resolveFirst!: (v: unknown) => void
    let resolveSecond!: (v: unknown) => void

    mockedPut
      .mockReturnValueOnce(new Promise(r => { resolveFirst = r }))
      .mockReturnValueOnce(new Promise(r => { resolveSecond = r }))

    const { syncGraph, validationResult } = useGraphSync()

    // First call
    syncGraph(makeVueFlowGraph('1'))
    await vi.advanceTimersByTimeAsync(300)
    expect(mockedPut).toHaveBeenCalledTimes(1)

    // Second call while first is in-flight
    syncGraph(makeVueFlowGraph('2'))
    await vi.advanceTimersByTimeAsync(300)
    expect(mockedPut).toHaveBeenCalledTimes(2)

    // Resolve first request (stale)
    resolveFirst({ data: makeValidation(false) })
    await vi.advanceTimersByTimeAsync(0)
    // Stale result should be ignored
    expect(validationResult.value).toBeNull()

    // Resolve second request (current)
    resolveSecond({ data: makeValidation(true) })
    await vi.advanceTimersByTimeAsync(0)
    expect(validationResult.value).toEqual(makeValidation(true))
  })

  it('returns validation result', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation(true) })
    const { syncGraph, validationResult } = useGraphSync()

    syncGraph(makeVueFlowGraph())
    await vi.advanceTimersByTimeAsync(300)

    expect(validationResult.value).toEqual(makeValidation(true))
  })

  it('flushNow sends immediately', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation() })
    const { syncGraph, flushNow } = useGraphSync()

    syncGraph(makeVueFlowGraph())
    expect(mockedPut).not.toHaveBeenCalled()

    await flushNow()
    expect(mockedPut).toHaveBeenCalledTimes(1)
  })

  it('isPending is true while request is in-flight', async () => {
    let resolve!: (v: unknown) => void
    mockedPut.mockReturnValue(new Promise(r => { resolve = r }))

    const { syncGraph, isPending, flushNow } = useGraphSync()

    expect(isPending.value).toBe(false)

    syncGraph(makeVueFlowGraph())
    flushNow() // fire immediately, don't await

    await vi.advanceTimersByTimeAsync(0)
    expect(isPending.value).toBe(true)

    resolve({ data: makeValidation() })
    await vi.advanceTimersByTimeAsync(0)
    expect(isPending.value).toBe(false)
  })

  it('patchParameters uses PATCH endpoint', async () => {
    mockedPatch.mockResolvedValue({ data: {} })
    const { patchParameters } = useGraphSync()

    await patchParameters('node_1', { threshold: 0.5 })

    expect(mockedPatch).toHaveBeenCalledWith(
      '/api/v1/graph/nodes/node_1/parameters',
      { threshold: 0.5 },
    )
  })
})

describe('serializeGraph', () => {
  it('converts Vue Flow node position {x,y} to backend [x,y]', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'n1',
        position: { x: 100, y: 200 },
        data: {
          name: 'My Node',
          toolName: 'threshold',
          parameters: { level: 0.5 },
          enabled: true,
          collapsed: false,
          output_templates: { mask: '{input}_mask' },
        },
      }],
      edges: [],
    })
    expect(result.nodes).toEqual([{
      id: 'n1',
      name: 'My Node',
      tool_name: 'threshold',
      position: [100, 200],
      parameters: { level: 0.5 },
      output_templates: { mask: '{input}_mask' },
      enabled: true,
      collapsed: false,
    }])
  })

  it('serializes column_ref edges', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        sourceHandle: 'image',
        targetHandle: 'input_image',
        type: 'column_ref',
      }],
    })
    expect(result.edges).toEqual([{
      type: 'column_ref',
      id: 'e1',
      source_node: 'n1',
      target_node: 'n2',
      source_output: 'image',
      target_input: 'input_image',
    }])
  })

  it('serializes positional edges, extracting index from handle name', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [{
        id: 'e2',
        source: 'n1',
        target: 'n2',
        sourceHandle: 'output',
        targetHandle: '__positional_3',
        type: 'positional',
      }],
    })
    expect(result.edges).toEqual([{
      type: 'positional',
      id: 'e2',
      source_node: 'n1',
      target_node: 'n2',
      positional_index: 3,
    }])
  })

  it('defaults positional_index to 0 when handle has no valid index', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [{
        id: 'e3',
        source: 'n1',
        target: 'n2',
        sourceHandle: null,
        targetHandle: null,
        type: 'positional',
      }],
    })
    expect(result.edges[0]).toMatchObject({
      type: 'positional',
      positional_index: 0,
    })
  })
})
