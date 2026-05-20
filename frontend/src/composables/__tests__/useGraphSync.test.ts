import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ValidationResult } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    put: vi.fn(),
    patch: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { useGraphSync, serializeGraph, _resetGraphSyncForTest } from '../useGraphSync'

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
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockedPut.mockReset()
    mockedPatch.mockReset()
    _resetGraphSyncForTest()
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
      { graph: expectedBackendGraph('3'), workflow_name: null },
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

  it('reports a graph_sync_error to the canonical error store on network failure', async () => {
    const { setActivePinia, createPinia } = await import('pinia')
    setActivePinia(createPinia())
    const errorsModule = await import('@/stores/errors')
    const errorStore = errorsModule.useErrorStore()
    mockedPut.mockRejectedValueOnce({
      message: 'boom',
      response: { status: 500 },
    })
    const { syncGraph, flushNow } = useGraphSync()
    syncGraph(makeVueFlowGraph())
    await flushNow()
    expect(errorStore.errors).toHaveLength(1)
    expect(errorStore.errors[0]!.kind).toBe('graph_sync_error')
    expect(errorStore.errors[0]!.status).toBe(500)
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

  it('serializeNode preserves optional sub-workflow fields for v2 compatibility', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'outer',
        position: { x: 0, y: 0 },
        data: {
          name: 'Outer',
          toolName: '__sub_workflow__',
          parameters: { exposed: 1 },
          sub_workflow: {
            nodes: [{
              id: 'inner',
              name: 'Inner',
              tool_name: 'tool_a',
              position: [0, 0],
              parameters: {},
            }],
            edges: [],
          },
          published_inputs: [{
            name: 'exposed',
            internal_node_id: 'inner',
            internal_field: 'a',
            kind: 'parameter',
          }],
          published_outputs: [{
            name: 'result',
            internal_node_id: 'inner',
            internal_output: 'out',
          }],
          sub_workflow_readonly_reason: null,
        },
      }],
      edges: [],
    })

    expect((result.nodes[0] as any).sub_workflow.nodes[0].id).toBe('inner')
    expect((result.nodes[0] as any).published_inputs[0].name).toBe('exposed')
    expect((result.nodes[0] as any).published_outputs[0].name).toBe('result')
  })

  it('serializeGraph preserves root workflow published interface fields', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [],
      published_inputs: [{
        name: 'input_image',
        internal_node_id: 'load_image',
        internal_field: 'image',
        kind: 'input',
        schema: { type: 'ImageFile', connectable: 'by_default' },
        default: null,
      }],
      published_outputs: [{
        name: 'mask',
        internal_node_id: 'segment',
        internal_output: 'mask',
        schema: { type: 'MaskPath' },
      }],
    } as any)

    expect((result as any).published_inputs).toEqual([expect.objectContaining({
      name: 'input_image',
      internal_node_id: 'load_image',
    })])
    expect((result as any).published_outputs).toEqual([expect.objectContaining({
      name: 'mask',
      internal_node_id: 'segment',
    })])
  })

  it('does not emit empty sub-workflow fields for regular tool nodes', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'regular',
        position: { x: 0, y: 0 },
        data: {
          name: 'Regular',
          toolName: 'tool_a',
          parameters: {},
          sub_workflow: null,
          published_inputs: [],
          published_outputs: [],
          sub_workflow_readonly_reason: null,
        },
      }],
      edges: [],
    })

    expect('sub_workflow' in (result.nodes[0] as any)).toBe(false)
    expect('published_inputs' in (result.nodes[0] as any)).toBe(false)
    expect('published_outputs' in (result.nodes[0] as any)).toBe(false)
    expect('sub_workflow_readonly_reason' in (result.nodes[0] as any)).toBe(false)
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

  it('preserves optional sub-workflow graph fields', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'outer',
        type: 'sub_workflow',
        position: { x: 100, y: 200 },
        data: {
          name: 'Outer',
          toolName: '__sub_workflow__',
          parameters: { image: '/tmp/input.tif' },
          sub_workflow: {
            nodes: [{
              id: 'inner',
              name: 'Inner',
              tool_name: 'TProcTool',
              position: [1, 2],
              parameters: { diameter: 7 },
              resources: {},
              output_templates: {},
              enabled: true,
              collapsed: false,
            }],
            edges: [],
          },
          published_inputs: [{
            name: 'image',
            internal_node_id: 'inner',
            internal_field: 'input_image',
            kind: 'input',
            schema: { type: 'Path' },
            default: null,
          }],
          published_outputs: [{
            name: 'mask',
            internal_node_id: 'inner',
            internal_output: 'mask',
            schema: { type: 'Path' },
          }],
          sub_workflow_readonly_reason: null,
        },
      }],
      edges: [],
    })

    expect(result.nodes[0]).toMatchObject({
      tool_name: '__sub_workflow__',
      sub_workflow: {
        nodes: [expect.objectContaining({ id: 'inner' })],
        edges: [],
      },
      published_inputs: [expect.objectContaining({ name: 'image' })],
      published_outputs: [expect.objectContaining({ name: 'mask' })],
      sub_workflow_readonly_reason: null,
    })
  })
})
