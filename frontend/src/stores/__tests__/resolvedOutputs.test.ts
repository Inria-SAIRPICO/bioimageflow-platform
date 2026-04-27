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
})
