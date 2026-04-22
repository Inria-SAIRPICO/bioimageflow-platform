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
    resources: {},
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
    expect(mockedPut).toHaveBeenCalledWith(
      '/api/v1/graph',
      expectedBackendGraph('3'),
      expect.objectContaining({ signal: expect.anything() }),
    )
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

  it('patchParameters sends {parameters} wrapper and tool_name query param', async () => {
    mockedPatch.mockResolvedValue({ data: { valid: true, node_statuses: {}, errors: [] } })
    const { patchParameters } = useGraphSync()

    await patchParameters('node_1', 'MyTool', { threshold: 0.5 })

    expect(mockedPatch).toHaveBeenCalledWith(
      '/api/v1/graph/nodes/node_1/parameters',
      { parameters: { threshold: 0.5 } },
      { params: { tool_name: 'MyTool' } },
    )
  })

  it('patchParameters merges single-node status without clobbering others', async () => {
    // Seed validationResult with two nodes via PUT first
    mockedPut.mockResolvedValue({
      data: {
        valid: true,
        node_statuses: {
          a: { node_id: 'a', status: 'unexecuted', cached: false },
          b: { node_id: 'b', status: 'unexecuted', cached: false },
        },
        errors: [],
      },
    })
    const { syncGraph, patchParameters, validationResult } = useGraphSync()
    syncGraph(makeVueFlowGraph('a'))
    await vi.advanceTimersByTimeAsync(300)

    mockedPatch.mockResolvedValue({
      data: {
        valid: true,
        node_statuses: {
          a: { node_id: 'a', status: 'out_of_date', cached: false },
        },
        errors: [],
      },
    })
    await patchParameters('a', 'MyTool', { x: 1 })

    // a updated, b preserved
    expect(validationResult.value?.node_statuses?.a.status).toBe('out_of_date')
    expect(validationResult.value?.node_statuses?.b.status).toBe('unexecuted')
  })

  it('syncState is "pending" while PUT in flight and "idle" on success', async () => {
    let resolve!: (v: unknown) => void
    mockedPut.mockReturnValue(new Promise(r => { resolve = r }))

    const { syncGraph, syncState, flushNow } = useGraphSync()
    expect(syncState.value).toBe('idle')

    syncGraph(makeVueFlowGraph())
    flushNow() // fire immediately
    await vi.advanceTimersByTimeAsync(0)
    expect(syncState.value).toBe('pending')

    resolve({ data: makeValidation() })
    await vi.advanceTimersByTimeAsync(0)
    expect(syncState.value).toBe('idle')
  })

  it('syncState transitions to "error" on PUT failure; validationResult is preserved', async () => {
    // First successful result
    mockedPut.mockResolvedValueOnce({ data: makeValidation(true) })
    const { syncGraph, flushNow, syncState, validationResult } = useGraphSync()
    syncGraph(makeVueFlowGraph())
    await vi.advanceTimersByTimeAsync(300)
    const previous = validationResult.value

    // Second call fails
    mockedPut.mockRejectedValueOnce({ message: 'network boom', response: { status: 500 } })
    syncGraph(makeVueFlowGraph('2'))
    await flushNow()

    expect(syncState.value).toBe('error')
    // Previous result is kept visible
    expect(validationResult.value).toEqual(previous)
  })

  it('errorStore.report is called on network failure', async () => {
    const report = vi.fn()
    mockedPut.mockRejectedValueOnce({ message: 'boom' })
    const { syncGraph, flushNow } = useGraphSync({ report })
    syncGraph(makeVueFlowGraph())
    await flushNow()
    expect(report).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'graph_sync_error' }),
    )
  })

  it('serializeNode round-trips the resources field', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'n1',
        position: { x: 0, y: 0 },
        data: {
          name: 'n', toolName: 't', parameters: {},
          resources: { cpu: 4, gpu: 1 },
        },
      }],
      edges: [],
    })
    expect(result.nodes[0].resources).toEqual({ cpu: 4, gpu: 1 })
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
      resources: {},
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
