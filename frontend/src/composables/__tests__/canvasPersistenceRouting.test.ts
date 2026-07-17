import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { GraphState, ValidationResult } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
  },
}))

import { api } from '@/api/client'
import {
  CanvasDiscardRecoveryCleanupError,
  _resetCanvasPersistenceForTest,
  useCanvasPersistence,
  type CanvasPersistenceTransports,
} from '../useCanvasPersistence'
import {
  canvasIdFromPanelId,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'
import {
  graphSyncCanvasSessions,
  useGraphSync,
} from '../useGraphSync'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'

const mockedApiPut = vi.mocked(api.put)
const mockedApiGet = vi.mocked(api.get)

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
  ) => ({
    ...draft(workflowId, body.expected_revision + 1),
    graph: body.graph,
  }))
  const writeRecovery = vi.fn(async () => {})
  return { fetchDraft, putDraft, writeRecovery }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('canvas persistence routing', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockedApiPut.mockReset()
    mockedApiGet.mockReset()
    _resetCanvasPersistenceForTest()
  })

  afterEach(() => {
    _resetCanvasPersistenceForTest()
    vi.useRealTimers()
  })

  it('uses one validating draft write as root persistence and graph-sync authority', async () => {
    const io = transports({ 'workflow-a': 4 })
    const acceptedValidation = {
      valid: false,
      node_statuses: {},
      errors: [],
    } satisfies ValidationResult
    io.putDraft.mockImplementation(async (
      workflowId: string,
      body: {
        graph: GraphState
        expected_revision: number
        validate?: boolean
      },
    ) => ({
      ...draft(workflowId, body.expected_revision + 1),
      graph: body.graph,
      validation: acceptedValidation,
    }))
    const descriptor = root('workflow:a', 'workflow-a')
    const persistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const sync = useGraphSync({
      descriptor,
      getWorkflowId: () => 'workflow-a',
    })
    const edited = graph('captured')

    persistence.queueGraph(edited)
    edited.nodes[0]!.parameters = { value: 'mutated-after-queue' }

    expect(persistence.persistenceState.value).toBe('saving')
    expect(persistence.persistenceIssue.value).toBeNull()
    expect(sync.currentGraph.value).toEqual(graph('captured'))
    expect(sync.isPending.value).toBe(true)
    await Promise.all([persistence.flush(), sync.flushNow()])

    expect(io.putDraft).toHaveBeenCalledOnce()
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.objectContaining({
      expected_revision: 4,
      graph: graph('captured'),
      validate: true,
    }))
    expect(io.writeRecovery).toHaveBeenCalledOnce()
    expect(mockedApiPut).not.toHaveBeenCalled()
    expect(sync.currentGraph.value).toEqual(graph('captured'))
    expect(sync.validationResult.value).toEqual(acceptedValidation)
    expect(sync.isPending.value).toBe(false)
    expect(persistence.acceptedDraftRevision.value).toBe(5)
    expect(persistence.persistenceState.value).toBe('idle')
    expect(persistence.persistenceIssue.value).toBeNull()
  })

  it('keeps a readable draft failure until retry succeeds or the exact issue is dismissed', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const firstFailure = new Error('offline')
    const secondFailure = new Error('still offline')
    const io = transports({ 'workflow-a': 1 })
    io.putDraft
      .mockRejectedValueOnce(firstFailure)
      .mockRejectedValueOnce(secondFailure)
    const persistence = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    persistence.initializeFromDraft(draft('workflow-a', 1, 'initial'))
    persistence.queueGraph(graph('edited'))

    expect(persistence.persistenceState.value).toBe('saving')
    await expect(persistence.flush()).rejects.toBe(firstFailure)

    expect(persistence.persistenceState.value).toBe('error')
    const firstIssue = persistence.persistenceIssue.value
    expect(firstIssue).toMatchObject({
      version: 1,
      kind: 'error',
      source: 'draft',
      summary: 'Changes could not be saved',
      dismissed: false,
    })
    expect(firstIssue?.detail).toContain('still queued on this canvas')
    expect(firstIssue?.detail).toContain('offline')

    persistence.dismissPersistenceIssue('another-canvas:persistence:1')
    expect(persistence.persistenceIssue.value?.dismissed).toBe(false)
    persistence.dismissPersistenceIssue(firstIssue!.id)
    expect(persistence.persistenceIssue.value?.dismissed).toBe(true)
    expect(persistence.persistenceState.value).toBe('error')

    await expect(persistence.retryPersistence()).rejects.toBe(secondFailure)
    const secondIssue = persistence.persistenceIssue.value
    expect(secondIssue).toMatchObject({
      version: 2,
      kind: 'error',
      source: 'draft',
      dismissed: false,
    })
    expect(secondIssue?.id).not.toBe(firstIssue?.id)

    await expect(persistence.retryPersistence()).resolves.toBeUndefined()
    expect(persistence.persistenceState.value).toBe('idle')
    expect(persistence.persistenceIssue.value).toBeNull()
    warning.mockRestore()
  })

  it('surfaces initialization failure and retries the retained graph', async () => {
    const io = transports({ 'workflow-a': 4 })
    const failure = new Error('draft endpoint unavailable')
    io.fetchDraft
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(draft('workflow-a', 4, 'remote'))
    const persistence = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })

    persistence.queueGraph(graph('local'))
    expect(persistence.persistenceState.value).toBe('saving')
    await expect(persistence.flush()).rejects.toBe(failure)

    expect(persistence.persistenceState.value).toBe('error')
    expect(persistence.persistenceIssue.value).toMatchObject({
      version: 1,
      source: 'initialization',
      dismissed: false,
    })
    expect(persistence.persistenceIssue.value?.detail).toContain(
      'draft endpoint unavailable',
    )

    await expect(persistence.retryPersistence()).resolves.toBeUndefined()
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.objectContaining({
      graph: graph('local'),
      expected_revision: 4,
    }))
    expect(persistence.persistenceState.value).toBe('idle')
    expect(persistence.persistenceIssue.value).toBeNull()
  })

  it('prioritizes conflict over concurrent recovery failure', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const conflict = {
      response: { status: 409, data: { current_revision: 8 } },
    }
    const io = transports({ 'workflow-a': 7 })
    io.putDraft.mockRejectedValueOnce(conflict)
    io.writeRecovery.mockRejectedValueOnce(new Error('indexeddb unavailable'))
    const persistence = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    persistence.initializeFromDraft(draft('workflow-a', 7, 'initial'))
    persistence.queueGraph(graph('local'))

    await expect(persistence.flush()).rejects.toBeDefined()
    await vi.waitFor(() => {
      expect(persistence.persistenceState.value).toBe('conflict')
    })
    expect(persistence.persistenceIssue.value).toMatchObject({
      kind: 'conflict',
      source: 'draft',
      dismissed: false,
    })
    expect(persistence.persistenceIssue.value?.detail).toContain('revision 8')
    warning.mockRestore()
  })

  it('projects the accepted response graph and validation as one authority', async () => {
    const io = transports({ 'workflow-a': 1 })
    const descriptor = root('workflow:a', 'workflow-a')
    const persistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const initial = draft('workflow-a', 1, 'initial')
    persistence.initializeFromDraft(initial)
    const sync = useGraphSync({
      descriptor,
      getWorkflowId: () => 'workflow-a',
    })
    const acceptedGraph = graph('server-normalized')
    const acceptedValidation = {
      valid: false,
      node_statuses: {},
      errors: [],
    } satisfies ValidationResult
    io.putDraft.mockResolvedValueOnce({
      ...draft('workflow-a', 2),
      graph: acceptedGraph,
      validation: acceptedValidation,
    })

    persistence.queueGraph(graph('local-request'))
    await persistence.flush()

    expect(sync.currentGraph.value).toEqual(acceptedGraph)
    expect(sync.validationResult.value).toEqual(acceptedValidation)
  })

  it('acknowledges its exact draft revision for websocket echoes in either ordering', async () => {
    const initial = draft('workflow-a', 1, 'initial')
    mockedApiGet.mockResolvedValueOnce({ data: initial })
    const tracked = useWorkflowDraftStore()
    await tracked.loadDraft('workflow-a')
    const io = transports({ 'workflow-a': 1 })
    const descriptor = root('workflow:a', 'workflow-a')
    const persistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    persistence.initializeFromDraft(initial)
    const first = deferred<WorkflowDraftResponse>()
    io.putDraft.mockReturnValueOnce(first.promise)

    persistence.queueGraph(graph('first'))
    const firstFlush = persistence.flush()
    await vi.advanceTimersByTimeAsync(0)
    tracked.noteRemoteChange({
      type: 'workflow_draft_changed',
      workflow_id: 'workflow-a',
      draft_revision: 2,
      updated_by: 'frontend',
      updated_at: '2026-07-16T01:00:00Z',
      dirty_against_saved: true,
    })
    expect(tracked.remoteAvailableRevision).toBe(2)
    first.resolve({
      ...draft('workflow-a', 2, 'first'),
      graph: graph('first'),
    })
    await firstFlush

    expect(tracked.appliedDraftRevision).toBe(2)
    expect(tracked.remoteAvailableRevision).toBeNull()

    persistence.queueGraph(graph('second'))
    await persistence.flush()
    expect(tracked.appliedDraftRevision).toBe(3)
    tracked.noteRemoteChange({
      type: 'workflow_draft_changed',
      workflow_id: 'workflow-a',
      draft_revision: 3,
      updated_by: 'frontend',
      updated_at: '2026-07-16T01:01:00Z',
      dirty_against_saved: true,
    })
    expect(tracked.remoteAvailableRevision).toBeNull()
  })

  it('joins an in-flight root write and waits for validation of an edit queued during it', async () => {
    const first = deferred<WorkflowDraftResponse>()
    const second = deferred<WorkflowDraftResponse>()
    const io = transports({ 'workflow-a': 1 })
    io.putDraft
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const descriptor = root('workflow:a', 'workflow-a')
    const persistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const initial = draft('workflow-a', 1, 'initial')
    persistence.initializeFromDraft(initial)
    const sync = useGraphSync({
      descriptor,
      getWorkflowId: () => 'workflow-a',
    })

    persistence.queueGraph(graph('old'))
    expect(persistence.persistenceState.value).toBe('saving')
    const persistenceFlush = persistence.flush()
    const graphFlush = sync.flushNow()
    await vi.advanceTimersByTimeAsync(0)
    expect(io.putDraft).toHaveBeenCalledOnce()

    persistence.queueGraph(graph('latest'))
    expect(persistence.persistenceState.value).toBe('saving')
    expect(sync.isPending.value).toBe(true)
    first.resolve({
      ...draft('workflow-a', 2, 'old'),
      graph: graph('old'),
      validation: { valid: false, node_statuses: {}, errors: [] },
    })
    await vi.advanceTimersByTimeAsync(0)

    expect(io.putDraft).toHaveBeenCalledTimes(2)
    expect(sync.validationResult.value).toEqual(initial.validation)
    expect(sync.isPending.value).toBe(true)
    expect(persistence.persistenceState.value).toBe('saving')
    expect(persistence.persistenceIssue.value).toBeNull()
    expect(io.putDraft.mock.calls[1]?.[1]).toEqual(expect.objectContaining({
      graph: graph('latest'),
      expected_revision: 2,
      validate: true,
    }))

    const latestValidation = {
      valid: false,
      node_statuses: {},
      errors: [],
    } satisfies ValidationResult
    second.resolve({
      ...draft('workflow-a', 3, 'latest'),
      graph: graph('latest'),
      validation: latestValidation,
    })
    await Promise.all([persistenceFlush, graphFlush])

    expect(sync.currentGraph.value).toEqual(graph('latest'))
    expect(sync.validationResult.value).toEqual(latestValidation)
    expect(sync.isPending.value).toBe(false)
    expect(persistence.persistenceState.value).toBe('saving')
    await persistence.flush()
    expect(persistence.persistenceState.value).toBe('idle')
    expect(persistence.persistenceIssue.value).toBeNull()
  })

  it('seeds matching draft validation without writing and can force draft-only revalidation', async () => {
    const io = transports({ 'workflow-a': 8 })
    const descriptor = root('workflow:a', 'workflow-a')
    const persistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const seeded = draft('workflow-a', 8, 'seeded')
    seeded.graph.nodes[0]!.parameters = { first: 1, second: 2 }
    persistence.initializeFromDraft(seeded)
    const sync = useGraphSync({
      descriptor,
      getWorkflowId: () => 'workflow-a',
    })

    sync.syncGraphState({
      ...seeded.graph,
      nodes: [{
        ...seeded.graph.nodes[0]!,
        parameters: { second: 2, first: 1 },
      }],
    })
    await sync.flushNow()

    expect(sync.currentGraph.value).toEqual(seeded.graph)
    expect(sync.validationResult.value).toEqual(seeded.validation)
    expect(io.putDraft).not.toHaveBeenCalled()
    expect(io.writeRecovery).not.toHaveBeenCalled()
    expect(mockedApiPut).not.toHaveBeenCalled()

    sync.revalidateGraphState(seeded.graph)
    expect(sync.isPending.value).toBe(true)
    await Promise.all([sync.flushNow(), persistence.flush()])

    expect(io.putDraft).toHaveBeenCalledOnce()
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.objectContaining({
      graph: seeded.graph,
      expected_revision: 8,
      validate: true,
    }))
    expect(io.writeRecovery).not.toHaveBeenCalled()
    expect(mockedApiPut).not.toHaveBeenCalled()

    persistence.queueDraft(seeded.graph)
    await Promise.all([sync.flushNow(), persistence.flush()])
    expect(io.putDraft).toHaveBeenCalledTimes(2)
    expect(io.putDraft).toHaveBeenLastCalledWith(
      'workflow-a',
      expect.objectContaining({
        graph: seeded.graph,
        expected_revision: 9,
        validate: true,
      }),
    )

    await Promise.all([sync.flushNow(), persistence.flush(), persistence.flush()])
    expect(io.putDraft).toHaveBeenCalledTimes(2)
  })

  it('reports root validation errors without hiding unsaved persistence state', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const failure = new Error('draft write failed')
    const io = transports({ 'workflow-a': 3 })
    io.putDraft.mockRejectedValueOnce(failure)
    const descriptor = root('workflow:a', 'workflow-a')
    const persistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const initial = draft('workflow-a', 3, 'initial')
    persistence.initializeFromDraft(initial)
    const sync = useGraphSync({
      descriptor,
      getWorkflowId: () => 'workflow-a',
    })

    sync.revalidateGraphState(initial.graph)
    expect(sync.isPending.value).toBe(true)
    expect(sync.syncState.value).toBe('pending')
    await expect(sync.flushNow()).rejects.toBe(failure)

    expect(sync.isPending.value).toBe(false)
    expect(sync.syncState.value).toBe('error')
    expect(sync.validationResult.value).toEqual(initial.validation)
    expect(persistence.isPending.value).toBe(true)
    expect(io.writeRecovery).not.toHaveBeenCalled()
    expect(warning).toHaveBeenCalledWith(
      '[canvas-persistence] Failed to save workflow draft:',
      failure,
    )
    warning.mockRestore()
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

  it('fences draft and recovery writes before resetting a discarded graph to saved', async () => {
    const draftWrite = deferred<WorkflowDraftResponse>()
    const recoveryWrite = deferred<void>()
    const clearRecovery = deferred<void>()
    const io = {
      ...transports({ 'workflow-a': 1 }),
      resetDraftToSaved: vi.fn(async (workflowId: string, expectedRevision: number) => ({
        ...draft(workflowId, expectedRevision + 1, 'saved'),
        dirty_against_saved: false,
      })),
      clearRecovery: vi.fn(() => clearRecovery.promise),
    }
    io.putDraft.mockReturnValueOnce(draftWrite.promise)
    io.writeRecovery.mockReturnValueOnce(recoveryWrite.promise)
    const fixed = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    useWorkflowDraftStore().trackWorkflow('workflow-a')
    fixed.initializeFromDraft(draft('workflow-a', 1, 'saved'))
    fixed.queueGraph(graph('discard-me'))

    const discard = fixed.discardToSaved()
    await vi.waitFor(() => {
      expect(io.putDraft).toHaveBeenCalledOnce()
      expect(io.writeRecovery).toHaveBeenCalledOnce()
    })
    expect(io.resetDraftToSaved).not.toHaveBeenCalled()

    draftWrite.resolve(draft('workflow-a', 2, 'discard-me'))
    recoveryWrite.resolve()
    await vi.waitFor(() => expect(io.resetDraftToSaved).toHaveBeenCalledWith(
      'workflow-a',
      2,
    ))
    expect(io.clearRecovery).toHaveBeenCalledWith('workflow-a')
    let settled = false
    void discard.then(() => { settled = true })
    await Promise.resolve()
    expect(settled).toBe(false)

    clearRecovery.resolve()
    const accepted = await discard
    expect(accepted.graph).toEqual(graph('saved'))
    expect(accepted.dirty_against_saved).toBe(false)
    expect(fixed.currentGraph.value).toEqual(graph('saved'))
    expect(fixed.acceptedDraftRevision.value).toBe(3)
  })

  it('rejects discard when strict recovery cleanup fails', async () => {
    const cleanupFailure = new Error('IndexedDB clear failed')
    let clearAttempt = 0
    const io = {
      ...transports({ 'workflow-a': 1 }),
      resetDraftToSaved: vi.fn(async (workflowId: string, expectedRevision: number) => ({
        ...draft(workflowId, expectedRevision + 1, 'saved'),
        dirty_against_saved: false,
      })),
      clearRecovery: vi.fn(async () => {
        clearAttempt += 1
        if (clearAttempt === 1) throw cleanupFailure
      }),
    }
    const fixed = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    fixed.initializeFromDraft(draft('workflow-a', 1, 'saved'))
    fixed.queueGraph(graph('discard-me'))

    let failedDiscard: unknown
    try {
      await fixed.discardToSaved()
    } catch (error) {
      failedDiscard = error
    }

    expect(failedDiscard).toBeInstanceOf(CanvasDiscardRecoveryCleanupError)
    expect((failedDiscard as CanvasDiscardRecoveryCleanupError).draft.graph)
      .toEqual(graph('saved'))
    expect(io.clearRecovery).toHaveBeenCalledWith('workflow-a')
    expect(fixed.currentGraph.value).toEqual(graph('saved'))
    expect(fixed.acceptedDraftRevision.value).toBe(3)

    await expect(fixed.discardToSaved()).resolves.toMatchObject({
      draft_revision: 4,
      graph: graph('saved'),
    })
    expect(io.resetDraftToSaved.mock.calls.map(call => call[1])).toEqual([2, 3])
  })

  it('keeps the local graph and records a newer authority when discard loses CAS', async () => {
    const conflict = { response: { status: 409, data: { current_revision: 4 } } }
    const io = {
      ...transports({ 'workflow-a': 1 }),
      resetDraftToSaved: vi.fn().mockRejectedValue(conflict),
      clearRecovery: vi.fn(async () => {}),
    }
    const fixed = useCanvasPersistence({
      descriptor: root('workflow:a', 'workflow-a'),
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    useWorkflowDraftStore().trackWorkflow('workflow-a')
    fixed.initializeFromDraft(draft('workflow-a', 1, 'saved'))
    fixed.queueGraph(graph('local'))
    await fixed.flush()
    io.fetchDraft.mockResolvedValueOnce({
      ...draft('workflow-a', 4, 'remote'),
      updated_by: 'agent',
    })

    await expect(fixed.discardToSaved()).rejects.toBe(conflict)

    expect(fixed.currentGraph.value).toEqual(graph('local'))
    expect(fixed.hasConflict.value).toBe(true)
    expect(io.clearRecovery).not.toHaveBeenCalled()
    expect(useWorkflowDraftStore().remoteAvailableRevision).toBe(4)
  })

  it('does not overwrite a newer server draft from an older opened draft snapshot', async () => {
    const io = transports({ 'workflow-a': 2 })
    io.fetchDraft.mockResolvedValueOnce(draft('workflow-a', 2, 'remote-newer'))
    const descriptor = root('workflow:a', 'workflow-a')
    const persistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'workflow-a',
      transports: io,
    })
    const opened = draft('workflow-a', 1, 'opened')
    persistence.initializeFromDraft(opened)
    const sync = useGraphSync({
      descriptor,
      getWorkflowId: () => 'workflow-a',
    })

    sync.syncGraphState(opened.graph)
    await sync.flushNow()

    expect(io.fetchDraft).not.toHaveBeenCalled()
    expect(io.putDraft).not.toHaveBeenCalled()
    await expect(persistence.ensureFreshForCriticalOperation()).resolves.toBe(false)
    expect(io.fetchDraft).toHaveBeenCalledOnce()
    expect(io.putDraft).not.toHaveBeenCalled()
    expect(persistence.hasConflict.value).toBe(true)
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

  it('keeps feedback isolated by canonical canvas and routes the active facade', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const failure = new Error('workflow-a offline')
    const heldB = deferred<WorkflowDraftResponse>()
    const io = transports({ 'workflow-a': 1, 'workflow-b': 5 })
    io.putDraft.mockImplementation((workflowId: string) => {
      if (workflowId === 'workflow-a') return Promise.reject(failure)
      return heldB.promise
    })
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
    a.initializeFromDraft(draft('workflow-a', 1, 'initial-a'))
    b.initializeFromDraft(draft('workflow-b', 5, 'initial-b'))
    const active = useCanvasPersistence()

    a.queueGraph(graph('edited-a'))
    b.queueGraph(graph('edited-b'))
    const flushA = expect(a.flush()).rejects.toBe(failure)
    const flushB = b.flush()
    await vi.advanceTimersByTimeAsync(0)
    await flushA

    expect(a.persistenceState.value).toBe('error')
    expect(a.persistenceIssue.value?.id).toContain('workflow:a')
    expect(b.persistenceState.value).toBe('saving')
    expect(b.persistenceIssue.value).toBeNull()

    graphSyncCanvasSessions.activate(descriptorA.canvasId)
    expect(active.persistenceState.value).toBe('error')
    expect(active.persistenceIssue.value?.id).toBe(a.persistenceIssue.value?.id)
    active.dismissPersistenceIssue(a.persistenceIssue.value!.id)
    expect(a.persistenceIssue.value?.dismissed).toBe(true)

    graphSyncCanvasSessions.activate(descriptorB.canvasId)
    expect(active.persistenceState.value).toBe('saving')
    expect(active.persistenceIssue.value).toBeNull()

    heldB.resolve({
      ...draft('workflow-b', 6, 'edited-b'),
      graph: graph('edited-b'),
    })
    await flushB
    expect(b.persistenceState.value).toBe('idle')
    expect(a.persistenceState.value).toBe('error')
    warning.mockRestore()
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

    expect(active.persistenceState.value).toBe('saving')
    expect(active.persistenceIssue.value).toBeNull()

    await expect(active.ensureFreshForCriticalOperation()).resolves.toBe(true)

    expect(active.persistenceState.value).toBe('idle')
    expect(io.putDraft).toHaveBeenCalledTimes(1)
    expect(io.putDraft).toHaveBeenCalledWith('workflow-a', expect.anything())
    expect(b.isPending.value).toBe(true)
    graphSyncCanvasSessions.activate(descriptorB.canvasId)
    expect(active.persistenceState.value).toBe('saving')
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

    expect(active.persistenceState.value).toBe('idle')
    expect(active.persistenceIssue.value).toBeNull()
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
    expect(active.persistenceState.value).toBe('idle')
    expect(active.persistenceIssue.value).toBeNull()
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
