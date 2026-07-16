import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useWebSocket, __resetForTests } from '@/composables/useWebSocket'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'

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
