import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useWebSocket, __resetForTests } from '@/composables/useWebSocket'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { useExecutionStore } from '@/stores/execution'
import { useNapariStore } from '@/stores/napari'
import { api } from '@/api/client'

const EXECUTION_CONTEXT = {
  execution_id: 'exec-websocket',
  workflow_id: 'websocket-workflow',
  draft_revision: 8,
} as const

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: FakeWebSocket[] = []

  readonly readyState = FakeWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this)
  }

  send = vi.fn()
  close = vi.fn()
}

describe('useWebSocket workflow draft dispatch', () => {
  const realWebSocket = globalThis.WebSocket

  beforeEach(() => {
    setActivePinia(createPinia())
    FakeWebSocket.instances = []
    globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket
    __resetForTests()
  })

  afterEach(() => {
    vi.useRealTimers()
    __resetForTests()
    globalThis.WebSocket = realWebSocket
    vi.restoreAllMocks()
  })

  it('dispatches workflow_draft_changed messages to the workflow draft store', () => {
    const draft = useWorkflowDraftStore()
    draft.reset('wf')
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'workflow_draft_changed',
        workflow_id: 'wf',
        draft_revision: 8,
        updated_by: 'agent',
        updated_at: '2026-05-21T12:08:00Z',
        dirty_against_saved: true,
      }),
    } as MessageEvent)

    expect(draft.remoteAvailableRevision).toBe(8)
    expect(draft.remoteUpdatedBy).toBe('agent')
    expect(draft.remoteUpdatedAt).toBe('2026-05-21T12:08:00Z')
    expect(draft.remoteDirtyAgainstSaved).toBe(true)
  })

  it('retains an inactive workflow draft message until that workflow is tracked', () => {
    const draft = useWorkflowDraftStore()
    draft.reset('workflow-a')
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'workflow_draft_changed',
        workflow_id: 'workflow-b',
        draft_revision: 9,
        updated_by: 'agent',
        updated_at: '2026-05-21T12:09:00Z',
        dirty_against_saved: false,
      }),
    } as MessageEvent)

    expect(draft.remoteAvailableRevision).toBeNull()
    draft.trackWorkflow('workflow-b')
    expect(draft.remoteAvailableRevision).toBe(9)
    expect(draft.remoteUpdatedBy).toBe('agent')
    expect(draft.remoteUpdatedAt).toBe('2026-05-21T12:09:00Z')
    expect(draft.remoteDirtyAgainstSaved).toBe(false)
  })

  it('dispatches progress, node state, and completion with one execution context', () => {
    const execution = useExecutionStore()
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    for (const message of [
      {
        type: 'node_state',
        ...EXECUTION_CONTEXT,
        node_id: 'node-1',
        status: 'running',
        cached: false,
      },
      {
        type: 'progress',
        ...EXECUTION_CONTEXT,
        node_id: 'node-1',
        status: 'row_progress',
        row: 2,
        total_rows: 5,
        timestamp: 1,
      },
      {
        type: 'execution_complete',
        ...EXECUTION_CONTEXT,
        success: true,
        errors: [],
        node_statuses: {
          'node-1': { node_id: 'node-1', status: 'executed', cached: false },
        },
      },
    ]) {
      FakeWebSocket.instances[0]!.onmessage?.({
        data: JSON.stringify(message),
      } as MessageEvent)
    }

    expect(execution.executionId).toBe(EXECUTION_CONTEXT.execution_id)
    expect(execution.executionWorkflowId).toBe(EXECUTION_CONTEXT.workflow_id)
    expect(execution.executionDraftRevision).toBe(EXECUTION_CONTEXT.draft_revision)
    expect(execution.state).toBe('idle')
    expect(execution.lastResult?.success).toBe(true)
    expect(execution.nodeStatuses['node-1']?.status).toBe('executed')
  })

  it('rejects contextless execution events while a contextual run is active', () => {
    const execution = useExecutionStore()
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')
    const receive = (message: Record<string, unknown>) => {
      FakeWebSocket.instances[0]!.onmessage?.({
        data: JSON.stringify(message),
      } as MessageEvent)
    }

    receive({
      type: 'node_state',
      ...EXECUTION_CONTEXT,
      node_id: 'node-1',
      status: 'running',
      cached: false,
    })
    receive({
      type: 'node_state',
      node_id: 'unscoped',
      status: 'failed',
      cached: false,
    })
    receive({
      type: 'progress',
      node_id: 'unscoped',
      status: 'row_progress',
      row: 1,
      total_rows: 2,
      timestamp: 1,
    })
    receive({
      type: 'execution_complete',
      success: true,
      errors: [],
      node_statuses: {},
    })

    expect(execution.executionId).toBe(EXECUTION_CONTEXT.execution_id)
    expect(execution.state).toBe('running')
    expect(execution.nodeStatuses.unscoped).toBeUndefined()
    expect(execution.progress).toBeNull()
    expect(execution.lastResult).toBeNull()
  })

  it('dispatches tool_reload and tool_removed messages to the tool registry store', () => {
    const registry = useToolRegistryStore()
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'tool_reload',
        tool_name: 'CustomTool',
        tool_metadata: {
          name: 'CustomTool',
          display_name: 'Custom Tool',
          package: '__custom__',
          package_version: 'local',
          tool_type: 'ProcessingTool',
          inputs: {},
          outputs: {},
          tags: [],
          categories: [],
          source_kind: 'custom',
          editable: true,
        },
      }),
    } as MessageEvent)

    expect(registry.getToolByName('CustomTool')?.editable).toBe(true)

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'tool_removed',
        tool_name: 'CustomTool',
      }),
    } as MessageEvent)

    expect(registry.getToolByName('CustomTool')).toBeUndefined()
  })

  it('routes Napari launch status to progress and Logger activation state', () => {
    const napari = useNapariStore()
    napari.requestPending = true
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'environment_status',
        env_name: 'napari',
        status: 'opening',
      }),
    } as MessageEvent)

    expect(napari.phase).toBe('opening')
    expect(napari.loggerActivationRequest).toBe(1)
  })

  it('refreshes the workflow tree for workflow_tree_changed messages', async () => {
    const workflow = useWorkflowStore()
    const fetchWorkflowTree = vi.spyOn(workflow, 'fetchWorkflowTree')
      .mockResolvedValue([])
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'workflow_tree_changed',
        action: 'workflow_created',
        workflow_id: 'wf',
      }),
    } as MessageEvent)
    await Promise.resolve()

    expect(fetchWorkflowTree).toHaveBeenCalledOnce()
  })

  it('invalidates an older list response for an unversioned folder structural event', async () => {
    const staleResponse = deferred<any>()
    const get = vi.spyOn(api, 'get')
      .mockReturnValueOnce(staleResponse.promise)
      .mockResolvedValueOnce({
        data: [{
          id: 'kept',
          name: 'kept',
          folder: '',
          display_name: 'Kept',
          path: '/tmp/kept/workflow.json',
          last_modified: '2026-07-16T10:00:00Z',
      identity_generation: 0,
        }],
      })
    const workflow = useWorkflowStore()
    const fetchWorkflowTree = vi.spyOn(workflow, 'fetchWorkflowTree')
      .mockResolvedValue([])
    const refresh = workflow.fetchWorkflows()
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'workflow_tree_changed',
        action: 'folder_moved',
      }),
    } as MessageEvent)
    staleResponse.resolve({
      data: [{
        id: 'stale',
        name: 'stale',
        folder: 'Deleted folder',
        display_name: 'Stale',
        path: '/tmp/stale/workflow.json',
        last_modified: '2026-07-16T09:00:00Z',
      identity_generation: 0,
      }],
    })
    await refresh

    expect(fetchWorkflowTree).toHaveBeenCalledOnce()
    expect(get).toHaveBeenCalledTimes(2)
    expect(workflow.workflows.map(item => item.id ?? item.name)).toEqual(['kept'])
  })

  it('routes remote workflow deletion through the canonical removal lifecycle', async () => {
    vi.spyOn(useWorkflowStore(), 'fetchWorkflowTree').mockResolvedValue([])
    const removed = vi.fn()
    window.addEventListener('bioimageflow:workflow-removed', removed)
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'workflow_tree_changed',
        action: 'workflow_deleted',
        workflow_id: 'folder/wf',
        identity_generation: 7,
      }),
    } as MessageEvent)
    await Promise.resolve()

    expect(removed).toHaveBeenCalledOnce()
    expect((removed.mock.calls[0]![0] as CustomEvent).detail).toEqual({
      workflowName: 'folder/wf',
      identityGeneration: 7,
    })
    window.removeEventListener('bioimageflow:workflow-removed', removed)
  })

  it('ignores a delayed deletion event older than a recreated identity', async () => {
    const workflow = useWorkflowStore()
    const fetchWorkflowTree = vi.spyOn(workflow, 'fetchWorkflowTree')
      .mockResolvedValue([])
    const removed = vi.fn()
    window.addEventListener('bioimageflow:workflow-removed', removed)
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'workflow_tree_changed',
        action: 'workflow_created',
        workflow_id: 'wf',
        identity_generation: 12,
      }),
    } as MessageEvent)
    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'workflow_tree_changed',
        action: 'workflow_deleted',
        workflow_id: 'wf',
        identity_generation: 11,
      }),
    } as MessageEvent)
    await Promise.resolve()

    expect(fetchWorkflowTree).toHaveBeenCalledOnce()
    expect(removed).not.toHaveBeenCalled()
    window.removeEventListener('bioimageflow:workflow-removed', removed)
  })

  it('preserves the durable server generation across WebSocket reconnects', () => {
    const workflow = useWorkflowStore()
    workflow.observeWorkflowServerIdentityGeneration('wf', 12)
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onopen?.(new Event('open'))

    expect(workflow.workflowServerIdentityGeneration('wf')).toBe(12)
    expect(workflow.observeWorkflowServerIdentityGeneration('wf', 0)).toBe(false)
    expect(workflow.workflowServerIdentityGeneration('wf')).toBe(12)
  })

  it('refreshes and publishes workflow identities after reconnect', async () => {
    vi.useFakeTimers()
    const workflow = useWorkflowStore()
    workflow.observeWorkflowServerIdentityGeneration('wf', 12)
    const fetchWorkflowTree = vi.spyOn(workflow, 'fetchWorkflowTree')
      .mockImplementation(async () => {
        workflow.observeWorkflowServerIdentityGeneration('wf', 12)
        workflow.workflows = [{
          id: 'wf',
          name: 'wf',
          display_name: 'Workflow',
          identity_generation: 12,
        }] as any
        return []
      })
    vi.spyOn(useToolRegistryStore(), 'fetchTools').mockResolvedValue(undefined)
    const refreshed = vi.fn()
    window.addEventListener('bioimageflow:workflow-identities-refreshed', refreshed)
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')
    FakeWebSocket.instances[0]!.onclose?.(new CloseEvent('close'))

    await vi.advanceTimersByTimeAsync(1000)
    FakeWebSocket.instances[1]!.onopen?.(new Event('open'))
    await Promise.resolve()
    await Promise.resolve()

    expect(fetchWorkflowTree).toHaveBeenCalledOnce()
    expect((refreshed.mock.calls[0]![0] as CustomEvent).detail).toEqual({
      workflows: [{ workflowName: 'wf', identityGeneration: 12 }],
    })
    window.removeEventListener('bioimageflow:workflow-identities-refreshed', refreshed)
    vi.useRealTimers()
  })

  it('refreshes workflows and requests existing open behavior for active workflow changes', async () => {
    const workflow = useWorkflowStore()
    const fetchWorkflowTree = vi.spyOn(workflow, 'fetchWorkflowTree')
      .mockResolvedValue([])
    const commandListener = vi.fn()
    window.addEventListener('bioimageflow:workflow-command', commandListener)
    const ws = useWebSocket()
    ws.connect('ws://example.test/ws')

    FakeWebSocket.instances[0]!.onmessage?.({
      data: JSON.stringify({
        type: 'active_workflow_changed',
        workflow_id: 'folder/wf',
        updated_by: 'agent',
      }),
    } as MessageEvent)
    await Promise.resolve()
    await Promise.resolve()

    expect(fetchWorkflowTree).toHaveBeenCalledOnce()
    expect(commandListener).toHaveBeenCalledOnce()
    expect((commandListener.mock.calls[0]?.[0] as CustomEvent).detail).toEqual({
      action: 'open',
      name: 'folder/wf',
    })

    window.removeEventListener('bioimageflow:workflow-command', commandListener)
  })
})
