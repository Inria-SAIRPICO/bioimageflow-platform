import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GraphState, ValidationResult } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import {
  _resetCanvasPersistenceForTest,
  useCanvasPersistence,
  type CanvasPersistenceTransports,
} from '../useCanvasPersistence'
import {
  canvasIdFromPanelId,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from '../useGraphSync'

function graph(value: string): GraphState {
  return {
    nodes: [{
      id: 'node',
      name: 'Node',
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

function validation(): ValidationResult {
  return { valid: true, node_statuses: {}, errors: [] }
}

function draft(
  workflowId: string,
  revision: number,
  value = `revision-${revision}`,
): WorkflowDraftResponse {
  return {
    draft_version: 1,
    workflow_id: workflowId,
    base_saved_revision: 'sha256:base',
    draft_revision: revision,
    updated_at: '2026-07-15T12:00:00Z',
    updated_by: 'frontend',
    dirty_against_saved: true,
    graph: graph(value),
    validation: validation(),
  }
}

function root(panelId: string, workflowId: string): CanvasSessionDescriptor {
  return {
    kind: 'root',
    canvasId: canvasIdFromPanelId(panelId),
    workflowId,
  }
}

function transports(
  initialRevisions: Record<string, number>,
): CanvasPersistenceTransports & {
  fetchDraft: ReturnType<typeof vi.fn>
  putDraft: ReturnType<typeof vi.fn>
  writeRecovery: ReturnType<typeof vi.fn>
} {
  const fetchDraft = vi.fn(async (workflowId: string) => (
    draft(workflowId, initialRevisions[workflowId] ?? 0)
  ))
  const putDraft = vi.fn(async (
    workflowId: string,
    body: { graph: GraphState; expected_revision: number },
  ) => draft(workflowId, body.expected_revision + 1, 'accepted'))
  const writeRecovery = vi.fn(async () => {})
  return { fetchDraft, putDraft, writeRecovery }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('canvas persistence routing', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    _resetCanvasPersistenceForTest()
  })

  afterEach(() => {
    _resetCanvasPersistenceForTest()
    vi.useRealTimers()
  })

  it('keeps two root draft and recovery writes independently addressed in one debounce', async () => {
    const io = transports({ 'workflow-a': 2, 'workflow-b': 7 })
    const descriptorA = root('workflow:a', 'workflow-a')
    const descriptorB = root('workflow:b', 'workflow-b')
    const a = useCanvasPersistence({
      descriptor: descriptorA,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const b = useCanvasPersistence({
      descriptor: descriptorB,
      getWorkflowId: () => 'workflow-b',
      transports: io,
    })

    a.queueGraph(graph('a'))
    b.queueGraph(graph('b'))
    await Promise.all([a.flush(), b.flush()])

    expect(io.putDraft).toHaveBeenCalledTimes(2)
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.objectContaining({
      expected_revision: 2,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'a' } })],
      }),
    }))
    expect(io.putDraft).toHaveBeenCalledWith('workflow-b', expect.objectContaining({
      expected_revision: 7,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'b' } })],
      }),
    }))
    expect(io.writeRecovery).toHaveBeenCalledTimes(2)
    expect(io.writeRecovery).toHaveBeenCalledWith(expect.objectContaining({
      name: 'workflow-a',
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'a' } })],
      }),
    }))
    expect(io.writeRecovery).toHaveBeenCalledWith(expect.objectContaining({
      name: 'workflow-b',
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'b' } })],
      }),
    }))
  })

  it('captures an inactive canvas workflow before global activation changes', async () => {
    const io = transports({ 'workflow-a': 3, 'workflow-b': 9 })
    let workflowId = 'workflow-a'
    const descriptor = root('workflow:a', 'workflow-a')
    const fixed = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => workflowId,
      transports: io,
    })

    fixed.queueGraph(graph('queued-for-a'))
    workflowId = 'workflow-b'
    graphSyncCanvasSessions.activate(descriptor.canvasId)
    await fixed.flush()

    expect(io.fetchDraft).toHaveBeenCalledWith('workflow-a')
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.anything())
    expect(io.writeRecovery).toHaveBeenCalledWith(expect.objectContaining({
      name: 'workflow-a',
    }))
  })

  it('uses an authoritative draft response without fetching initialization again', async () => {
    const io = transports({ 'workflow-a': 2 })
    const fixed = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })

    fixed.initializeFromDraft(draft('workflow-a', 8))
    fixed.queueGraph(graph('local'))
    await fixed.flush()

    expect(io.fetchDraft).not.toHaveBeenCalled()
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.objectContaining({
      expected_revision: 8,
    }))
  })

  it('clears pending after edits coalesce while draft initialization is in flight', async () => {
    const initial = deferred<WorkflowDraftResponse>()
    const io = transports({ 'workflow-a': 3 })
    io.fetchDraft.mockReturnValue(initial.promise)
    const fixed = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })

    fixed.queueGraph(graph('first'))
    fixed.queueGraph(graph('second'))
    fixed.queueGraph(graph('latest'))
    expect(fixed.isPending.value).toBe(true)

    initial.resolve(draft('workflow-a', 3))
    await fixed.flush()

    expect(io.putDraft).toHaveBeenCalledOnce()
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.objectContaining({
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'latest' } })],
      }),
    }))
    expect(fixed.isPending.value).toBe(false)
  })

  it('retains a same-workflow CAS conflict and blocks the critical operation', async () => {
    let backendRevision = 1
    const io = transports({ shared: 1 })
    io.fetchDraft.mockImplementation(async () => draft('shared', backendRevision))
    io.putDraft.mockImplementation(async (
      workflowId: string,
      body: { expected_revision: number },
    ) => {
      if (body.expected_revision !== backendRevision) {
        throw {
          response: {
            status: 409,
            data: { current_revision: backendRevision },
          },
        }
      }
      backendRevision += 1
      return draft(workflowId, backendRevision)
    })
    const a = useCanvasPersistence({
      descriptor: root('workflow:a', 'shared'),
      getWorkflowId: () => 'shared',
      transports: io,
    })
    const b = useCanvasPersistence({
      descriptor: root('workflow:b', 'shared'),
      getWorkflowId: () => 'shared',
      transports: io,
    })

    a.queueGraph(graph('a'))
    b.queueGraph(graph('b-local'))
    await a.flush()

    await expect(b.ensureFreshForCriticalOperation()).resolves.toBe(false)
    expect(b.currentGraph.value.nodes[0]?.parameters).toEqual({
      value: 'b-local',
    })
    expect(b.hasConflict.value).toBe(true)
  })

  it('clears a sticky CAS conflict only after explicit authoritative resolution', async () => {
    const conflict = {
      response: {
        status: 409,
        data: { current_revision: 2 },
      },
    }
    const io = transports({ 'workflow-a': 1 })
    io.fetchDraft.mockResolvedValueOnce(draft('workflow-a', 1))
    io.putDraft.mockRejectedValueOnce(conflict)
    const fixed = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    fixed.queueGraph(graph('local'))

    await expect(fixed.ensureFreshForCriticalOperation()).resolves.toBe(false)
    expect(fixed.hasConflict.value).toBe(true)

    const resolved = draft('workflow-a', 3, 'resolved')
    io.fetchDraft.mockResolvedValue(resolved)
    fixed.resolveFromDraft(resolved)

    expect(fixed.hasConflict.value).toBe(false)
    fixed.queueGraph(graph('after-resolution'))
    await expect(fixed.ensureFreshForCriticalOperation()).resolves.toBe(true)
    expect(fixed.currentGraph.value.nodes[0]?.parameters).toEqual({
      value: 'after-resolution',
    })
    expect(io.putDraft).toHaveBeenCalledTimes(2)
    expect(io.putDraft).toHaveBeenLastCalledWith('workflow-a', expect.objectContaining({
      expected_revision: 3,
    }))
  })

  it('blocks on a fetched newer revision without replacing the local graph', async () => {
    const io = transports({ 'workflow-a': 1 })
    io.fetchDraft
      .mockResolvedValueOnce(draft('workflow-a', 1))
      .mockResolvedValueOnce(draft('workflow-a', 3, 'remote'))
    const fixed = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    fixed.queueGraph(graph('local'))

    await expect(fixed.ensureFreshForCriticalOperation()).resolves.toBe(false)

    expect(fixed.currentGraph.value.nodes[0]?.parameters).toEqual({ value: 'local' })
    expect(fixed.hasConflict.value).toBe(true)
  })

  it('flushes only the active root persistence session', async () => {
    const io = transports({ 'workflow-a': 1, 'workflow-b': 4 })
    const descriptorA = root('workflow:a', 'workflow-a')
    const descriptorB = root('workflow:b', 'workflow-b')
    const a = useCanvasPersistence({
      descriptor: descriptorA,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const b = useCanvasPersistence({
      descriptor: descriptorB,
      getWorkflowId: () => 'workflow-b',
      transports: io,
    })
    const active = useCanvasPersistence()
    a.queueGraph(graph('a'))
    b.queueGraph(graph('b'))
    graphSyncCanvasSessions.activate(descriptorA.canvasId)

    await expect(active.ensureFreshForCriticalOperation()).resolves.toBe(true)

    expect(io.putDraft).toHaveBeenCalledTimes(1)
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.anything())
    expect(b.isPending.value).toBe(true)
  })

  it('does not fall through to a root when no canvas or a nested canvas is active', async () => {
    const io = transports({ 'workflow-a': 1 })
    const descriptor = root('workflow:a', 'workflow-a')
    const rootSession = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    rootSession.queueGraph(graph('a'))
    const active = useCanvasPersistence()

    await expect(active.ensureFreshForCriticalOperation()).resolves.toBe(false)

    const nestedId = canvasIdFromPanelId('sub-workflow:nested')
    graphSyncCanvasSessions.register({
      kind: 'nested',
      canvasId: nestedId,
      sessionId: 'nested',
      parentCanvasId: descriptor.canvasId,
    })
    graphSyncCanvasSessions.activate(nestedId)
    expect(active.canvasId).toBe(nestedId)
    await expect(active.ensureFreshForCriticalOperation()).resolves.toBe(false)

    expect(io.putDraft).not.toHaveBeenCalled()
    expect(rootSession.isPending.value).toBe(true)
  })

  it('unregistering one canvas cancels only its persistence resources', async () => {
    const io = transports({ 'workflow-a': 1, 'workflow-b': 1 })
    const descriptorA = root('workflow:a', 'workflow-a')
    const descriptorB = root('workflow:b', 'workflow-b')
    const a = useCanvasPersistence({
      descriptor: descriptorA,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const b = useCanvasPersistence({
      descriptor: descriptorB,
      getWorkflowId: () => 'workflow-b',
      transports: io,
    })
    a.queueGraph(graph('a'))
    b.queueGraph(graph('b'))

    a.dispose()
    await vi.advanceTimersByTimeAsync(500)

    expect(io.putDraft).toHaveBeenCalledTimes(1)
    expect(io.putDraft).toHaveBeenCalledWith('workflow-b', expect.anything())
    expect(io.writeRecovery).toHaveBeenCalledTimes(1)
    expect(io.writeRecovery).toHaveBeenCalledWith(expect.objectContaining({
      name: 'workflow-b',
    }))
  })
})
