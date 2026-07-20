import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { GraphState, ValidationResult } from '@/api/types'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'
import { makeGraph, requireToolNode } from '@/test-utils/graphFixtures'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
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
const mockedGet = vi.mocked(api.get)

function graph(value: string): GraphState {
  return makeGraph({
    nodes: [{
      type: 'tool',
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
  })
}

function validation(valid: boolean): ValidationResult {
  return { valid, node_statuses: {}, errors: [] }
}

function draftResponse(
  workflowId: string,
  draftRevision: number,
  value: GraphState,
  result = validation(true),
) {
  return {
    draft_version: 1 as const,
    workflow_id: workflowId,
    base_saved_revision: 'sha256:base',
    draft_revision: draftRevision,
    updated_at: '2026-07-16T00:00:00Z',
    updated_by: 'frontend' as const,
    dirty_against_saved: true,
    graph: value,
    validation: result,
  }
}

function workflowIdFromUrl(url: string): string {
  const segments = url.split('/')
  return decodeURIComponent(segments[segments.length - 1] ?? '')
}

describe('canvas-scoped graph sync routing', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockedPut.mockReset()
    mockedGet.mockReset().mockImplementation(async (url) => ({
      data: draftResponse(workflowIdFromUrl(String(url)), 1, graph('initial')),
    }))
    mockedPut.mockImplementation(async (url, body) => {
      const workflowId = workflowIdFromUrl(String(url))
      const request = body as {
        graph: GraphState
        expected_revision: number
      }
      return {
        data: draftResponse(
          workflowId,
          request.expected_revision + 1,
          request.graph,
          validation(workflowId === 'workflow-a'),
        ),
      }
    })
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
    syncB.syncGraphState(graph('b'))
    workflowA = 'renamed-after-queue'
    workflowB = 'active-workflow-changed'
    await Promise.all([syncA.flushNow(), syncB.flushNow()])

    expect(mockedPut).toHaveBeenCalledWith(
      '/api/v1/workflow-drafts/workflow-a',
      expect.objectContaining({
        graph: graph('a'),
        expected_revision: 1,
        validate: true,
      }),
    )
    expect(requireToolNode(syncA.currentGraph.value).parameters).toEqual({ value: 'a' })
    expect(requireToolNode(syncB.currentGraph.value).parameters).toEqual({ value: 'b' })
    expect(syncA.validationResult.value).toEqual(validation(true))
    expect(syncB.validationResult.value).toEqual(validation(false))
  })

  it('routes the no-argument facade to the explicitly active canvas', async () => {
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
    active.syncGraphState(graph('active-a'))
    const flushA = active.flushNow()
    activateGraphSyncCanvas(canvasB)
    await flushA

    expect(requireToolNode(syncA.currentGraph.value).parameters).toEqual({ value: 'active-a' })
    expect(requireToolNode(syncB.currentGraph.value).parameters).toEqual({ value: 'b' })
    expect(mockedPut).toHaveBeenLastCalledWith(
      '/api/v1/workflow-drafts/workflow-a',
      expect.objectContaining({
        graph: graph('active-a'),
        validate: true,
      }),
    )
    expect(syncA.validationResult.value).toEqual(validation(true))
    expect(syncB.validationResult.value).toBeNull()

    expect(requireToolNode(active.currentGraph.value).parameters).toEqual({ value: 'b' })
    await active.flushNow()
    expect(active.validationResult.value).toEqual(validation(false))
  })

  it('unregisters one canvas without disposing or selecting another', async () => {
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
