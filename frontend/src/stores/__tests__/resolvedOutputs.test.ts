import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ToolMetadata } from '@/api/types'

// Mock the API client
const mockFetchNodeOutputSchema = vi.fn()
vi.mock('@/api/client', () => ({
  api: { create: () => ({}) },
  fetchNodeOutputSchema: (...args: any[]) => mockFetchNodeOutputSchema(...args),
}))

// Mock useIndexedDB (required by useGraphSync's serializeGraph dependency chain)
vi.mock('@/composables/useIndexedDB', () => ({
  useIndexedDB: () => ({
    saveWorkflow: vi.fn(),
    loadWorkflow: vi.fn().mockResolvedValue(null),
  }),
}))

import { useResolvedOutputsStore } from '@/stores/resolvedOutputs'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function registerCanvases(): [CanvasId, CanvasId] {
  const canvasA = canvasIdFromPanelId('workflow:a')
  const canvasB = canvasIdFromPanelId('workflow:b')
  canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
  canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
  return [canvasA, canvasB]
}

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'test',
    display_name: 'Test',
    package: 'test',
    package_version: '1.0.0',
    tool_type: 'DataFrameTool',
    accepts_upstream: true,
    dynamic_outputs: true,
    documentation: '',
    tags: [],
    categories: [],
    inputs: {},
    outputs: {},
    environment: null,
    ...overrides,
  }
}

describe('resolvedOutputs store', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    mockFetchNodeOutputSchema.mockReset()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const makeGraph = () => ({
    nodes: [
      {
        id: 'gen_1',
        type: 'tool',
        position: { x: 0, y: 0 },
        data: {
          toolName: 'Generate',
          tool: makeTool({ name: 'Generate', dynamic_outputs: true }),
          parameters: { column_name: 'sensitivity' },
        },
      },
      {
        id: 'cross_1',
        type: 'tool',
        position: { x: 100, y: 0 },
        data: {
          toolName: 'CrossJoin',
          tool: makeTool({ name: 'CrossJoin', dynamic_outputs: true }),
          parameters: {},
        },
      },
    ],
    edges: [
      {
        id: 'e1',
        source: 'gen_1',
        target: 'cross_1',
        sourceHandle: 'sensitivity',
        targetHandle: '__positional_0',
        type: 'positional',
      },
    ],
  })

  it('refreshResolvedOutputs debounces and fetches', async () => {
    const store = useResolvedOutputsStore()
    mockFetchNodeOutputSchema.mockResolvedValue({
      resolved: true,
      columns: { sensitivity: { type: 'any' } },
    })

    const graph = makeGraph()
    const getGraph = () => graph
    const getToolForNode = (nodeId: string) =>
      graph.nodes.find((n) => n.id === nodeId)?.data?.tool as ToolMetadata | undefined

    store.refreshResolvedOutputs('gen_1', getGraph, getToolForNode)

    // Not called yet (debounced)
    expect(mockFetchNodeOutputSchema).not.toHaveBeenCalled()

    // Fast forward debounce timer
    vi.advanceTimersByTime(250)
    await vi.runAllTimersAsync()

    expect(mockFetchNodeOutputSchema).toHaveBeenCalledWith('gen_1', expect.any(Object))
    expect(store.resolvedOutputsByNodeId['gen_1']).toEqual({
      resolved: true,
      columns: { sensitivity: { type: 'any' } },
    })
  })

  it('propagates downstream to dynamic_outputs nodes along positional edges', async () => {
    const store = useResolvedOutputsStore()
    mockFetchNodeOutputSchema
      .mockResolvedValueOnce({
        resolved: true,
        columns: { sensitivity: { type: 'any' } },
      })
      .mockResolvedValueOnce({
        resolved: true,
        columns: { sensitivity: { type: 'any' }, path: { type: 'Path' } },
      })

    const graph = makeGraph()
    const getGraph = () => graph
    const getToolForNode = (nodeId: string) =>
      graph.nodes.find((n) => n.id === nodeId)?.data?.tool as ToolMetadata | undefined

    store.refreshResolvedOutputs('gen_1', getGraph, getToolForNode)
    vi.advanceTimersByTime(250)
    await vi.runAllTimersAsync()

    // Both gen_1 and cross_1 should have been fetched
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledTimes(2)
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledWith('gen_1', expect.any(Object))
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledWith('cross_1', expect.any(Object))

    expect(store.resolvedOutputsByNodeId['cross_1']).toEqual({
      resolved: true,
      columns: { sensitivity: { type: 'any' }, path: { type: 'Path' } },
    })
  })

  it('propagation uses dynamic_outputs flag, not class names — fictional tool is refreshed', async () => {
    const store = useResolvedOutputsStore()
    mockFetchNodeOutputSchema.mockResolvedValue({
      resolved: true,
      columns: { x: { type: 'any' } },
    })

    // Create a graph with a fictional third-party merge tool
    const graph = {
      nodes: [
        {
          id: 'gen_1',
          type: 'tool',
          position: { x: 0, y: 0 },
          data: {
            toolName: 'Generate',
            tool: makeTool({ name: 'Generate', dynamic_outputs: true }),
            parameters: { column_name: 'x' },
          },
        },
        {
          id: 'custom_1',
          type: 'tool',
          position: { x: 100, y: 0 },
          data: {
            toolName: 'MyCustomMerge',
            tool: makeTool({ name: 'MyCustomMerge', dynamic_outputs: true }),
            parameters: {},
          },
        },
      ],
      edges: [
        {
          id: 'e1',
          source: 'gen_1',
          target: 'custom_1',
          sourceHandle: 'x',
          targetHandle: '__positional_0',
          type: 'positional',
        },
      ],
    }

    const getGraph = () => graph
    const getToolForNode = (nodeId: string) =>
      graph.nodes.find((n) => n.id === nodeId)?.data?.tool as ToolMetadata | undefined

    store.refreshResolvedOutputs('gen_1', getGraph, getToolForNode)
    vi.advanceTimersByTime(250)
    await vi.runAllTimersAsync()

    // custom_1 (MyCustomMerge) should also have been refreshed via propagation
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledWith('custom_1', expect.any(Object))
    expect(store.resolvedOutputsByNodeId['custom_1']).toBeDefined()
  })

  it('does not propagate to nodes without dynamic_outputs', async () => {
    const store = useResolvedOutputsStore()
    mockFetchNodeOutputSchema.mockResolvedValue({
      resolved: true,
      columns: { x: { type: 'any' } },
    })

    const graph = {
      nodes: [
        {
          id: 'gen_1',
          type: 'tool',
          position: { x: 0, y: 0 },
          data: {
            toolName: 'Generate',
            tool: makeTool({ name: 'Generate', dynamic_outputs: true }),
            parameters: { column_name: 'x' },
          },
        },
        {
          id: 'static_1',
          type: 'tool',
          position: { x: 100, y: 0 },
          data: {
            toolName: 'FilterRows',
            tool: makeTool({ name: 'FilterRows', dynamic_outputs: false }),
            parameters: {},
          },
        },
      ],
      edges: [
        {
          id: 'e1',
          source: 'gen_1',
          target: 'static_1',
          sourceHandle: 'x',
          targetHandle: '__positional_0',
          type: 'positional',
        },
      ],
    }

    const getGraph = () => graph
    const getToolForNode = (nodeId: string) =>
      graph.nodes.find((n) => n.id === nodeId)?.data?.tool as ToolMetadata | undefined

    store.refreshResolvedOutputs('gen_1', getGraph, getToolForNode)
    vi.advanceTimersByTime(250)
    await vi.runAllTimersAsync()

    // Only gen_1 should be fetched (static_1 has dynamic_outputs=false)
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledTimes(1)
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledWith('gen_1', expect.any(Object))
  })

  it('removeNode clears the entry and any pending timer', () => {
    const store = useResolvedOutputsStore()
    store.resolvedOutputsByNodeId['gen_1'] = { resolved: true, columns: {} }
    store.removeNode('gen_1')
    expect(store.resolvedOutputsByNodeId['gen_1']).toBeUndefined()
  })

  it('keeps resolved outputs and debounce timers independent for identical node ids', async () => {
    const [canvasA, canvasB] = registerCanvases()
    const store = useResolvedOutputsStore()
    const resultA = deferred<{ resolved: boolean; columns: Record<string, unknown> }>()
    const resultB = deferred<{ resolved: boolean; columns: Record<string, unknown> }>()
    mockFetchNodeOutputSchema
      .mockReturnValueOnce(resultA.promise)
      .mockReturnValueOnce(resultB.promise)

    const graphA = makeGraph()
    const graphB = makeGraph()
    store.refreshCanvasResolvedOutputs(canvasA, 'gen_1', () => graphA, () => undefined)
    store.refreshCanvasResolvedOutputs(canvasB, 'gen_1', () => graphB, () => undefined)

    vi.advanceTimersByTime(200)
    await Promise.resolve()
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledTimes(2)

    resultB.resolve({ resolved: true, columns: { from_b: { type: 'str' } } })
    await Promise.resolve()
    await Promise.resolve()
    expect(store.getCanvasResolvedOutput(canvasA, 'gen_1')).toBeUndefined()
    expect(store.getCanvasResolvedOutput(canvasB, 'gen_1')).toEqual({
      resolved: true,
      columns: { from_b: { type: 'str' } },
    })

    resultA.resolve({ resolved: true, columns: { from_a: { type: 'int' } } })
    await Promise.resolve()
    await Promise.resolve()
    expect(store.getCanvasResolvedOutput(canvasA, 'gen_1')).toEqual({
      resolved: true,
      columns: { from_a: { type: 'int' } },
    })
    expect(store.getCanvasResolvedOutput(canvasB, 'gen_1')).toEqual({
      resolved: true,
      columns: { from_b: { type: 'str' } },
    })

    canvasSessionRegistry.activate(canvasB)
    expect(store.resolvedOutputsByNodeId.gen_1?.columns).toEqual({
      from_b: { type: 'str' },
    })
  })

  it('releasing one canvas cancels only its timers and cache', async () => {
    const [canvasA, canvasB] = registerCanvases()
    const store = useResolvedOutputsStore()
    mockFetchNodeOutputSchema.mockResolvedValue({ resolved: true, columns: {} })
    const graph = makeGraph()

    store.refreshCanvasResolvedOutputs(canvasA, 'gen_1', () => graph, () => undefined)
    store.refreshCanvasResolvedOutputs(canvasB, 'gen_1', () => graph, () => undefined)
    store.releaseCanvas(canvasA)

    await vi.advanceTimersByTimeAsync(200)
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledTimes(1)
    expect(store.getCanvasResolvedOutput(canvasA, 'gen_1')).toBeUndefined()
    expect(store.getCanvasResolvedOutput(canvasB, 'gen_1')).toEqual({
      resolved: true,
      columns: {},
    })
  })

  it('does not propagate through a downstream request superseded while it is in flight', async () => {
    const [canvasA] = registerCanvases()
    const store = useResolvedOutputsStore()
    const oldCrossResult = deferred<{ resolved: boolean; columns: Record<string, unknown> }>()
    let crossCalls = 0
    mockFetchNodeOutputSchema.mockImplementation((nodeId: string) => {
      if (nodeId === 'gen_1') {
        return Promise.resolve({ resolved: true, columns: { source: { type: 'str' } } })
      }
      if (nodeId === 'cross_1') {
        crossCalls += 1
        if (crossCalls === 1) return oldCrossResult.promise
        return Promise.resolve({ resolved: true, columns: { current: { type: 'str' } } })
      }
      return Promise.resolve({ resolved: true, columns: { stale_tail: { type: 'str' } } })
    })
    const graph = {
      ...makeGraph(),
      nodes: [
        ...makeGraph().nodes,
        {
          id: 'tail_1',
          type: 'tool',
          position: { x: 200, y: 0 },
          data: { tool: makeTool({ name: 'Tail', dynamic_outputs: true }) },
        },
      ],
      edges: [
        ...makeGraph().edges,
        {
          id: 'e2',
          source: 'cross_1',
          target: 'tail_1',
          targetHandle: '__positional_0',
        },
      ],
    }
    const getTool = (nodeId: string) => (
      graph.nodes.find((node) => node.id === nodeId)?.data?.tool as ToolMetadata | undefined
    )

    store.refreshCanvasResolvedOutputs(canvasA, 'gen_1', () => graph, getTool)
    vi.advanceTimersByTime(200)
    await Promise.resolve()
    await Promise.resolve()
    expect(mockFetchNodeOutputSchema.mock.calls.map(([nodeId]) => nodeId)).toEqual([
      'gen_1',
      'cross_1',
    ])

    await store.refreshCanvasNow(canvasA, 'cross_1', () => graph)
    oldCrossResult.resolve({ resolved: true, columns: { stale: { type: 'str' } } })
    await Promise.resolve()
    await Promise.resolve()

    expect(mockFetchNodeOutputSchema).not.toHaveBeenCalledWith('tail_1', expect.anything())
    expect(store.getCanvasResolvedOutput(canvasA, 'cross_1')?.columns).toEqual({
      current: { type: 'str' },
    })
  })

  it('stops sibling propagation when the source is superseded during an awaited child', async () => {
    const [canvasA] = registerCanvases()
    const store = useResolvedOutputsStore()
    const childResult = deferred<{ resolved: boolean; columns: Record<string, unknown> }>()
    mockFetchNodeOutputSchema.mockImplementation((nodeId: string) => {
      if (nodeId === 'cross_1') return childResult.promise
      return Promise.resolve({ resolved: true, columns: {} })
    })
    const base = makeGraph()
    const graph = {
      ...base,
      nodes: [
        ...base.nodes,
        {
          id: 'sibling_1',
          type: 'tool',
          position: { x: 100, y: 100 },
          data: { tool: makeTool({ name: 'Sibling', dynamic_outputs: true }) },
        },
      ],
      edges: [
        ...base.edges,
        {
          id: 'e-sibling',
          source: 'gen_1',
          target: 'sibling_1',
          targetHandle: '__positional_0',
        },
      ],
    }
    const getTool = (nodeId: string) => (
      graph.nodes.find((node) => node.id === nodeId)?.data?.tool as ToolMetadata | undefined
    )

    store.refreshCanvasResolvedOutputs(canvasA, 'gen_1', () => graph, getTool)
    vi.advanceTimersByTime(200)
    await Promise.resolve()
    await Promise.resolve()
    expect(mockFetchNodeOutputSchema).toHaveBeenCalledWith('cross_1', expect.anything())

    store.refreshCanvasResolvedOutputs(canvasA, 'gen_1', () => graph, getTool)
    childResult.resolve({ resolved: true, columns: {} })
    await Promise.resolve()
    await Promise.resolve()

    expect(store.getCanvasResolvedOutput(canvasA, 'cross_1')).toBeUndefined()
    expect(mockFetchNodeOutputSchema).not.toHaveBeenCalledWith('sibling_1', expect.anything())
  })

  it('does not recreate a released canvas context from delayed fixed-canvas work', async () => {
    const [canvasA] = registerCanvases()
    const store = useResolvedOutputsStore()
    const graph = makeGraph()
    mockFetchNodeOutputSchema.mockResolvedValue({ resolved: true, columns: {} })

    store.resolvedOutputsForCanvas(canvasA)
    store.releaseCanvas(canvasA)
    store.refreshCanvasResolvedOutputs(canvasA, 'gen_1', () => graph, () => undefined)
    await vi.advanceTimersByTimeAsync(200)

    expect(mockFetchNodeOutputSchema).not.toHaveBeenCalled()
    expect(store.getCanvasResolvedOutput(canvasA, 'gen_1')).toBeUndefined()

    store.resolvedOutputsForCanvas(canvasA)
    store.refreshCanvasResolvedOutputs(canvasA, 'gen_1', () => graph, () => undefined)
    await vi.advanceTimersByTimeAsync(200)

    expect(mockFetchNodeOutputSchema).toHaveBeenCalledTimes(1)
    expect(store.getCanvasResolvedOutput(canvasA, 'gen_1')).toEqual({
      resolved: true,
      columns: {},
    })
  })

  it('does not expose or mutate legacy output state while registered canvases have no active canvas', async () => {
    const store = useResolvedOutputsStore()
    store.resolvedOutputsByNodeId.gen_1 = {
      resolved: true,
      columns: { legacy: { type: 'str' } },
    }
    registerCanvases()
    const graph = makeGraph()

    expect(store.resolvedOutputsByNodeId.gen_1).toBeUndefined()
    store.refreshResolvedOutputs('gen_1', () => graph, () => undefined)
    await vi.advanceTimersByTimeAsync(200)

    expect(mockFetchNodeOutputSchema).not.toHaveBeenCalled()
  })
})
