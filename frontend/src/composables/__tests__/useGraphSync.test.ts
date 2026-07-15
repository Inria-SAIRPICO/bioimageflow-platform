import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref, watch } from 'vue'
import type { ValidationResult } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    put: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { useWorkflowStore } from '@/stores/workflow'
import { useGraphSync, serializeGraph, _resetGraphSyncForTest } from '../useGraphSync'

const mockedPut = vi.mocked(api.put)

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

  it('joins an in-flight request before sending the newer graph', async () => {
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

    // A newer graph queues while the first request is in flight.
    syncGraph(makeVueFlowGraph('2'))
    await vi.advanceTimersByTimeAsync(300)
    expect(mockedPut).toHaveBeenCalledTimes(1)

    // Resolving the first request starts the queued newer request. Its stale
    // validation is not published while the newer graph remains pending.
    resolveFirst({ data: makeValidation(false) })
    await vi.advanceTimersByTimeAsync(0)
    expect(validationResult.value).toBeNull()
    expect(mockedPut).toHaveBeenCalledTimes(2)

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

  it('ignores an in-flight response after a newer graph is queued', async () => {
    let resolveFirst!: (v: unknown) => void
    let resolveSecond!: (v: unknown) => void

    mockedPut
      .mockReturnValueOnce(new Promise(r => { resolveFirst = r }))
      .mockReturnValueOnce(new Promise(r => { resolveSecond = r }))

    const { syncGraph, validationResult } = useGraphSync()

    syncGraph(makeVueFlowGraph('old'))
    await vi.advanceTimersByTimeAsync(300)
    expect(mockedPut).toHaveBeenCalledTimes(1)

    syncGraph(makeVueFlowGraph('new'))
    resolveFirst({
      data: {
        valid: true,
        node_statuses: {
          old: { node_id: 'old', status: 'executed', cached: true },
        },
        errors: [],
      },
    })
    await vi.advanceTimersByTimeAsync(0)

    expect(validationResult.value).toBeNull()
    await vi.advanceTimersByTimeAsync(300)
    expect(mockedPut).toHaveBeenCalledTimes(2)

    resolveSecond({ data: makeValidation(true) })
    await vi.advanceTimersByTimeAsync(0)
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

  it('flushNow waits for pending Vue watchers before sending', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation() })
    const { syncGraph, flushNow } = useGraphSync()
    const parameter = ref('old')

    watch(parameter, (value) => {
      const graph = makeVueFlowGraph()
      graph.nodes[0]!.data.parameters = { path: value }
      syncGraph(graph)
    })

    parameter.value = 'new'
    await flushNow()

    expect(mockedPut).toHaveBeenCalledWith(
      '/api/v1/graph',
      {
        graph: expect.objectContaining({
          nodes: [
            expect.objectContaining({
              parameters: { path: 'new' },
            }),
          ],
        }),
        workflow_name: null,
      },
      expect.objectContaining({ signal: expect.anything() }),
    )
  })

  it('syncGraphState keeps backend graph state authoritative', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation() })
    const graph = {
      nodes: [{
        id: 'a',
        name: 'A',
        tool_name: 'tool_a',
        position: [1, 2],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [{
        type: 'column_ref',
        id: 'e1',
        source_node: 'a',
        target_node: 'b',
        source_output: 'result',
        target_input: 'image',
      }],
    } as any
    const { syncGraphState, currentGraph, flushNow } = useGraphSync()

    syncGraphState(graph)
    graph.edges = []

    expect(currentGraph.value.edges).toEqual([expect.objectContaining({ id: 'e1' })])
    await flushNow()

    expect(mockedPut).toHaveBeenCalledWith(
      '/api/v1/graph',
      {
        graph: expect.objectContaining({
          edges: [expect.objectContaining({ id: 'e1' })],
        }),
        workflow_name: null,
      },
      expect.objectContaining({ signal: expect.anything() }),
    )
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
    await expect(flushNow()).rejects.toMatchObject({ message: 'network boom' })

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
    await expect(flushNow()).rejects.toMatchObject({ message: 'boom' })
    expect(errorStore.errors).toHaveLength(1)
    expect(errorStore.errors[0]!.kind).toBe('graph_sync_error')
    expect(errorStore.errors[0]!.status).toBe(500)
  })

  it('captures workflow identity when the graph is queued', async () => {
    mockedPut.mockResolvedValue({ data: makeValidation(true) })
    const workflowStore = useWorkflowStore()
    workflowStore.$patch({ current: { name: 'queued-workflow' } as any })
    const { syncGraph, flushNow } = useGraphSync()

    syncGraph(makeVueFlowGraph())
    workflowStore.$patch({ current: { name: 'later-workflow' } as any })
    await flushNow()

    expect(mockedPut).toHaveBeenCalledWith(
      '/api/v1/graph',
      expect.objectContaining({ workflow_name: 'queued-workflow' }),
      expect.anything(),
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
