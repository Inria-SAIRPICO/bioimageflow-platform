import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import type { GraphState, WorkflowInfo } from '@/api/types'
import { makeGraph } from '@/test-utils/graphFixtures'
import {
  ROOT_PERSISTENCE_RESOURCE,
  type RootCanvasPersistenceResource,
} from '@/composables/useCanvasPersistence'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'
import { saveRootWorkflowTarget } from '../rootWorkflowSave'

function graph(value: string): GraphState {
  return makeGraph({
    nodes: [{
      type: 'tool',
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
  })
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

function registerPersistence(
  workflowName = 'workflow-a',
  initialGraph = graph('captured'),
) {
  const canvasId = canvasIdFromPanelId(`workflow:${workflowName}`)
  canvasSessionRegistry.register({
    kind: 'root',
    canvasId,
    workflowId: workflowName,
  })
  const resource = {
    canvasId,
    workflowId: ref<string | null>(workflowName),
    acceptedDraftRevision: ref<number | null>(1),
    currentGraph: ref<GraphState>(initialGraph),
    validationResult: ref(null),
    isValidationPending: ref(false),
    validationSyncState: ref<'idle' | 'pending' | 'error'>('idle'),
    isPending: ref(false),
    hasConflict: ref(false),
    persistenceState: ref<'idle' | 'saving' | 'error' | 'conflict'>('idle'),
    persistenceIssue: ref(null),
    queueGraph: vi.fn((next: GraphState) => {
      resource.currentGraph.value = JSON.parse(JSON.stringify(next)) as GraphState
    }),
    queueDraft: vi.fn(),
    queueValidation: vi.fn(),
    flushValidation: vi.fn(async () => {}),
    initializeFromDraft: vi.fn(),
    resolveFromDraft: vi.fn(),
    flush: vi.fn(async () => {}),
    retryPersistence: vi.fn(async () => {}),
    dismissPersistenceIssue: vi.fn(),
    ensureFreshForCriticalOperation: vi.fn(async () => true),
    discardToSaved: vi.fn(),
    dispose: vi.fn(),
  } satisfies RootCanvasPersistenceResource
  canvasSessionRegistry.getOrCreateResource(
    canvasId,
    ROOT_PERSISTENCE_RESOURCE,
    () => resource,
  )
  useUIStore().setCanvasWorkflow(canvasId, workflowName, workflowName)
  return { canvasId, resource }
}

describe('saveRootWorkflowTarget', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    canvasSessionRegistry.dispose()
  })

  it('saves and cleans the exact registered root target', async () => {
    const captured = graph('captured')
    const { canvasId, resource } = registerPersistence('workflow-a', captured)
    const info = {
      id: 'workflow-a',
      name: 'workflow-a',
      display_name: 'Workflow A',
    } as WorkflowInfo
    vi.spyOn(useWorkflowStore(), 'saveWorkflow').mockResolvedValue(info)
    useUIStore().markCanvasDirty(canvasId)

    const result = await saveRootWorkflowTarget({
      canvasId,
      workflowName: 'workflow-a',
    })

    expect(result).toEqual({ status: 'saved', info, graph: captured })
    expect(useWorkflowStore().saveWorkflow).toHaveBeenCalledWith(captured, {
      canvasId,
      workflowName: 'workflow-a',
    })
    expect(resource.queueDraft).toHaveBeenCalledWith(captured)
    expect(resource.flush).toHaveBeenCalledOnce()
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(false)
  })

  it('preserves a newer edit and refuses to close over it', async () => {
    const captured = graph('captured')
    const newer = graph('newer')
    const { canvasId, resource } = registerPersistence('workflow-a', captured)
    const save = deferred<WorkflowInfo>()
    vi.spyOn(useWorkflowStore(), 'saveWorkflow').mockReturnValue(save.promise)

    const resultPromise = saveRootWorkflowTarget({
      canvasId,
      workflowName: 'workflow-a',
    })
    await vi.waitFor(() => expect(useWorkflowStore().saveWorkflow).toHaveBeenCalledOnce())
    resource.currentGraph.value = newer
    save.resolve({
      id: 'workflow-a',
      name: 'workflow-a',
      display_name: 'Workflow A',
    } as WorkflowInfo)

    await expect(resultPromise).resolves.toEqual({ status: 'newer-edit' })
    expect(resource.queueGraph).toHaveBeenCalledWith(newer)
    expect(resource.queueDraft).not.toHaveBeenCalled()
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
  })

  it('preserves an edit that lands between the saved-graph check and draft flush', async () => {
    const captured = graph('captured')
    const newer = graph('newer')
    const { canvasId, resource } = registerPersistence('workflow-a', captured)
    let liveGraph = captured
    let injectNewerGraphOnRead = false
    Object.defineProperty(resource, 'currentGraph', {
      configurable: true,
      value: {
        get value() {
          const result = liveGraph
          if (injectNewerGraphOnRead) {
            injectNewerGraphOnRead = false
            queueMicrotask(() => {
              liveGraph = newer
              useUIStore().markCanvasDirty(canvasId)
            })
          }
          return result
        },
      },
    })
    resource.queueDraft.mockImplementation((next) => {
      liveGraph = next
    })
    resource.queueGraph.mockImplementation((next) => {
      liveGraph = next
    })
    const info = {
      id: 'workflow-a',
      name: 'workflow-a',
      display_name: 'Workflow A',
    } as WorkflowInfo
    vi.spyOn(useWorkflowStore(), 'saveWorkflow').mockImplementation(async () => {
      injectNewerGraphOnRead = true
      return info
    })

    await expect(saveRootWorkflowTarget({
      canvasId,
      workflowName: 'workflow-a',
    })).resolves.toEqual({ status: 'newer-edit' })

    expect(resource.queueDraft).toHaveBeenCalledWith(captured)
    expect(resource.queueGraph).toHaveBeenCalledWith(newer)
    expect(liveGraph).toEqual(newer)
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
  })

  it('reports a freshness conflict without writing the saved artifact', async () => {
    const { canvasId, resource } = registerPersistence()
    resource.ensureFreshForCriticalOperation.mockResolvedValueOnce(false)
    const save = vi.spyOn(useWorkflowStore(), 'saveWorkflow')

    await expect(saveRootWorkflowTarget({
      canvasId,
      workflowName: 'workflow-a',
    })).resolves.toEqual({ status: 'conflict' })

    expect(save).not.toHaveBeenCalled()
  })
})
