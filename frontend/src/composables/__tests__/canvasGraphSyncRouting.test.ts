import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { GraphState, ValidationResult } from '@/api/types'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'

vi.mock('@/api/client', () => ({
  api: {
    put: vi.fn(),
  },
}))

import { api } from '@/api/client'
import {
  _resetGraphSyncForTest,
  activateGraphSyncCanvas,
  graphSyncCanvasSessions,
  unregisterGraphSyncCanvas,
  useGraphSync,
} from '../useGraphSync'

const mockedPut = vi.mocked(api.put)

function graph(value: string): GraphState {
  return {
    nodes: [{
      id: 'repeated-node',
      name: 'Repeated',
      tool_name: 'tool',
      position: [0, 0],
      parameters: { value },
      resources: {},
      output_templates: {},
      enabled: true,
      collapsed: false,
    }],
    edges: [],
  }
}

function validation(valid: boolean): ValidationResult {
  return { valid, node_statuses: {}, errors: [] }
}

describe('canvas-scoped graph sync routing', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockedPut.mockReset()
    _resetGraphSyncForTest()
  })

  afterEach(() => {
    _resetGraphSyncForTest()
    vi.useRealTimers()
  })

  it('does not activate a canvas when registering or accessing its graph sync', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const options = {
      descriptor: { kind: 'root' as const, canvasId, workflowId: 'workflow-a' },
      getWorkflowId: () => 'workflow-a',
    }

    useGraphSync(options)
    useGraphSync(options)

    expect(graphSyncCanvasSessions.activeCanvasId.value).toBeNull()
    expect(graphSyncCanvasSessions.get(canvasId)).not.toBeNull()
  })

  it('isolates repeated node ids and samples an inactive canvas workflow at queue time', async () => {
    mockedPut.mockImplementation(async (_url, body) => ({
      data: validation((body as any).workflow_name === 'workflow-a'),
    }))
    let workflowA = 'workflow-a'
    let workflowB = 'workflow-b'
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const syncA = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: workflowA },
      getWorkflowId: () => workflowA,
    })
    const syncB = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: workflowB },
      getWorkflowId: () => workflowB,
    })

    activateGraphSyncCanvas(canvasB)
    syncA.syncGraphState(graph('a'))
    workflowA = 'renamed-after-queue'
    workflowB = 'active-workflow-changed'
    syncB.syncGraphState(graph('b'))
    await Promise.all([syncA.flushNow(), syncB.flushNow()])

    expect(mockedPut).toHaveBeenCalledWith(
      '/api/v1/graph',
      { graph: graph('a'), workflow_name: 'workflow-a' },
      expect.objectContaining({ signal: expect.anything() }),
    )
    expect(syncA.currentGraph.value.nodes[0]?.parameters).toEqual({ value: 'a' })
    expect(syncB.currentGraph.value.nodes[0]?.parameters).toEqual({ value: 'b' })
    expect(syncA.validationResult.value).toEqual(validation(true))
    expect(syncB.validationResult.value).toEqual(validation(false))
  })

  it('routes the no-argument facade to the explicitly active canvas', async () => {
    mockedPut.mockImplementation(async (_url, body) => ({
      data: validation((body as any).workflow_name === 'workflow-a'),
    }))
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const syncA = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'workflow-a' },
      getWorkflowId: () => 'workflow-a',
    })
    const syncB = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'workflow-b' },
      getWorkflowId: () => 'workflow-b',
    })
    syncA.syncGraphState(graph('a'))
    syncB.syncGraphState(graph('b'))
    const active = useGraphSync()

    activateGraphSyncCanvas(canvasA)
    active.syncNodeParameters('repeated-node', { value: 'active-a' })
    const flushA = active.flushNow()
    activateGraphSyncCanvas(canvasB)
    await flushA

    expect(syncA.currentGraph.value.nodes[0]?.parameters).toEqual({ value: 'active-a' })
    expect(syncB.currentGraph.value.nodes[0]?.parameters).toEqual({ value: 'b' })
    expect(mockedPut).toHaveBeenLastCalledWith(
      '/api/v1/graph',
      { graph: graph('active-a'), workflow_name: 'workflow-a' },
      expect.objectContaining({ signal: expect.anything() }),
    )
    expect(syncA.validationResult.value).toEqual(validation(true))
    expect(syncB.validationResult.value).toBeNull()

    expect(active.currentGraph.value.nodes[0]?.parameters).toEqual({ value: 'b' })
    await active.flushNow()
    expect(active.validationResult.value).toEqual(validation(false))
  })

  it('unregisters one canvas without disposing or selecting another', async () => {
    mockedPut.mockResolvedValue({ data: validation(true) })
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'workflow-a' },
      getWorkflowId: () => 'workflow-a',
    })
    const syncB = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'workflow-b' },
      getWorkflowId: () => 'workflow-b',
    })
    activateGraphSyncCanvas(canvasA)

    unregisterGraphSyncCanvas(canvasA)

    expect(graphSyncCanvasSessions.activeCanvasId.value).toBeNull()
    expect(graphSyncCanvasSessions.get(canvasA)).toBeNull()
    expect(graphSyncCanvasSessions.get(canvasB)).not.toBeNull()
    syncB.syncGraphState(graph('still-alive'))
    await syncB.flushNow()
    expect(syncB.currentGraph.value).toEqual(graph('still-alive'))
  })

  it('does not silently use the legacy canvas when sessions exist but none is active', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'workflow-a' },
      getWorkflowId: () => 'workflow-a',
    })

    expect(() => useGraphSync().syncGraphState(graph('wrong-target'))).toThrow(
      'No active canvas graph sync session',
    )
    expect(mockedPut).not.toHaveBeenCalled()
  })
})
