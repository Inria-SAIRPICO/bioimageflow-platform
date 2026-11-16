import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, watch } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import type { DockviewApi, DockviewReadyEvent } from 'dockview-vue'
import type { AddPanelOptions, IDockviewPanel } from 'dockview-core'
import type { RootWorkflowPresentation } from '@/services/rootWorkflowPresentation'
import { makeGraph } from '@/test-utils/graphFixtures'
import { canvasIdFromPanelId, canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'
import { useSettingsStore } from '@/stores/settings'
import { api } from '@/api/client'
import { ROOT_PERSISTENCE_RESOURCE } from '@/composables/useCanvasPersistence'
import { useAutoSave, writeAutoSaveEntry } from '@/composables/useAutoSave'
import { requestWorkflowDeletion } from '@/services/workflowDeletion'
import type { WorkflowInfo } from '@/api/types'

const startup = vi.hoisted(() => ({ resolve: vi.fn() }))
vi.mock('@/services/startupWorkflow', () => ({ resolveStartupWorkflow: startup.resolve }))
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({ connect: vi.fn(), disconnect: vi.fn() }),
}))
import App from '@/App.vue'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(accept => { resolve = accept })
  return { promise, resolve }
}

function presentation(): RootWorkflowPresentation {
  return {
    graph: makeGraph(), workflowName: 'analysis', workflowDisplayName: 'Analysis',
    missingTools: [], dirty: false, identityGeneration: 0, serverIdentityGeneration: null,
  }
}

function dockview() {
  const panels = new Map<string, IDockviewPanel>()
  let active: IDockviewPanel | undefined
  let onActivation: ((panel: IDockviewPanel) => void) | undefined
  const dispose = vi.fn()
  const addPanel = vi.fn((options: AddPanelOptions) => {
    const reference = options.position && 'referencePanel' in options.position
      ? panels.get(String(options.position.referencePanel))
      : undefined
    const group = options.position?.direction === 'within' && reference
      ? reference.group
      : { panels: [] as IDockviewPanel[] }
    const panel = {
      id: options.id, params: options.params, group,
      api: { setTitle: vi.fn(), setActive: vi.fn(() => {
        if (active === panel) return
        active = panel
        onActivation?.(panel)
      }) },
    } as unknown as IDockviewPanel
    const index = options.position && 'index' in options.position ? options.position.index : undefined
    group.panels.splice(index ?? group.panels.length, 0, panel)
    if (options.id.startsWith('workflow:')) {
      canvasSessionRegistry.register({
        kind: 'root', canvasId: canvasIdFromPanelId(options.id), workflowId: options.id.slice(9),
      })
    }
    panels.set(panel.id, panel)
    return panel
  })
  const api = {
    addPanel,
    getPanel: (id: string) => panels.get(id),
    removePanel: (panel: IDockviewPanel) => {
      panel.group.panels.splice(panel.group.panels.indexOf(panel), 1)
      panels.delete(panel.id)
    },
    onDidRemovePanel: () => ({ dispose }),
    onDidActivePanelChange: (listener: (panel: IDockviewPanel) => void) => {
      onActivation = listener
      return { dispose }
    },
  } as unknown as DockviewApi
  return { api, panels, addPanel, dispose, active: () => active }
}

const wrappers: ReturnType<typeof shallowMount>[] = []
function mountShell() {
  const wrapper = shallowMount(App, { global: { plugins: [createPinia(), PrimeVue] } })
  wrappers.push(wrapper)
  const dock = dockview()
  const vm = wrapper.vm as unknown as { onDockviewReady(event: DockviewReadyEvent): void }
  vm.onDockviewReady({ api: dock.api } as DockviewReadyEvent)
  return { wrapper, dock }
}

function acceptedOpen() {
  window.dispatchEvent(new CustomEvent('bioimageflow:root-workflow-open-started', {
    detail: { workflowName: 'analysis' },
  }))
}
function applyOpen() {
  window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail: presentation() }))
}

describe('application shell startup ownership', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    startup.resolve.mockReset()
    window.localStorage.clear()
  })
  afterEach(() => {
    wrappers.splice(0).forEach(wrapper => wrapper.unmount())
    canvasSessionRegistry.dispose()
    vi.restoreAllMocks()
  })

  it('mounts startup normally when there is no accepted Open', async () => {
    startup.resolve.mockResolvedValueOnce(presentation())
    const { dock } = mountShell()
    await flushPromises()
    expect(dock.panels.has('workflow:analysis')).toBe(true)
    expect(dock.panels.has('canvas-loading')).toBe(false)
  })

  it('bounds canonical startup cause to its target and restores foreground activation for existing roots', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    const workflow = useWorkflowStore()
    workflow.workflows = [
      { id: 'analysis', name: 'analysis', display_name: 'Analysis', identity_generation: 0 },
      { id: 'other', name: 'other', display_name: 'Other', identity_generation: 0 },
    ] as typeof workflow.workflows
    const other = dock.api.addPanel({ id: 'workflow:other', component: 'canvasView' })
    const observed: Array<{ name: string; cause: string }> = []
    const stop = watch(() => workflow.presentationPublication, publication => {
      if (!publication) return
      observed.push({ name: publication.workflowName, cause: publication.cause })
      expect(Object.isFrozen(publication)).toBe(true)
      // Reentrant activation of a different target must not inherit startup cause.
      if (publication.cause === 'startup') other.api.setActive()
    }, { flush: 'sync' })
    try {
      loading.resolve(presentation())
      await flushPromises()
      expect(observed).toEqual([
        { name: 'analysis', cause: 'startup' },
        { name: 'other', cause: 'foreground' },
      ])
      dock.api.getPanel('workflow:analysis')!.api.setActive()
      // A same-active setActive emits no Dockview active-change notification.
      applyOpen()
      other.api.setActive()
      applyOpen()
      await flushPromises()
      expect(observed.slice(2)).toEqual([
        { name: 'analysis', cause: 'foreground' },
        { name: 'other', cause: 'foreground' },
        { name: 'analysis', cause: 'foreground' },
      ])
    } finally {
      stop()
    }
  })

  it('does not mount competing startup content while accepted Open is loading', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    acceptedOpen()
    loading.resolve(presentation())
    await flushPromises()
    expect(dock.panels.has('workflow:analysis')).toBe(false)
    expect(dock.panels.has('canvas-empty')).toBe(true)
    applyOpen()
    await flushPromises()
    expect(dock.panels.has('workflow:analysis')).toBe(true)
    expect(dock.addPanel.mock.calls.filter(([options]) => options.id === 'workflow:analysis')).toHaveLength(1)
  })

  it('preserves accepted Create presentation when an older startup finishes before its graph loads', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    window.dispatchEvent(new CustomEvent('bioimageflow:root-workflow-open-started', { detail: { cause: 'create' } }))
    loading.resolve(presentation())
    await flushPromises()
    expect(dock.panels.has('workflow:analysis')).toBe(false)
    const id = '8851bdb9-bc35-4725-a14a-a98a75d4bf28'
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail: {
      ...presentation(), graph: makeGraph({ name: 'created' }), workflowName: id, workflowDisplayName: 'Created workflow',
    } }))
    await flushPromises()
    expect(dock.panels.has(`workflow:${id}`)).toBe(true)
    expect(dock.active()?.id).toBe(`workflow:${id}`)
    expect(dock.panels.has('workflow:analysis')).toBe(false)
  })

  it('does not reactivate a root after explicit Open and child/dock activation', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    acceptedOpen()
    applyOpen()
    const child = dock.api.addPanel({ id: 'nested-workflow:child', component: 'nestedWorkflowEditor' })
    const childId = canvasIdFromPanelId(child.id)
    canvasSessionRegistry.register({
      kind: 'nested', canvasId: childId, sessionId: 'child', parentCanvasId: canvasIdFromPanelId('workflow:analysis'),
    })
    child.api.setActive()
    useUIStore().setCanvasSelectedNodes(childId, ['nested_increment'])
    dock.api.getPanel('dataTable')!.api.setActive()
    loading.resolve(presentation())
    await flushPromises()
    expect(canvasSessionRegistry.activeCanvasId.value).toBe(childId)
    expect(useUIStore().selectedNodeIds).toEqual(['nested_increment'])
    expect(dock.active()?.id).toBe('dataTable')

    // A deliberate later Open retains its ordinary existing-root activation.
    acceptedOpen()
    applyOpen()
    await flushPromises()
    expect(canvasSessionRegistry.activeCanvasId.value).toBe('workflow:analysis')
  })

  it('leaves usable empty controls after accepted Open fails', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { dock } = mountShell()
    acceptedOpen()
    loading.resolve(presentation())
    await flushPromises()
    expect(dock.panels.has('canvas-empty')).toBe(true)
    expect(dock.panels.has('workflows')).toBe(true)
  })

  it('never mounts a late startup response after unmount', async () => {
    const loading = deferred<RootWorkflowPresentation>()
    startup.resolve.mockReturnValueOnce(loading.promise)
    const { wrapper, dock } = mountShell()
    wrapper.unmount()
    const calls = dock.addPanel.mock.calls.length
    loading.resolve(presentation())
    await flushPromises()
    expect(dock.addPanel).toHaveBeenCalledTimes(calls)
    expect(dock.dispose).toHaveBeenCalled()
  })
})


describe('workflow deletion workspace ownership', () => {
  async function mountedOwner(freshness: Promise<boolean>) {
    startup.resolve.mockResolvedValueOnce({ ...presentation(), workflowName: '3a93e0eb-5681-48c4-83c7-145e90335786' })
    const { dock } = mountShell()
    await flushPromises()
    const store = useWorkflowStore()
    const info = {
      id: '3a93e0eb-5681-48c4-83c7-145e90335786', name: '3a93e0eb-5681-48c4-83c7-145e90335786', relative_path: '3a93e0eb-5681-48c4-83c7-145e90335786', display_name: 'Workspace A workflow',
      workspace_path: '/workspace-a', identity_generation: 0,
      path: '/workspace-a/workflows/analysis/workflow.json', results_path: '/workspace-a/workflows/analysis/results', last_modified: '',
    } as WorkflowInfo
    store.workflows = [info]
    store.current = info
    store.observeWorkflowServerIdentityGeneration(info.id, 0)
    const canvasId = canvasIdFromPanelId('workflow:3a93e0eb-5681-48c4-83c7-145e90335786')
    const fresh = vi.fn().mockReturnValue(freshness)
    canvasSessionRegistry.getOrCreateResource(canvasId, ROOT_PERSISTENCE_RESOURCE, () => ({
      workflowId: ref(info.id), workspacePath: info.workspace_path,
      ensureFreshForCriticalOperation: fresh, dispose: vi.fn(),
    }))
    const request = {
      workflowName: info.id, workspacePath: info.workspace_path!,
      workspaceSelectionRevision: useSettingsStore().workspaceSelectionRevision,
      canvasId, localIdentityGeneration: store.workflowIdentityGeneration(info.id),
      serverIdentityGeneration: 0, sessionRegistrationToken: canvasSessionRegistry.get(canvasId)!.registrationToken,
    }
    return { dock, store, info, canvasId, fresh, request }
  }

  async function switchToClone(info: WorkflowInfo, canvasId: ReturnType<typeof canvasIdFromPanelId>) {
    useSettingsStore().workspaceSelectionRevision += 1
    const clone = { ...info, workspace_path: '/workspace-b', display_name: 'Workspace B clone' }
    useWorkflowStore().workflows = [clone]
    useWorkflowStore().current = clone
    useUIStore().setCanvasWorkflow(canvasId, clone.id, clone.display_name)
    useUIStore().markCanvasDirty(canvasId)
    const snapshot = { name: clone.id, graph: makeGraph({ display_name: 'B unsaved edits' }), timestamp: Date.now(), workspace_path: '/workspace-b', identity_generation: 0 }
    await writeAutoSaveEntry(snapshot)
    return { clone, snapshot }
  }

  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    startup.resolve.mockReset()
    window.localStorage.clear()
  })
  afterEach(() => {
    wrappers.splice(0).forEach(wrapper => wrapper.unmount())
    canvasSessionRegistry.dispose()
    vi.restoreAllMocks()
  })

  it('refuses DELETE after a cloned workspace replaces the owner during its persistence barrier', async () => {
    const barrier = deferred<boolean>()
    const { dock, store, info, canvasId, fresh, request } = await mountedOwner(barrier.promise)
    const deleteTransport = vi.spyOn(api, 'delete')
    const deletion = requestWorkflowDeletion(request)
    const rejected = expect(deletion).rejects.toThrow(/replaced after this delete confirmation opened/)
    await flushPromises()
    expect(fresh).toHaveBeenCalledOnce()
    const { clone, snapshot } = await switchToClone(info, canvasId)
    barrier.resolve(true)
    await rejected
    expect(deleteTransport).not.toHaveBeenCalled()
    expect(dock.panels.has('workflow:3a93e0eb-5681-48c4-83c7-145e90335786')).toBe(true)
    expect(store.current).toEqual(clone)
    expect(store.workflows).toEqual([clone])
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
    expect(await useAutoSave().loadAutoSave(info.id, snapshot)).toMatchObject(snapshot)
  })

  it('fences the DELETE transport to A and ignores a late A success after switching to the same UUID in B', async () => {
    const response = deferred<{ data: { deleted: boolean; identity_generation: number } }>()
    const { dock, store, info, canvasId, request } = await mountedOwner(Promise.resolve(true))
    const panel = dock.panels.get('workflow:3a93e0eb-5681-48c4-83c7-145e90335786')
    const deleteTransport = vi.spyOn(api, 'delete').mockReturnValue(response.promise)
    const deletion = requestWorkflowDeletion(request)
    const rejected = expect(deletion).rejects.toThrow(/workspace changed/)
    await flushPromises()
    expect(deleteTransport).toHaveBeenCalledWith('/api/v1/workflows/3a93e0eb-5681-48c4-83c7-145e90335786', {
      params: { expected_identity_generation: 0 }, headers: { 'X-BioImageFlow-Workspace': '/workspace-a' },
    })
    const { clone, snapshot } = await switchToClone(info, canvasId)
    response.resolve({ data: { deleted: true, identity_generation: 1 } })
    await rejected
    expect(dock.panels.get('workflow:3a93e0eb-5681-48c4-83c7-145e90335786')).toBe(panel)
    expect(canvasSessionRegistry.get(canvasId)?.registrationToken).toBe(request.sessionRegistrationToken)
    expect(store.current).toEqual(clone)
    expect(store.workflows).toEqual([clone])
    expect(store.workflowServerIdentityGeneration(info.id)).toBe(0)
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
    expect(await useAutoSave().loadAutoSave(info.id, snapshot)).toMatchObject(snapshot)
  })
})
