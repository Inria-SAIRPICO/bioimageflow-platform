import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GraphState, ValidationResult } from '@/api/types'
import { canvasIdFromPanelId } from '../canvasSessionRegistry'
import {
  CanvasSessionDisposedError,
  createGraphSyncCoordinator,
  type GraphSyncRequest,
} from '../graphSyncCoordinator'

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

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('graph sync coordinator', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('captures canvas, workflow, graph, and revision when work is queued', async () => {
    const requests: GraphSyncRequest[] = []
    const transport = vi.fn(async (request: GraphSyncRequest) => {
      requests.push(request)
      return validation(request.workflowId === 'workflow-a')
    })
    const a = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'workflow-a',
      transport,
    })
    const b = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:b'),
      workflowId: 'workflow-b',
      transport,
    })

    const graphA = graph('a')
    a.queue(graphA, { semanticRevision: 4 })
    b.queue(graph('b'), { semanticRevision: 9 })
    graphA.nodes[0]!.parameters = { value: 'mutated-after-queue' }
    await Promise.all([a.flushLatest(), b.flushLatest()])

    expect(requests).toEqual(expect.arrayContaining([
      expect.objectContaining({
        canvasId: canvasIdFromPanelId('workflow:a'),
        workflowId: 'workflow-a',
        semanticRevision: 4,
        graph: expect.objectContaining({
          nodes: [expect.objectContaining({ parameters: { value: 'a' } })],
        }),
      }),
      expect.objectContaining({
        canvasId: canvasIdFromPanelId('workflow:b'),
        workflowId: 'workflow-b',
        semanticRevision: 9,
        graph: expect.objectContaining({
          nodes: [expect.objectContaining({ parameters: { value: 'b' } })],
        }),
      }),
    ]))
    expect(a.validationResult.value?.valid).toBe(true)
    expect(b.validationResult.value?.valid).toBe(false)
  })

  it('samples the owning workflow getter when each graph is queued', async () => {
    const requests: GraphSyncRequest[] = []
    let owningWorkflowId: string | null = 'workflow-a'
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('canvas:a'),
      workflowId: 'stale-initial-workflow',
      getWorkflowId: () => owningWorkflowId,
      transport: vi.fn(async (request: GraphSyncRequest) => {
        requests.push(request)
        return validation(true)
      }),
    })

    coordinator.queue(graph('queued-for-a'))
    owningWorkflowId = 'workflow-b'
    await coordinator.flushLatest()

    expect(requests).toHaveLength(1)
    expect(requests[0]).toMatchObject({
      canvasId: canvasIdFromPanelId('canvas:a'),
      workflowId: 'workflow-a',
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'queued-for-a' } })],
      }),
    })

    owningWorkflowId = null
    coordinator.queue(graph('queued-without-owner'))
    owningWorkflowId = 'assigned-after-queue'
    await coordinator.flushLatest()

    expect(requests[1]).toMatchObject({
      workflowId: null,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'queued-without-owner' } })],
      }),
    })
  })

  it('is pending for the entire debounce interval', () => {
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport: vi.fn(async () => validation(true)),
    })

    coordinator.queue(graph('queued'))

    expect(coordinator.isPending.value).toBe(true)
    expect(coordinator.syncState.value).toBe('pending')
  })

  it('flushLatest joins an old request and then sends the newest revision', async () => {
    const first = deferred<ValidationResult>()
    const second = deferred<ValidationResult>()
    const transport = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport,
    })

    coordinator.queue(graph('old'), { semanticRevision: 1 })
    await vi.advanceTimersByTimeAsync(300)
    expect(transport).toHaveBeenCalledTimes(1)

    coordinator.queue(graph('new'), { semanticRevision: 2 })
    const flush = coordinator.flushLatest()
    expect(transport).toHaveBeenCalledTimes(1)

    first.resolve(validation(false))
    await vi.advanceTimersByTimeAsync(0)
    expect(transport).toHaveBeenCalledTimes(2)
    expect(coordinator.validationResult.value).toBeNull()
    expect(coordinator.isPending.value).toBe(true)
    expect(transport.mock.calls[1]?.[0]).toMatchObject({
      semanticRevision: 2,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'new' } })],
      }),
    })

    second.resolve(validation(true))
    await expect(flush).resolves.toMatchObject({ semanticRevision: 2 })
    expect(coordinator.validationResult.value).toEqual(validation(true))
    expect(coordinator.isPending.value).toBe(false)
  })

  it('rejects an operational failure and can retry the same latest snapshot', async () => {
    const failure = new Error('offline')
    const recovery = deferred<ValidationResult>()
    const transport = vi.fn()
      .mockResolvedValueOnce(validation(false))
      .mockRejectedValueOnce(failure)
      .mockReturnValueOnce(recovery.promise)
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport,
    })

    coordinator.queue(graph('accepted'), { semanticRevision: 1 })
    await coordinator.flushLatest()
    const previousValidation = coordinator.validationResult.value

    coordinator.queue(graph('retry'), { semanticRevision: 7 })
    await expect(coordinator.flushLatest()).rejects.toBe(failure)
    expect(coordinator.syncState.value).toBe('error')
    expect(coordinator.lastError.value).toBe(failure)
    expect(coordinator.validationResult.value).toEqual(previousValidation)
    expect(coordinator.currentGraph.value.nodes[0]?.parameters).toEqual({ value: 'retry' })

    const recoveryFlush = coordinator.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    expect(coordinator.isPending.value).toBe(true)
    expect(coordinator.syncState.value).toBe('pending')
    expect(coordinator.lastError.value).toBe(failure)
    recovery.resolve(validation(true))
    await expect(recoveryFlush).resolves.toMatchObject({
      semanticRevision: 7,
      validation: validation(true),
    })
    expect(transport).toHaveBeenCalledTimes(3)
    expect(coordinator.syncState.value).toBe('idle')
    expect(coordinator.lastError.value).toBeNull()
  })

  it('holds a conflict without replaying its stale request and resumes the latest graph explicitly', async () => {
    const conflict = { kind: 'revision-conflict' }
    const transport = vi.fn()
      .mockRejectedValueOnce(conflict)
      .mockResolvedValueOnce(validation(true))
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport,
      isConflict: error => error === conflict,
    })

    coordinator.queue(graph('stale'))
    await expect(coordinator.flushLatest()).rejects.toBe(conflict)

    expect(coordinator.syncState.value).toBe('conflict')
    expect(coordinator.isPending.value).toBe(true)
    expect(coordinator.lastError.value).toBe(conflict)
    await expect(coordinator.flushLatest()).rejects.toBe(conflict)
    expect(transport).toHaveBeenCalledOnce()

    coordinator.queue(graph('latest'))
    await vi.advanceTimersByTimeAsync(1_000)
    expect(coordinator.syncState.value).toBe('conflict')
    expect(coordinator.lastError.value).toBe(conflict)
    expect(transport).toHaveBeenCalledOnce()

    expect(coordinator.resumeAfterConflict()).toBe(true)
    await expect(coordinator.flushLatest()).resolves.toMatchObject({
      semanticRevision: 2,
      graph: graph('latest'),
    })
    expect(transport).toHaveBeenCalledTimes(2)
    expect(transport.mock.calls[1]?.[0]).toMatchObject({
      semanticRevision: 2,
      graph: graph('latest'),
    })
    expect(coordinator.syncState.value).toBe('idle')
    expect(coordinator.isPending.value).toBe(false)
    expect(coordinator.lastError.value).toBeNull()
  })

  it('shares one serialized drain between concurrent flush callers', async () => {
    const held = deferred<ValidationResult>()
    const transport = vi.fn(() => held.promise)
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport,
    })
    coordinator.queue(graph('shared'))

    const first = coordinator.flushLatest()
    const second = coordinator.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    expect(transport).toHaveBeenCalledOnce()

    held.resolve(validation(true))
    const [firstResult, secondResult] = await Promise.all([first, second])
    expect(firstResult).toEqual(secondResult)
    expect(firstResult).toMatchObject({ semanticRevision: 1 })
  })

  it('catches and reports a failed background debounce drain', async () => {
    const failure = new Error('background offline')
    const onOperationalError = vi.fn()
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport: vi.fn().mockRejectedValue(failure),
      onOperationalError,
    })

    coordinator.queue(graph('background'))
    await vi.advanceTimersByTimeAsync(300)

    expect(onOperationalError).toHaveBeenCalledWith(
      failure,
      expect.objectContaining({ workflowId: 'a', semanticRevision: 1 }),
    )
    expect(coordinator.syncState.value).toBe('error')
    expect(coordinator.lastError.value).toBe(failure)

    coordinator.queue(graph('newer'))

    expect(coordinator.lastError.value).toBeNull()
    coordinator.dispose()
  })

  it('continues with a newer revision when the superseded request fails', async () => {
    const oldRequest = deferred<ValidationResult>()
    const onOperationalError = vi.fn()
    const transport = vi.fn()
      .mockReturnValueOnce(oldRequest.promise)
      .mockResolvedValueOnce(validation(true))
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport,
      onOperationalError,
    })

    coordinator.queue(graph('old'), { semanticRevision: 1 })
    await vi.advanceTimersByTimeAsync(300)
    coordinator.queue(graph('new'), { semanticRevision: 2 })
    await vi.advanceTimersByTimeAsync(300)

    const oldFailure = new Error('old request failed')
    oldRequest.reject(oldFailure)
    await vi.advanceTimersByTimeAsync(0)

    expect(transport).toHaveBeenCalledTimes(2)
    expect(transport.mock.calls[1]?.[0]).toMatchObject({
      semanticRevision: 2,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'new' } })],
      }),
    })
    expect(coordinator.acceptedRevision.value).toBe(2)
    expect(coordinator.validationResult.value).toEqual(validation(true))
    expect(coordinator.isPending.value).toBe(false)
    expect(coordinator.lastError.value).toBeNull()
    expect(onOperationalError).not.toHaveBeenCalled()
  })

  it('disposing one coordinator rejects its work without affecting another', async () => {
    const held = deferred<ValidationResult>()
    const a = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport: vi.fn(() => held.promise),
    })
    const b = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:b'),
      workflowId: 'b',
      transport: vi.fn(async () => validation(true)),
    })

    a.queue(graph('a'))
    const flushingA = a.flushLatest()
    b.queue(graph('b'))
    a.dispose()

    await expect(flushingA).rejects.toBeInstanceOf(CanvasSessionDisposedError)
    held.resolve(validation(false))
    await vi.advanceTimersByTimeAsync(0)
    expect(a.validationResult.value).toBeNull()
    await expect(b.flushLatest()).resolves.toMatchObject({ validation: validation(true) })
    expect(b.syncState.value).toBe('idle')
  })

  it('disposal cancels a queued debounce before transport starts', async () => {
    const transport = vi.fn(async () => validation(true))
    const coordinator = createGraphSyncCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'a',
      transport,
    })

    coordinator.queue(graph('queued'))
    coordinator.dispose()
    await vi.advanceTimersByTimeAsync(300)

    expect(transport).not.toHaveBeenCalled()
    await expect(coordinator.flushLatest()).rejects.toBeInstanceOf(
      CanvasSessionDisposedError,
    )
  })
})
