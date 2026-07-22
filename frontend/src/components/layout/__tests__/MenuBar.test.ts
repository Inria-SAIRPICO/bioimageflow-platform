import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { makeGraph, makeGraphNode } from '@/test-utils/graphFixtures'

const toastAdd = vi.hoisted(() => vi.fn())
const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}))
const autoSaveMocks = vi.hoisted(() => ({
  clearAutoSave: vi.fn().mockResolvedValue(undefined),
  clearAutoSaveStrict: vi.fn().mockResolvedValue(undefined),
  setLastOpenedWorkflow: vi.fn().mockResolvedValue(undefined),
}))
const workflowDraftMocks = vi.hoisted(() => ({
  ensureFreshForCriticalOperation: vi.fn().mockResolvedValue(true),
  scheduleSave: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  loadDraft: vi.fn(),
  forgetWorkflow: vi.fn(),
  acknowledgeAcceptedDraft: vi.fn(),
}))
const persistenceMocks = vi.hoisted(() => ({
  canvasId: null as string | null,
  ensureFreshForCriticalOperation: vi.fn().mockResolvedValue(true),
  queueDraft: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
}))
const canvasCommandMocks = vi.hoisted(() => ({
  routeSave: vi.fn().mockResolvedValue('root'),
}))

vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: toastAdd }),
}))

vi.mock('@/api/client', () => ({
  api: apiMocks,
}))

vi.mock('@/composables/useAutoSave', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/composables/useAutoSave')
  >()
  return {
    ...actual,
    useAutoSave: () => autoSaveMocks,
  }
})

vi.mock('@/stores/workflowDraft', () => ({
  useWorkflowDraftStore: () => workflowDraftMocks,
}))

vi.mock('@/composables/useCanvasPersistence', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/composables/useCanvasPersistence')
  >()
  return {
    ...actual,
    useCanvasPersistence: () => persistenceMocks,
  }
})

vi.mock('@/composables/useCanvasCommands', () => ({
  useCanvasCommands: () => canvasCommandMocks,
}))

import MenuBar from '../MenuBar.vue'
import { useUIStore } from '@/stores/ui'
import { useErrorStore } from '@/stores/errors'
import { useWorkflowStore } from '@/stores/workflow'
import { useExecutionStore } from '@/stores/execution'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import { useGraphSync } from '@/composables/useGraphSync'
import {
  getOrCreateRootPersistenceResource,
  ROOT_PERSISTENCE_RESOURCE,
  type RootCanvasPersistenceResource,
} from '@/composables/useCanvasPersistence'
import type { GraphState, WorkflowInfo } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import {
  WorkflowDeletionCommittedCleanupError,
  type WorkflowDeletionEventDetail,
} from '@/services/workflowDeletion'

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

// PrimeVue Menubar uses matchMedia for responsive behavior
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
})

Object.defineProperty(globalThis, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
})

let pinia: ReturnType<typeof createPinia>
let mountedWrappers: ReturnType<typeof mount>[] = []

function mountMenuBar() {
  const wrapper = mount(MenuBar, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

function registerActiveRootWorkflow(options: {
  name?: string
  displayName?: string
  description?: string | null
  graph?: GraphState
} = {}) {
  const name = options.name ?? 'wf_a'
  const displayName = options.displayName ?? 'Workflow A'
  const canvasId = canvasIdFromPanelId(`workflow:${name}`)
  const workflow = {
    name,
    display_name: displayName,
    description: options.description ?? null,
    storage_path: `/tmp/workflows/${name}`,
    path: `/tmp/workflows/${name}.json`,
    last_modified: '2026-01-01T00:00:00Z',
      identity_generation: 0,
  } as WorkflowInfo
  const sync = useGraphSync({
    descriptor: { kind: 'root', canvasId, workflowId: name },
    getWorkflowId: () => name,
  })
  sync.currentGraph.value = options.graph ?? makeGraph()
  const persistence = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
    canvasId,
    ROOT_PERSISTENCE_RESOURCE,
  )!
  vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
  vi.spyOn(persistence, 'queueDraft').mockImplementation(() => {})
  vi.spyOn(persistence, 'queueGraph').mockImplementation((graph) => {
    persistence.currentGraph.value = graph
  })
  vi.spyOn(persistence, 'flush').mockResolvedValue(undefined)
  const store = useWorkflowStore()
  if (!store.workflows.some(item => (item.id ?? item.name) === name)) {
    store.workflows = [...store.workflows, workflow]
  }
  store.current = workflow
  useUIStore().setCanvasWorkflow(canvasId, name, displayName)
  canvasSessionRegistry.activate(canvasId)
  persistenceMocks.canvasId = canvasId
  return { canvasId, workflow, sync, persistence }
}

function observeWorkflowDeletion(
  callback: (detail: WorkflowDeletionEventDetail) => void,
): () => void {
  const listener = (event: Event) => {
    callback((event as CustomEvent<WorkflowDeletionEventDetail>).detail)
  }
  window.addEventListener('bioimageflow:request-delete-workflow', listener)
  return () => window.removeEventListener('bioimageflow:request-delete-workflow', listener)
}

describe('MenuBar', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    window.localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
    toastAdd.mockClear()
    apiMocks.get.mockReset()
    apiMocks.post.mockReset()
    apiMocks.put.mockReset()
    apiMocks.patch.mockReset()
    apiMocks.delete.mockReset()
    autoSaveMocks.clearAutoSave.mockClear()
    autoSaveMocks.clearAutoSaveStrict.mockReset().mockResolvedValue(undefined)
    autoSaveMocks.setLastOpenedWorkflow.mockClear()
    workflowDraftMocks.ensureFreshForCriticalOperation.mockClear()
    workflowDraftMocks.ensureFreshForCriticalOperation.mockResolvedValue(true)
    workflowDraftMocks.scheduleSave.mockClear()
    workflowDraftMocks.flush.mockClear()
    workflowDraftMocks.loadDraft.mockReset()
    workflowDraftMocks.forgetWorkflow.mockClear()
    workflowDraftMocks.acknowledgeAcceptedDraft.mockClear()
    persistenceMocks.ensureFreshForCriticalOperation.mockClear()
    persistenceMocks.ensureFreshForCriticalOperation.mockResolvedValue(true)
    persistenceMocks.canvasId = null
    persistenceMocks.queueDraft.mockClear()
    persistenceMocks.flush.mockClear()
    canvasCommandMocks.routeSave.mockClear()
    canvasCommandMocks.routeSave.mockResolvedValue('root')
    if (typeof window.URL.createObjectURL !== 'function') {
      Object.defineProperty(window.URL, 'createObjectURL', {
        value: vi.fn(() => 'blob:workflow'),
        configurable: true,
      })
    } else {
      vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:workflow')
    }
    if (typeof window.URL.revokeObjectURL !== 'function') {
      Object.defineProperty(window.URL, 'revokeObjectURL', {
        value: vi.fn(),
        configurable: true,
      })
    } else {
      vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {})
    }
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  afterEach(() => {
    for (const wrapper of mountedWrappers) wrapper.unmount()
    mountedWrappers = []
    document.body.innerHTML = ''
  })

  it('renders a menubar element', () => {
    const wrapper = mountMenuBar()
    expect(wrapper.find('[data-testid="app-menubar"]').exists()).toBe(true)
  })

  it('has 5 top-level menu items', () => {
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any
    expect(vm.menuItems).toHaveLength(5)
    const labels = vm.menuItems.map((item: any) => item.label)
    expect(labels).toEqual(['Workflow', 'Edit', 'Execution', 'View', 'Help'])
  })

  it('View menu has 7 panel toggle items', () => {
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any
    const viewMenu = vm.menuItems.find((item: any) => item.label === 'View')
    expect(viewMenu.items).toHaveLength(7)
    const toggleLabels = viewMenu.items.map((item: any) => item.label)
    expect(toggleLabels).toEqual([
      'Tools Panel',
      'Workflows Panel',
      'Datasets Panel',
      'Nodes',
      'Data Table',
      'Logger',
      'Code Editor',
    ])
  })

  it('View toggle items reflect uiStore.panels state', () => {
    const store = useUIStore()
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any
    const viewMenu = vm.menuItems.find((item: any) => item.label === 'View')
    const toolsToggle = viewMenu.items.find((item: any) => item.label === 'Tools Panel')

    expect(toolsToggle.icon).toBe('pi pi-check')
    store.togglePanel('tools')
    const viewMenuAfter = vm.menuItems.find((item: any) => item.label === 'View')
    const toolsToggleAfter = viewMenuAfter.items.find((item: any) => item.label === 'Tools Panel')
    expect(toolsToggleAfter.icon).toBeUndefined()
  })

  it('View toggle item calls uiStore.togglePanel', () => {
    const store = useUIStore()
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any
    const viewMenu = vm.menuItems.find((item: any) => item.label === 'View')
    const toolsToggle = viewMenu.items.find((item: any) => item.label === 'Tools Panel')

    expect(store.panels.tools).toBe(true)
    toolsToggle.command()
    expect(store.panels.tools).toBe(false)
  })

  it('renders a theme chooser button with light, dark, and system choices', () => {
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any

    expect(wrapper.find('[data-testid="theme-menu-button"]').exists()).toBe(true)
    expect(vm.themeMenuItems.map((item: any) => item.label)).toEqual([
      'Light',
      'Dark',
      'System',
    ])
    expect(vm.themeButtonIcon).toBe('pi pi-desktop')
  })

  it('theme chooser updates the stored theme preference', () => {
    const store = useUIStore()
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any

    vm.themeMenuItems.find((item: any) => item.label === 'Dark').command()

    expect(store.themePreference).toBe('dark')
    expect(vm.themeButtonIcon).toBe('pi pi-moon')
  })

  describe('Workflow menu', () => {
    it('does not expose the global workflow when no registered canvas is active', () => {
      useWorkflowStore().current = {
        name: 'wf_a',
        folder: '',
        display_name: 'Workflow A',
        path: '/tmp/workflows/wf_a.json',
        last_modified: '2026-01-01T00:00:00Z',
      identity_generation: 0,
      }
      const canvasId = canvasIdFromPanelId('workflow:registered')
      canvasSessionRegistry.register({
        kind: 'root',
        canvasId,
        workflowId: 'registered',
      })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
      const execution = vm.menuItems.find((item: any) => item.label === 'Execution')

      expect(wrapper.find('[data-testid="workflow-title"]').text()).toBe('No workflow')
      expect(workflow.items.find((item: any) => item.label === 'Export').disabled).toBe(true)
      expect(execution.items.find((item: any) => item.label === 'Run Workflow').disabled)
        .toBe(true)
    })

    it('uses the active canvas workflow for action metadata and branching', async () => {
      const { canvasId: canvasA } = registerActiveRootWorkflow({
        name: 'a',
        displayName: 'Workflow A',
        description: 'Description A',
      })
      registerActiveRootWorkflow({
        name: 'b',
        displayName: 'Workflow B',
        description: 'Description B',
      })
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      const store = useWorkflowStore()
      store.current = store.workflows[1]
      const exportWorkflow = vi.spyOn(store, 'exportWorkflow').mockResolvedValue(undefined)
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')

      workflow.items.find((item: any) => item.label === 'Save As').command()
      expect(vm.workflowDialogInitialName).toBe('a_copy')
      expect(vm.workflowDialogInitialDescription).toBe('Description A')

      window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
        detail: { action: 'export', name: 'a' },
      }))
      await flushPromises()
      expect(vm.exportSaveDialogVisible).toBe(true)
      expect(exportWorkflow).not.toHaveBeenCalled()

      workflow.items.find((item: any) => item.label === 'Delete').command()
      expect(vm.deleteDialogWorkflow.name).toBe('a')
    })

    it('keeps Rename bound to the canvas that opened the dialog', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const canvasB = canvasIdFromPanelId('workflow:b')
      canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
      canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
      const workflowA = { name: 'a', display_name: 'Workflow A' } as any
      const workflowB = { name: 'b', display_name: 'Workflow B' } as any
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [workflowA, workflowB]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      apiMocks.patch.mockResolvedValueOnce({
        data: { ...workflowA, display_name: 'Workflow A renamed' },
      })
      const wrapper = mountMenuBar()
      await wrapper.find('[data-testid="workflow-title-edit"]').trigger('click')
      const vm = wrapper.vm as any
      vm.renameDisplayName = 'Workflow A renamed'

      canvasSessionRegistry.activate(canvasB)
      persistenceMocks.canvasId = canvasB
      store.current = workflowB
      await vm.submitRename()

      expect(apiMocks.patch).toHaveBeenCalledWith('/api/v1/workflows/a', {
        action: 'update',
        display_name: 'Workflow A renamed',
      })
      expect(store.currentName).toBe('b')
      expect(ui.activeWorkflowName).toBe('Workflow B')
      canvasSessionRegistry.activate(canvasA)
      expect(ui.activeWorkflowName).toBe('Workflow A renamed')
      wrapper.unmount()
    })

    it('saves a copy from the canvas that opened Save As after activation changes', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const canvasB = canvasIdFromPanelId('workflow:b')
      const graphA: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'a-node',
          name: 'A node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const graphB: GraphState = makeGraph()
      const syncA = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
        getWorkflowId: () => 'a',
      })
      const syncB = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'b' },
        getWorkflowId: () => 'b',
      })
      syncA.currentGraph.value = graphA
      syncB.currentGraph.value = graphB
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [
        { name: 'a', display_name: 'Workflow A' },
        { name: 'b', display_name: 'Workflow B' },
      ] as any
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
      workflow.items.find((item: any) => item.label === 'Save As').command()
      const applied: any[] = []
      const onApply = (event: Event) => applied.push((event as CustomEvent).detail)
      window.addEventListener('bioimageflow:apply-graph', onApply)
      apiMocks.patch.mockResolvedValueOnce({
        data: { name: 'a_copy', display_name: 'Workflow A copy' },
      })
      apiMocks.put.mockResolvedValueOnce({
        data: { name: 'a_copy', display_name: 'Workflow A copy' },
      })

      canvasSessionRegistry.activate(canvasB)
      persistenceMocks.canvasId = canvasB
      await vm.onWorkflowDialogSubmit({
        name: 'a_copy',
        folder: '',
        display_name: 'Workflow A copy',
        description: null,
      })

      expect(apiMocks.patch).toHaveBeenCalledWith('/api/v1/workflows/a', expect.objectContaining({
        action: 'duplicate',
        new_name: 'a_copy',
      }))
      expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflows/a_copy', { graph: graphA })
      expect(applied[applied.length - 1]).toMatchObject({
        graph: graphA,
        workflowName: 'a_copy',
        workflowDisplayName: 'Workflow A copy',
        identityGeneration: 1,
      })
      window.removeEventListener('bioimageflow:apply-graph', onApply)
      wrapper.unmount()
    })

    it('keeps a delayed workflow deletion bound to the canvas that requested it', async () => {
      const { canvasId: canvasA, workflow: workflowA } = registerActiveRootWorkflow({
        name: 'a',
        displayName: 'Workflow A',
      })
      const { canvasId: canvasB, workflow: workflowB } = registerActiveRootWorkflow({
        name: 'b',
        displayName: 'Workflow B',
      })
      const store = useWorkflowStore()
      store.current = workflowA
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      let deletionRequest: WorkflowDeletionEventDetail | null = null
      const stopObserving = observeWorkflowDeletion((detail) => {
        deletionRequest = detail
      })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
      workflow.items.find((item: any) => item.label === 'Delete').command()
      const applied: any[] = []
      const onApply = (event: Event) => applied.push((event as CustomEvent).detail)
      window.addEventListener('bioimageflow:apply-graph', onApply)

      const deletion = vm.confirmDeleteWorkflow()
      expect(deletionRequest).toMatchObject({ workflowName: 'a', canvasId: canvasA })
      canvasSessionRegistry.activate(canvasB)
      persistenceMocks.canvasId = canvasB
      store.current = workflowB
      deletionRequest!.resolve()
      await deletion

      expect(applied).toEqual([])
      expect(store.currentName).toBe('b')
      expect(vm.deleteDialogVisible).toBe(false)
      expect(vm.deleteCanvasTarget).toBeNull()
      stopObserving()
      window.removeEventListener('bioimageflow:apply-graph', onApply)
      wrapper.unmount()
    })

    it('keeps the confirmed canvas mounted when workflow deletion fails', async () => {
      const { canvasId, workflow } = registerActiveRootWorkflow({
        name: 'a',
        displayName: 'Workflow A',
      })
      const store = useWorkflowStore()
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      workflowMenu.items.find((item: any) => item.label === 'Delete').command()
      let deletionRequest: WorkflowDeletionEventDetail | null = null
      const stopObserving = observeWorkflowDeletion((detail) => {
        deletionRequest = detail
        detail.reject(new Error('delete failed'))
      })

      await vm.confirmDeleteWorkflow()

      expect(deletionRequest).toMatchObject({ workflowName: 'a', canvasId })
      expect(canvasSessionRegistry.get(canvasId)).not.toBeNull()
      expect(store.workflows).toEqual([workflow])
      expect(vm.deleteDialogVisible).toBe(true)
      expect(vm.deleteTargetName).toBe('a')
      expect(vm.deleteCanvasTarget).toMatchObject({ canvasId, workflowName: 'a' })
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        severity: 'error',
        summary: 'Delete workflow failed',
      }))
      stopObserving()
      wrapper.unmount()
    })

    it('rejects a delete confirmation after the same workflow id is recreated', async () => {
      const { canvasId } = registerActiveRootWorkflow({
        name: 'a',
        displayName: 'Old A',
      })
      const store = useWorkflowStore()
      store.observeWorkflowServerIdentityGeneration('a', 4)
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      workflowMenu.items.find((item: any) => item.label === 'Delete').command()
      const capturedToken = vm.deleteCanvasTarget.sessionRegistrationToken
      let deletionRequest: WorkflowDeletionEventDetail | null = null
      const stopObserving = observeWorkflowDeletion((detail) => {
        deletionRequest = detail
      })

      canvasSessionRegistry.unregister(canvasId)
      await store.forgetDeletedWorkflow('a')
      store.observeWorkflowServerIdentityGeneration('a', 5)
      registerActiveRootWorkflow({ name: 'a', displayName: 'Fresh A' })
      const freshToken = canvasSessionRegistry.get(canvasId)?.registrationToken

      await vm.confirmDeleteWorkflow()

      expect(freshToken).not.toBe(capturedToken)
      expect(deletionRequest).toBeNull()
      expect(canvasSessionRegistry.get(canvasId)?.registrationToken).toBe(freshToken)
      expect(vm.deleteDialogVisible).toBe(false)
      expect(vm.deleteCanvasTarget).toBeNull()
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        severity: 'error',
        summary: 'Delete workflow failed',
        detail: expect.stringContaining('replaced after this delete confirmation opened'),
      }))
      stopObserving()
      wrapper.unmount()
    })

    it('rejects a workflow-browser delete after an unmounted identity is recreated', async () => {
      registerActiveRootWorkflow({ name: 'b', displayName: 'Workflow B' })
      const store = useWorkflowStore()
      store.workflows = [
        { name: 'a', display_name: 'Old A' } as WorkflowInfo,
        ...store.workflows,
      ]
      store.observeWorkflowServerIdentityGeneration('a', 4)
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      let deletionRequest: WorkflowDeletionEventDetail | null = null
      const stopObserving = observeWorkflowDeletion((detail) => {
        deletionRequest = detail
      })

      window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
        detail: { action: 'delete', name: 'a' },
      }))
      expect(vm.deleteCanvasTarget).toMatchObject({
        workflowName: 'a',
        canvasId: null,
        serverIdentityGeneration: 4,
        sessionRegistrationToken: null,
      })

      store.observeWorkflowServerIdentityGeneration('a', 5)
      store.workflows = [
        { name: 'a', display_name: 'Fresh A' } as WorkflowInfo,
        ...store.workflows.filter((workflow: WorkflowInfo) => workflow.name !== 'a'),
      ]
      await vm.confirmDeleteWorkflow()

      expect(deletionRequest).toBeNull()
      expect(vm.deleteDialogVisible).toBe(false)
      expect(vm.deleteCanvasTarget).toBeNull()
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        severity: 'error',
        detail: expect.stringContaining('replaced after this delete confirmation opened'),
      }))
      stopObserving()
      wrapper.unmount()
    })

    it('closes a committed delete dialog and warns when local cleanup fails', async () => {
      registerActiveRootWorkflow({ name: 'a', displayName: 'Workflow A' })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      workflowMenu.items.find((item: any) => item.label === 'Delete').command()
      const stopObserving = observeWorkflowDeletion((detail) => {
        detail.reject(new WorkflowDeletionCommittedCleanupError(
          'a',
          new Error('IndexedDB unavailable'),
        ))
      })

      await vm.confirmDeleteWorkflow()

      expect(vm.deleteDialogVisible).toBe(false)
      expect(vm.deleteTargetName).toBeNull()
      expect(vm.deleteCanvasTarget).toBeNull()
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        severity: 'warn',
        summary: 'Workflow deleted with cleanup warning',
        detail: expect.stringContaining('IndexedDB unavailable'),
      }))
      stopObserving()
      wrapper.unmount()
    })

    it('opens the workflow chooser for an open command without a workflow name', async () => {
      const workflows = [
        { name: 'a', display_name: 'Workflow A' } as WorkflowInfo,
      ]
      apiMocks.get.mockResolvedValueOnce({ data: workflows })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any

      window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
        detail: { action: 'open' },
      }))
      await flushPromises()

      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflows')
      expect(vm.openDialogVisible).toBe(true)
      expect(document.body.querySelector('[data-testid="open-workflow-dialog"]')).not.toBeNull()
    })

    it('opens the workflow that finished loading even if global current changes later', async () => {
      const graphA: GraphState = makeGraph()
      apiMocks.get.mockResolvedValueOnce({
        data: {
          info: { name: 'a', display_name: 'Workflow A' },
          graph: graphA,
          missing_packages: [],
          missing_tools: [],
        },
      })
      const openedDraft = {
        draft_version: 1 as const,
        workflow_id: 'a',
        base_saved_revision: 'sha256:a',
        draft_revision: 7,
        updated_at: '2026-07-16T01:00:00Z',
        updated_by: 'agent' as const,
        dirty_against_saved: false,
        graph: graphA,
        validation: { valid: true, node_statuses: {}, errors: [] },
      }
      let resolveDraft!: (value: typeof openedDraft) => void
      workflowDraftMocks.loadDraft.mockReturnValueOnce(new Promise((resolve) => {
        resolveDraft = resolve
      }))
      const wrapper = mountMenuBar()
      const applied: any[] = []
      const onApply = (event: Event) => applied.push((event as CustomEvent).detail)
      window.addEventListener('bioimageflow:apply-graph', onApply)

      window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
        detail: { action: 'open', name: 'a' },
      }))
      await flushPromises()
      useWorkflowStore().current = { name: 'b', display_name: 'Workflow B' } as any
      resolveDraft(openedDraft)
      await flushPromises()

      expect(applied[applied.length - 1]).toMatchObject({
        graph: graphA,
        workflowName: 'a',
        workflowDisplayName: 'Workflow A',
        draft: openedDraft,
        identityGeneration: 0,
      })
      window.removeEventListener('bioimageflow:apply-graph', onApply)
      wrapper.unmount()
    })

    it('omits dependency-only entries and shows an icon for Save As', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
      const labels = workflow.items.map((item: any) => item.label)

      expect(labels).toEqual([
        'New',
        'Open',
        'Save',
        'Save As',
        'Import',
        'Export',
        'Build from Python source',
        'Delete',
      ])
      expect(labels).not.toContain('Dependencies')
      expect(labels).not.toContain('Use Installed Versions')
      expect(workflow.items.find((item: any) => item.label === 'Save As').icon).toBe('pi pi-copy')
      expect(workflow.items.find((item: any) => item.label === 'Import').icon).toBe('pi pi-upload')
      expect(workflow.items.find((item: any) => item.label === 'Export').icon).toBe('pi pi-download')
    })

    it('disables Export when no workflow is active', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')

      expect(workflow.items.find((item: any) => item.label === 'Export').disabled).toBe(true)
    })

    it('calls the workflow export action for the current workflow', async () => {
      registerActiveRootWorkflow({
        name: 'cell_segmentation',
        displayName: 'Cell segmentation',
      })
      const workflow = useWorkflowStore()
      const exportWorkflow = vi
        .spyOn(workflow, 'exportWorkflow')
        .mockResolvedValue(undefined)
      apiMocks.put.mockResolvedValueOnce({ data: workflow.current })

      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      await workflowMenu.items.find((item: any) => item.label === 'Export').command()
      await flushPromises()
      expect(vm.exportSaveDialogVisible).toBe(true)
      await vm.confirmExportCurrentWorkflow()
      await flushPromises()

      expect(exportWorkflow).toHaveBeenCalledWith('cell_segmentation')
    })

    it('confirms that export saves the current workflow before downloading', async () => {
      registerActiveRootWorkflow({
        name: 'cell_segmentation',
        displayName: 'Cell segmentation',
      })
      apiMocks.put.mockResolvedValueOnce({
        data: {
          name: 'cell_segmentation',
          folder: '',
          display_name: 'Cell segmentation',
          path: '/tmp/cell_segmentation.json',
          last_modified: '2026-04-29T00:00:01Z',
      identity_generation: 0,
        },
      })
      apiMocks.post.mockResolvedValueOnce({
        data: new Blob(['zip']),
        headers: {},
      })

      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      await workflowMenu.items.find((item: any) => item.label === 'Export').command()
      await flushPromises()

      expect(vm.exportSaveDialogVisible).toBe(true)
      expect(apiMocks.put).not.toHaveBeenCalled()
      expect(apiMocks.post).not.toHaveBeenCalledWith(
        '/api/v1/workflows/cell_segmentation/export',
        undefined,
        expect.anything(),
      )

      await vm.confirmExportCurrentWorkflow()
      await flushPromises()

      expect(apiMocks.put).toHaveBeenCalledWith(
        '/api/v1/workflows/cell_segmentation',
        { graph: makeGraph() },
      )
      expect(apiMocks.post).toHaveBeenCalledWith(
        '/api/v1/workflows/cell_segmentation/export',
        undefined,
        { responseType: 'blob' },
      )
    })

    it('releases the captured export target when the dialog is cancelled', async () => {
      const { workflow } = registerActiveRootWorkflow({
        name: 'cell_segmentation',
        displayName: 'Cell segmentation',
      })
      apiMocks.put.mockResolvedValueOnce({ data: workflow })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      workflowMenu.items.find((item: any) => item.label === 'Export').command()
      vm.exportSaveDialogVisible = false
      await vm.confirmExportCurrentWorkflow()

      expect(apiMocks.put).not.toHaveBeenCalled()
      expect(apiMocks.post).not.toHaveBeenCalled()
      wrapper.unmount()
    })

    it('keeps confirmed export bound to the root canvas that opened the dialog', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const canvasB = canvasIdFromPanelId('workflow:b')
      const initialGraphA: GraphState = makeGraph()
      const latestGraphA: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'a-node',
          name: 'A node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: { value: 'latest-a' },
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const graphB: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'b-node',
          name: 'B node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: { value: 'b' },
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const syncA = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
        getWorkflowId: () => 'a',
      })
      const syncB = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'b' },
        getWorkflowId: () => 'b',
      })
      syncA.currentGraph.value = initialGraphA
      syncB.currentGraph.value = graphB
      const persistenceA = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
        canvasA,
        ROOT_PERSISTENCE_RESOURCE,
      )!
      const persistenceB = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
        canvasB,
        ROOT_PERSISTENCE_RESOURCE,
      )!
      const ensureFreshA = vi.spyOn(persistenceA, 'ensureFreshForCriticalOperation')
        .mockResolvedValue(true)
      const queueDraftA = vi.spyOn(persistenceA, 'queueDraft')
      const flushA = vi.spyOn(persistenceA, 'flush').mockResolvedValue(undefined)
      const ensureFreshB = vi.spyOn(persistenceB, 'ensureFreshForCriticalOperation')
        .mockResolvedValue(true)
      const queueDraftB = vi.spyOn(persistenceB, 'queueDraft')
      const flushB = vi.spyOn(persistenceB, 'flush').mockResolvedValue(undefined)
      const store = useWorkflowStore()
      const ui = useUIStore()
      const workflowA = { name: 'a', display_name: 'Workflow A' } as any
      const workflowB = { name: 'b', display_name: 'Workflow B' } as any
      store.workflows = [workflowA, workflowB]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      apiMocks.put.mockResolvedValueOnce({ data: workflowA })
      apiMocks.post.mockResolvedValueOnce({ data: new Blob(['zip']), headers: {} })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      workflowMenu.items.find((item: any) => item.label === 'Export').command()
      syncA.currentGraph.value = latestGraphA
      canvasSessionRegistry.activate(canvasB)
      persistenceMocks.canvasId = canvasB
      store.current = workflowB
      await vm.confirmExportCurrentWorkflow()

      expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflows/a', {
        graph: latestGraphA,
      })
      expect(apiMocks.post).toHaveBeenCalledWith(
        '/api/v1/workflows/a/export',
        undefined,
        { responseType: 'blob' },
      )
      expect(ensureFreshA).toHaveBeenCalledOnce()
      expect(queueDraftA).toHaveBeenCalledWith(latestGraphA)
      expect(flushA).toHaveBeenCalledOnce()
      expect(ensureFreshB).not.toHaveBeenCalled()
      expect(queueDraftB).not.toHaveBeenCalled()
      expect(flushB).not.toHaveBeenCalled()
      expect(persistenceMocks.ensureFreshForCriticalOperation).not.toHaveBeenCalled()
      wrapper.unmount()
    })

    it.each(['save', 'flush'] as const)(
      'aborts fixed export and preserves a newer A edit arriving during %s',
      async (phase) => {
        const canvasA = canvasIdFromPanelId('workflow:a')
        const canvasB = canvasIdFromPanelId('workflow:b')
        const capturedGraphA: GraphState = makeGraph()
        const newerGraphA: GraphState = makeGraph({
          nodes: [{
            type: 'tool',
            id: 'newer-a-node',
            name: 'Newer A node',
            tool_name: 'tool',
            position: [0, 0],
            parameters: { value: 'newer-a' },
            resources: {},
            output_templates: {},
            enabled: true,
            collapsed: false,
          }],
          edges: [],
        })
        const graphB: GraphState = makeGraph()
        useGraphSync({
          descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
          getWorkflowId: () => 'a',
        })
        useGraphSync({
          descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'b' },
          getWorkflowId: () => 'b',
        })
        const persistenceA = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
          canvasA,
          ROOT_PERSISTENCE_RESOURCE,
        )!
        const persistenceB = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
          canvasB,
          ROOT_PERSISTENCE_RESOURCE,
        )!
        persistenceA.currentGraph.value = capturedGraphA
        persistenceB.currentGraph.value = graphB
        vi.spyOn(persistenceA, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
        const queueDraftA = vi.spyOn(persistenceA, 'queueDraft')
        const queueGraphA = vi.spyOn(persistenceA, 'queueGraph').mockImplementation(() => {})
        const pendingFlush = deferred<void>()
        const flushA = vi.spyOn(persistenceA, 'flush').mockImplementation(
          phase === 'flush' ? () => pendingFlush.promise : async () => {},
        )
        const ensureFreshB = vi.spyOn(persistenceB, 'ensureFreshForCriticalOperation')
          .mockResolvedValue(true)
        const queueDraftB = vi.spyOn(persistenceB, 'queueDraft')
        const flushB = vi.spyOn(persistenceB, 'flush').mockResolvedValue(undefined)
        const workflowA = { name: 'a', display_name: 'Workflow A' } as any
        const workflowB = { name: 'b', display_name: 'Workflow B' } as any
        const pendingSave = deferred<{ data: typeof workflowA }>()
        const store = useWorkflowStore()
        const ui = useUIStore()
        store.workflows = [workflowA, workflowB]
        store.current = workflowA
        ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
        ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
        canvasSessionRegistry.activate(canvasA)
        persistenceMocks.canvasId = canvasA
        if (phase === 'save') {
          apiMocks.put.mockReturnValueOnce(pendingSave.promise)
        } else {
          apiMocks.put.mockResolvedValueOnce({ data: workflowA })
        }
        const wrapper = mountMenuBar()
        const vm = wrapper.vm as any
        const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

        workflowMenu.items.find((item: any) => item.label === 'Export').command()
        canvasSessionRegistry.activate(canvasB)
        persistenceMocks.canvasId = canvasB
        store.current = workflowB
        const confirmation = vm.confirmExportCurrentWorkflow()
        if (phase === 'save') {
          await vi.waitFor(() => expect(apiMocks.put).toHaveBeenCalledOnce())
        } else {
          await vi.waitFor(() => expect(flushA).toHaveBeenCalledOnce())
        }
        persistenceA.currentGraph.value = newerGraphA
        ui.markCanvasDirty(canvasA)
        if (phase === 'save') {
          pendingSave.resolve({ data: workflowA })
        } else {
          pendingFlush.resolve()
        }
        await confirmation

        expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflows/a', {
          graph: capturedGraphA,
        })
        expect(apiMocks.post).not.toHaveBeenCalled()
        expect(persistenceA.currentGraph.value).toEqual(newerGraphA)
        expect(queueGraphA).toHaveBeenCalledWith(newerGraphA)
        expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(true)
        if (phase === 'save') {
          expect(queueDraftA).not.toHaveBeenCalled()
          expect(flushA).toHaveBeenCalledOnce()
        } else {
          expect(queueDraftA).toHaveBeenCalledWith(capturedGraphA)
          expect(flushA).toHaveBeenCalledTimes(2)
        }
        expect(ensureFreshB).not.toHaveBeenCalled()
        expect(queueDraftB).not.toHaveBeenCalled()
        expect(flushB).not.toHaveBeenCalled()
        wrapper.unmount()
      },
    )

    it('aborts confirmed export when its root canvas was disposed', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const canvasB = canvasIdFromPanelId('workflow:b')
      useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
        getWorkflowId: () => 'a',
      })
      useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'b' },
        getWorkflowId: () => 'b',
      })
      const persistenceB = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
        canvasB,
        ROOT_PERSISTENCE_RESOURCE,
      )!
      const ensureFreshB = vi.spyOn(persistenceB, 'ensureFreshForCriticalOperation')
        .mockResolvedValue(true)
      const store = useWorkflowStore()
      const ui = useUIStore()
      const workflowA = { name: 'a', display_name: 'Workflow A' } as any
      const workflowB = { name: 'b', display_name: 'Workflow B' } as any
      store.workflows = [workflowA, workflowB]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      workflowMenu.items.find((item: any) => item.label === 'Export').command()
      canvasSessionRegistry.unregister(canvasA)
      canvasSessionRegistry.activate(canvasB)
      persistenceMocks.canvasId = canvasB
      store.current = workflowB
      await vm.confirmExportCurrentWorkflow()

      expect(apiMocks.put).not.toHaveBeenCalled()
      expect(apiMocks.post).not.toHaveBeenCalled()
      expect(ensureFreshB).not.toHaveBeenCalled()
      expect(persistenceMocks.ensureFreshForCriticalOperation).not.toHaveBeenCalled()
      expect(toastAdd).not.toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
      wrapper.unmount()
    })

    it('blocks save when unresolved remote draft changes need resolution', async () => {
      const { persistence } = registerActiveRootWorkflow({
        name: 'new_workflow',
        displayName: 'New workflow',
      })
      vi.mocked(persistence.ensureFreshForCriticalOperation).mockResolvedValueOnce(false)

      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      await workflowMenu.items.find((item: any) => item.label === 'Save').command()
      await flushPromises()

      expect(apiMocks.put).not.toHaveBeenCalled()
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        severity: 'warn',
        summary: 'Resolve workflow changes first',
      }))
    })

    it('blocks confirmed export when unresolved remote draft changes need resolution', async () => {
      const { persistence } = registerActiveRootWorkflow({
        name: 'cell_segmentation',
        displayName: 'Cell segmentation',
      })
      vi.mocked(persistence.ensureFreshForCriticalOperation).mockResolvedValueOnce(false)

      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      await workflowMenu.items.find((item: any) => item.label === 'Export').command()
      await flushPromises()
      expect(vm.exportSaveDialogVisible).toBe(true)
      await vm.confirmExportCurrentWorkflow()
      await flushPromises()

      expect(apiMocks.put).not.toHaveBeenCalled()
      expect(apiMocks.post).not.toHaveBeenCalled()
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        severity: 'warn',
        summary: 'Resolve workflow changes first',
      }))
    })

    it('creates a workflow under the folder selected in the workflows panel', async () => {
      apiMocks.post.mockResolvedValueOnce({
        data: {
          id: 'Analysis Results/nuclei',
          name: 'nuclei',
          folder: 'Analysis Results',
          display_name: 'Nuclei',
          path: '/tmp/Analysis Results/nuclei/workflow.json',
          last_modified: '2026-05-21T10:00:00Z',
          identity_generation: 8,
        },
      })
      const wrapper = mountMenuBar()
      const applied: any[] = []
      const onApply = (event: Event) => applied.push((event as CustomEvent).detail)
      window.addEventListener('bioimageflow:apply-graph', onApply)

      window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
        detail: { action: 'new', folderId: 'Analysis Results' },
      }))
      await flushPromises()
      const input = document.body.querySelector(
        '[data-testid="workflow-display-name-input"]',
      ) as HTMLInputElement
      input.value = 'Nuclei'
      input.dispatchEvent(new Event('input', { bubbles: true }))
      const submit = document.body.querySelector(
        '[data-testid="workflow-dialog-submit"]',
      ) as HTMLButtonElement
      submit.click()
      await flushPromises()

      expect(apiMocks.post).toHaveBeenCalledWith('/api/v1/workflows', {
        name: 'Analysis Results/nuclei',
        display_name: 'Nuclei',
        description: null,
      })
      expect(applied[applied.length - 1]).toMatchObject({
        workflowName: 'Analysis Results/nuclei',
        identityGeneration: 1,
        serverIdentityGeneration: 8,
      })
      window.removeEventListener('bioimageflow:apply-graph', onApply)
    })

    it('does not apply a workflow whose delayed creation finishes after execution starts', async () => {
      let resolveCreate!: (value: { data: Record<string, unknown> }) => void
      apiMocks.post.mockReturnValueOnce(new Promise((resolve) => {
        resolveCreate = resolve
      }))
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
      workflow.items.find((item: any) => item.label === 'New').command()
      const applied: unknown[] = []
      const onApply = (event: Event) => applied.push((event as CustomEvent).detail)
      window.addEventListener('bioimageflow:apply-graph', onApply)

      const submission = vm.onWorkflowDialogSubmit({
        name: 'delayed',
        folder: '',
        display_name: 'Delayed',
        description: null,
      })
      await vi.waitFor(() => expect(apiMocks.post).toHaveBeenCalledOnce())
      useExecutionStore().state = 'starting'
      resolveCreate({
        data: {
          name: 'delayed',
          folder: '',
          display_name: 'Delayed',
          path: '/tmp/delayed/workflow.json',
          last_modified: '2026-07-15T00:00:00Z',
      identity_generation: 0,
        },
      })
      await submission

      expect(applied).toEqual([])
      window.removeEventListener('bioimageflow:apply-graph', onApply)
      wrapper.unmount()
    })

    it('does not apply a delayed dependency rebind after remote workflow deletion', async () => {
      const { workflow } = registerActiveRootWorkflow()
      const response = deferred<any>()
      apiMocks.post.mockReturnValueOnce(response.promise)
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      vm.dependencyDialogVisible = true
      const applied: unknown[] = []
      const onApply = (event: Event) => applied.push((event as CustomEvent).detail)
      window.addEventListener('bioimageflow:apply-graph', onApply)

      const rebinding = vm.rebindImportedDependencies()
      await vi.waitFor(() => expect(apiMocks.post).toHaveBeenCalledWith(
        '/api/v1/workflows/wf_a/rebind-versions',
      ))
      await useWorkflowStore().forgetDeletedWorkflow('wf_a')
      response.resolve({
        data: {
          info: { ...workflow, display_name: 'Stale rebind' },
          graph: { nodes: [{ id: 'stale' }], edges: [] },
          missing_packages: [],
          missing_tools: [],
        },
      })
      await rebinding

      expect(applied).toEqual([])
      expect(vm.dependencyDialogVisible).toBe(true)
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        severity: 'error',
        summary: 'Dependency rebind failed',
      }))
      window.removeEventListener('bioimageflow:apply-graph', onApply)
    })

    it('clears captured delete state when the lifecycle request succeeds after execution locks', async () => {
      const { canvasId } = registerActiveRootWorkflow()
      let deletionRequest: WorkflowDeletionEventDetail | null = null
      const stopObserving = observeWorkflowDeletion((detail) => {
        deletionRequest = detail
      })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
      workflow.items.find((item: any) => item.label === 'Delete').command()
      const deletion = vm.confirmDeleteWorkflow()
      expect(deletionRequest).toMatchObject({ workflowName: 'wf_a', canvasId })
      useExecutionStore().state = 'starting'
      deletionRequest!.resolve()
      await deletion

      expect(vm.deleteDialogVisible).toBe(false)
      expect(vm.deleteTargetName).toBeNull()
      expect(vm.deleteCanvasTarget).toBeNull()
      stopObserving()
      wrapper.unmount()
    })

    it('shows the import rename dialog when upload returns a conflict', async () => {
      apiMocks.post.mockRejectedValueOnce(new AxiosError(
        'conflict',
        undefined,
        undefined,
        undefined,
        {
          status: 409,
          statusText: 'Conflict',
          headers: {},
          config: {} as any,
          data: {
            detail: "Workflow 'wf' already exists",
            suggested_name: 'wf_2',
          },
        },
      ))
      const wrapper = mountMenuBar()
      const input = wrapper.find('[data-testid="workflow-import-input"]')
      Object.defineProperty(input.element, 'files', {
        value: [new File(['zip'], 'wf.bioimageflow.zip', { type: 'application/zip' })],
        configurable: true,
      })

      await input.trigger('change')
      await flushPromises()

      const vm = wrapper.vm as any
      expect(vm.importRenameDialogVisible).toBe(true)
    })


    it('uses the platform dialog for workflow delete without creating a replacement workflow', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm')
      registerActiveRootWorkflow({ name: 'Untitled', displayName: 'Untitled' })
      const workflow = useWorkflowStore()
      const createWorkflow = vi.spyOn(workflow, 'createWorkflow')
      let deletionRequest: WorkflowDeletionEventDetail | null = null
      const stopObserving = observeWorkflowDeletion((detail) => {
        deletionRequest = detail
        detail.resolve()
      })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      workflowMenu.items.find((item: any) => item.label === 'Delete').command()
      await flushPromises()

      expect(confirmSpy).not.toHaveBeenCalled()
      expect(vm.deleteDialogVisible).toBe(true)
      await vm.confirmDeleteWorkflow()
      await flushPromises()

      expect(deletionRequest).toMatchObject({
        workflowName: 'Untitled',
        canvasId: canvasIdFromPanelId('workflow:Untitled'),
      })
      expect(createWorkflow).not.toHaveBeenCalled()
      stopObserving()
      confirmSpy.mockRestore()
    })

    it('uses the platform dialog for delete commands from the workflows panel', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm')
      const workflow = useWorkflowStore()
      workflow.workflows = [{
        id: 'Analysis/beta',
        name: 'beta',
        folder: 'Analysis',
        display_name: 'Beta',
        path: '/tmp/Analysis/beta/workflow.json',
        last_modified: '2026-05-22T08:00:00Z',
      identity_generation: 0,
      }]
      let deletionRequest: WorkflowDeletionEventDetail | null = null
      const stopObserving = observeWorkflowDeletion((detail) => {
        deletionRequest = detail
        detail.resolve()
      })
      const wrapper = mountMenuBar()

      window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
        detail: { action: 'delete', name: 'Analysis/beta' },
      }))
      await flushPromises()
      const vm = wrapper.vm as any

      expect(confirmSpy).not.toHaveBeenCalled()
      expect(vm.deleteDialogVisible).toBe(true)
      expect(vm.deleteDialogWorkflow.display_name).toBe('Beta')
      await vm.confirmDeleteWorkflow()
      await flushPromises()

      expect(deletionRequest).toMatchObject({
        workflowName: 'Analysis/beta',
        canvasId: null,
      })
      stopObserving()
      confirmSpy.mockRestore()
    })

    it('labels workflow display-name editing accurately', async () => {
      registerActiveRootWorkflow({
        name: 'cell_segmentation',
        displayName: 'Cell segmentation',
      })

      const wrapper = mountMenuBar()
      await wrapper.vm.$nextTick()

      const edit = wrapper.find('[data-testid="workflow-title-edit"]')
      expect(edit.exists()).toBe(true)
      expect(edit.attributes('aria-label')).toBe('Edit workflow display name')
      expect(edit.attributes('title')).toBe('Edit workflow display name')

      await edit.trigger('click')
      await flushPromises()
      const dialog = document.body.querySelector('[data-testid="rename-workflow-dialog"]')
      expect(dialog?.textContent).toContain('Edit workflow display name')
      expect(dialog?.textContent).toContain('Display name')
    })

    it('save success toast uses the workflow display name', async () => {
      const { persistence } = registerActiveRootWorkflow({
        name: 'new_workflow',
        displayName: 'New workflow',
      })
      apiMocks.put.mockResolvedValue({
        data: {
          name: 'new_workflow',
          folder: '',
          display_name: 'New workflow',
          path: '/tmp/new_workflow.json',
          last_modified: '2026-04-29T00:00:01Z',
      identity_generation: 0,
        },
      })

      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      await workflowMenu.items.find((item: any) => item.label === 'Save').command()

      expect(apiMocks.put).toHaveBeenCalledWith(
        '/api/v1/workflows/new_workflow',
        { graph: makeGraph() },
      )
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        summary: 'Workflow saved',
        detail: 'New workflow',
      }))
      expect(persistence.ensureFreshForCriticalOperation).toHaveBeenCalledOnce()
      expect(persistence.queueDraft).toHaveBeenCalledOnce()
      expect(persistence.flush).toHaveBeenCalledOnce()
      expect(workflowDraftMocks.ensureFreshForCriticalOperation).not.toHaveBeenCalled()
      expect(workflowDraftMocks.scheduleSave).not.toHaveBeenCalled()
      expect(workflowDraftMocks.flush).not.toHaveBeenCalled()
    })

    it('marks a fixed root canvas clean only after its captured graph finishes saving', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const graphA: GraphState = makeGraph()
      const workflowA = { name: 'a', display_name: 'Workflow A' } as WorkflowInfo
      const syncA = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
        getWorkflowId: () => 'a',
      })
      syncA.currentGraph.value = graphA
      const persistenceA = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
        canvasA,
        ROOT_PERSISTENCE_RESOURCE,
      )!
      vi.spyOn(persistenceA, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
      const queueDraft = vi.spyOn(persistenceA, 'queueDraft').mockImplementation(() => {})
      const flush = vi.spyOn(persistenceA, 'flush').mockResolvedValue(undefined)
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [workflowA]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.markCanvasDirty(canvasA)
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      apiMocks.put.mockResolvedValueOnce({ data: workflowA })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      await workflowMenu.items.find((item: any) => item.label === 'Save').command()

      expect(queueDraft).toHaveBeenCalledWith(graphA)
      expect(flush).toHaveBeenCalledOnce()
      expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(false)
      wrapper.unmount()
    })

    it('keeps Save bound to the graph captured before the freshness barrier', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const graphA: GraphState = makeGraph()
      const graphB: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'newer-node',
          name: 'Newer node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: { value: 'graph-b' },
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const workflowA = { name: 'a', display_name: 'Workflow A' } as WorkflowInfo
      const syncA = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
        getWorkflowId: () => 'a',
      })
      syncA.currentGraph.value = graphA
      const persistenceA = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
        canvasA,
        ROOT_PERSISTENCE_RESOURCE,
      )!
      const pendingFreshness = deferred<boolean>()
      vi.spyOn(persistenceA, 'ensureFreshForCriticalOperation')
        .mockReturnValueOnce(pendingFreshness.promise)
      const queueDraft = vi.spyOn(persistenceA, 'queueDraft').mockImplementation(() => {})
      const queueGraph = vi.spyOn(persistenceA, 'queueGraph').mockImplementation(() => {})
      vi.spyOn(persistenceA, 'flush').mockResolvedValue(undefined)
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [workflowA]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.markCanvasDirty(canvasA)
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      apiMocks.put.mockResolvedValueOnce({ data: workflowA })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      const saving = workflowMenu.items.find((item: any) => item.label === 'Save').command()
      await vi.waitFor(() => (
        expect(persistenceA.ensureFreshForCriticalOperation).toHaveBeenCalledOnce()
      ))
      syncA.currentGraph.value = graphB
      ui.markCanvasDirty(canvasA)
      pendingFreshness.resolve(true)
      await saving

      expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflows/a', { graph: graphA })
      expect(queueDraft).not.toHaveBeenCalled()
      expect(queueGraph).toHaveBeenCalledWith(graphB)
      expect(syncA.currentGraph.value).toEqual(graphB)
      expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(true)
      wrapper.unmount()
    })

    it('keeps preservation conservative when a newer edit converges back to graph A', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const graphA: GraphState = makeGraph()
      const graphB: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'temporary-node',
          name: 'Temporary node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const workflowA = { name: 'a', display_name: 'Workflow A' } as WorkflowInfo
      const syncA = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
        getWorkflowId: () => 'a',
      })
      syncA.currentGraph.value = graphA
      const persistenceA = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
        canvasA,
        ROOT_PERSISTENCE_RESOURCE,
      )!
      vi.spyOn(persistenceA, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
      const queueDraft = vi.spyOn(persistenceA, 'queueDraft').mockImplementation(() => {})
      vi.spyOn(persistenceA, 'queueGraph').mockImplementation(() => {})
      const pendingPreservation = deferred<void>()
      const flush = vi.spyOn(persistenceA, 'flush')
        .mockReturnValueOnce(pendingPreservation.promise)
        .mockResolvedValue(undefined)
      const pendingSave = deferred<{ data: WorkflowInfo }>()
      apiMocks.put.mockReturnValueOnce(pendingSave.promise)
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [workflowA]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.markCanvasDirty(canvasA)
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      const saving = workflowMenu.items.find((item: any) => item.label === 'Save').command()
      await vi.waitFor(() => expect(apiMocks.put).toHaveBeenCalledOnce())
      syncA.currentGraph.value = graphB
      ui.markCanvasDirty(canvasA)
      pendingSave.resolve({ data: workflowA })
      await vi.waitFor(() => expect(flush).toHaveBeenCalledOnce())

      syncA.currentGraph.value = graphA
      ui.markCanvasDirty(canvasA)
      pendingPreservation.resolve()
      await saving

      expect(queueDraft).not.toHaveBeenCalled()
      expect(flush).toHaveBeenCalledOnce()
      expect(syncA.currentGraph.value).toEqual(graphA)
      expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(true)
      wrapper.unmount()
    })

    it('preserves graph B when it lands after the preservation check resolves', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const graphA: GraphState = makeGraph()
      const graphB: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'newer-node',
          name: 'Newer node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const workflowA = { name: 'a', display_name: 'Workflow A' } as WorkflowInfo
      const syncA = useGraphSync({
        descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
        getWorkflowId: () => 'a',
      })
      const persistenceA = canvasSessionRegistry.getResource<RootCanvasPersistenceResource>(
        canvasA,
        ROOT_PERSISTENCE_RESOURCE,
      )!
      let liveGraph = graphA
      let injectNewerGraphOnRead = false
      Object.defineProperty(persistenceA, 'currentGraph', {
        configurable: true,
        value: {
          get value() {
            const result = liveGraph
            if (injectNewerGraphOnRead) {
              injectNewerGraphOnRead = false
              queueMicrotask(() => {
                liveGraph = graphB
                useUIStore().markCanvasDirty(canvasA)
              })
            }
            return result
          },
        },
      })
      vi.spyOn(persistenceA, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
      const queueDraft = vi.spyOn(persistenceA, 'queueDraft').mockImplementation((graph) => {
        liveGraph = graph
      })
      const queueGraph = vi.spyOn(persistenceA, 'queueGraph').mockImplementation((graph) => {
        liveGraph = graph
      })
      vi.spyOn(persistenceA, 'flush').mockResolvedValue(undefined)
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [workflowA]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.markCanvasDirty(canvasA)
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      apiMocks.put.mockImplementationOnce(async () => {
        injectNewerGraphOnRead = true
        return { data: workflowA }
      })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      await workflowMenu.items.find((item: any) => item.label === 'Save').command()

      expect(queueDraft).toHaveBeenCalledWith(graphA)
      expect(queueGraph).toHaveBeenCalledWith(graphB)
      expect(liveGraph).toEqual(graphB)
      expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(true)
      syncA.dispose()
      wrapper.unmount()
    })

    it('saves graph A while preserving graph B as the dirty accepted draft when the save PUT is delayed', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const canvasB = canvasIdFromPanelId('workflow:b')
      const graphA: GraphState = makeGraph()
      const graphB: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'newer-node',
          name: 'Newer node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: { value: 'graph-b' },
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const workflowA = { name: 'a', display_name: 'Workflow A' } as WorkflowInfo
      const workflowB = { name: 'b', display_name: 'Workflow B' } as WorkflowInfo
      let savedGraph = graphA
      let draftRevision = 1
      let acceptedDraft: WorkflowDraftResponse = {
        draft_version: 1,
        workflow_id: 'a',
        base_saved_revision: 'sha256:graph-a',
        draft_revision: draftRevision,
        updated_at: '2026-07-16T10:00:00Z',
        updated_by: 'frontend',
        dirty_against_saved: false,
        graph: graphA,
        validation: { valid: true, node_statuses: {}, errors: [] },
      }
      const descriptorA = { kind: 'root', canvasId: canvasA, workflowId: 'a' } as const
      canvasSessionRegistry.register(descriptorA)
      const persistenceA = getOrCreateRootPersistenceResource({
        descriptor: descriptorA,
        getWorkflowId: () => 'a',
        transports: {
          fetchDraft: vi.fn(async () => acceptedDraft),
          putDraft: vi.fn(async (_workflowId, body) => {
            draftRevision += 1
            acceptedDraft = {
              ...acceptedDraft,
              draft_revision: draftRevision,
              base_saved_revision: 'sha256:graph-a',
              dirty_against_saved: JSON.stringify(body.graph) !== JSON.stringify(savedGraph),
              graph: JSON.parse(JSON.stringify(body.graph)) as GraphState,
            }
            return acceptedDraft
          }),
          writeRecovery: vi.fn(async () => {}),
        },
      })
      persistenceA.initializeFromDraft(acceptedDraft)
      canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [workflowA, workflowB]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
      ui.markCanvasDirty(canvasA)
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      const pendingSave = deferred<{ data: WorkflowInfo }>()
      apiMocks.put.mockReturnValueOnce(pendingSave.promise)
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      const saving = workflowMenu.items.find((item: any) => item.label === 'Save').command()
      await vi.waitFor(() => expect(apiMocks.put).toHaveBeenCalledOnce())
      expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflows/a', { graph: graphA })

      persistenceA.queueGraph(graphB)
      ui.markCanvasDirty(canvasA)
      canvasSessionRegistry.activate(canvasB)
      persistenceMocks.canvasId = canvasB
      store.current = workflowB
      savedGraph = JSON.parse(JSON.stringify(graphA)) as GraphState
      pendingSave.resolve({ data: workflowA })
      await saving

      expect(savedGraph).toEqual(graphA)
      expect(acceptedDraft.graph).toEqual(graphB)
      expect(acceptedDraft.dirty_against_saved).toBe(true)
      expect(persistenceA.currentGraph.value).toEqual(graphB)
      expect(persistenceA.acceptedDraftRevision.value).toBe(draftRevision)
      expect(persistenceA.isPending.value).toBe(false)
      expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(true)
      expect(store.currentName).toBe('b')
      wrapper.unmount()
    })

    it('keeps graph B dirty and accepted when it is edited during the graph A draft flush', async () => {
      const canvasA = canvasIdFromPanelId('workflow:a')
      const graphA: GraphState = makeGraph()
      const graphB: GraphState = makeGraph({
        nodes: [{
          type: 'tool',
          id: 'newer-node',
          name: 'Newer node',
          tool_name: 'tool',
          position: [0, 0],
          parameters: { value: 'graph-b' },
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })
      const workflowA = { name: 'a', display_name: 'Workflow A' } as WorkflowInfo
      let draftRevision = 1
      let acceptedDraft: WorkflowDraftResponse = {
        draft_version: 1,
        workflow_id: 'a',
        base_saved_revision: 'sha256:graph-a',
        draft_revision: draftRevision,
        updated_at: '2026-07-16T10:00:00Z',
        updated_by: 'frontend',
        dirty_against_saved: false,
        graph: graphA,
        validation: { valid: true, node_statuses: {}, errors: [] },
      }
      const pendingDraftA = deferred<WorkflowDraftResponse>()
      const putDraft = vi.fn((_workflowId: string, body: { graph: GraphState }) => {
        if (putDraft.mock.calls.length === 1) return pendingDraftA.promise
        draftRevision += 1
        acceptedDraft = {
          ...acceptedDraft,
          draft_revision: draftRevision,
          dirty_against_saved: JSON.stringify(body.graph) !== JSON.stringify(graphA),
          graph: JSON.parse(JSON.stringify(body.graph)) as GraphState,
        }
        return Promise.resolve(acceptedDraft)
      })
      const descriptorA = { kind: 'root', canvasId: canvasA, workflowId: 'a' } as const
      canvasSessionRegistry.register(descriptorA)
      const persistenceA = getOrCreateRootPersistenceResource({
        descriptor: descriptorA,
        getWorkflowId: () => 'a',
        transports: {
          fetchDraft: vi.fn(async () => acceptedDraft),
          putDraft,
          writeRecovery: vi.fn(async () => {}),
        },
      })
      persistenceA.initializeFromDraft(acceptedDraft)
      const store = useWorkflowStore()
      const ui = useUIStore()
      store.workflows = [workflowA]
      store.current = workflowA
      ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
      ui.markCanvasDirty(canvasA)
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      apiMocks.put.mockResolvedValueOnce({ data: workflowA })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      const saving = workflowMenu.items.find((item: any) => item.label === 'Save').command()
      await vi.waitFor(() => expect(putDraft).toHaveBeenCalledOnce())
      expect(putDraft.mock.calls[0]?.[1]).toEqual(expect.objectContaining({ graph: graphA }))

      persistenceA.queueGraph(graphB)
      ui.markCanvasDirty(canvasA)
      draftRevision += 1
      acceptedDraft = {
        ...acceptedDraft,
        draft_revision: draftRevision,
        dirty_against_saved: false,
        graph: graphA,
      }
      pendingDraftA.resolve(acceptedDraft)
      await saving

      expect(putDraft).toHaveBeenCalledTimes(3)
      expect(putDraft.mock.calls[putDraft.mock.calls.length - 1]?.[1]).toEqual(expect.objectContaining({
        graph: graphB,
      }))
      expect(acceptedDraft.graph).toEqual(graphB)
      expect(acceptedDraft.dirty_against_saved).toBe(true)
      expect(persistenceA.currentGraph.value).toEqual(graphB)
      expect(persistenceA.acceptedDraftRevision.value).toBe(draftRevision)
      expect(persistenceA.isPending.value).toBe(false)
      expect(ui.canvasHasUnsavedChanges(canvasA)).toBe(true)
      wrapper.unmount()
    })

    it('keeps Save bound to its root when another canvas activates during freshness', async () => {
      const { workflow: workflowA, persistence: persistenceA } = registerActiveRootWorkflow({
        name: 'a',
        displayName: 'Workflow A',
      })
      const { canvasId: canvasB, persistence: persistenceB } = registerActiveRootWorkflow({
        name: 'b',
        displayName: 'Workflow B',
      })
      const canvasA = canvasIdFromPanelId('workflow:a')
      canvasSessionRegistry.activate(canvasA)
      persistenceMocks.canvasId = canvasA
      const pendingFreshness = deferred<boolean>()
      vi.mocked(persistenceA.ensureFreshForCriticalOperation)
        .mockReturnValueOnce(pendingFreshness.promise)
      apiMocks.put.mockResolvedValueOnce({ data: workflowA })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      const save = workflowMenu.items.find((item: any) => item.label === 'Save').command()
      await flushPromises()
      expect(persistenceA.ensureFreshForCriticalOperation).toHaveBeenCalledOnce()

      canvasSessionRegistry.activate(canvasB)
      persistenceMocks.canvasId = canvasB
      pendingFreshness.resolve(true)
      await save

      expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflows/a', {
        graph: makeGraph(),
      })
      expect(persistenceA.queueDraft).toHaveBeenCalledWith(makeGraph())
      expect(persistenceA.flush).toHaveBeenCalledOnce()
      expect(persistenceB.ensureFreshForCriticalOperation).not.toHaveBeenCalled()
      expect(persistenceB.queueDraft).not.toHaveBeenCalled()
    })

    it('routes Save to an active nested canvas without saving the root workflow', async () => {
      const parentCanvasId = canvasIdFromPanelId('workflow:wf_a')
      const nestedCanvasId = canvasIdFromPanelId('nested-workflow:nested-a')
      canvasSessionRegistry.register({
        kind: 'root',
        canvasId: parentCanvasId,
        workflowId: 'wf_a',
      })
      canvasSessionRegistry.register({
        kind: 'nested',
        canvasId: nestedCanvasId,
        sessionId: 'nested-a',
        parentCanvasId,
      })
      useUIStore().setCanvasWorkflow(nestedCanvasId, 'wf_a', 'Nested A')
      canvasSessionRegistry.activate(nestedCanvasId)
      persistenceMocks.canvasId = nestedCanvasId
      canvasCommandMocks.routeSave.mockResolvedValueOnce('nested')
      const saveRoot = vi.spyOn(useWorkflowStore(), 'saveWorkflow')
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

      await workflowMenu.items.find((item: any) => item.label === 'Save').command()
      await flushPromises()

      expect(canvasCommandMocks.routeSave).toHaveBeenCalledOnce()
      expect(saveRoot).not.toHaveBeenCalled()
      expect(persistenceMocks.ensureFreshForCriticalOperation).not.toHaveBeenCalled()
    })
  })

  describe('Edit menu', () => {
    it('enables commands that are implemented by the canvas', () => {
      registerActiveRootWorkflow()
      const store = useUIStore()
      store.setSelectedNodes(['n1'])
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const edit = vm.menuItems.find((item: any) => item.label === 'Edit')

      expect(edit.items.find((item: any) => item.label === 'Undo').disabled).toBe(false)
      expect(edit.items.find((item: any) => item.label === 'Redo').disabled).toBe(false)
      expect(edit.items.find((item: any) => item.label === 'Cut').disabled).toBe(false)
      expect(edit.items.find((item: any) => item.label === 'Copy').disabled).toBe(false)
      expect(edit.items.find((item: any) => item.label === 'Paste').disabled).toBe(false)
      expect(edit.items.find((item: any) => item.label === 'Select All').disabled).toBe(false)
    })

    it('dispatches canvas edit commands', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const dispatched: string[] = []
      window.addEventListener('bioimageflow:edit-command', ((event: CustomEvent) => {
        dispatched.push(event.detail.command)
      }) as EventListener)

      const edit = vm.menuItems.find((item: any) => item.label === 'Edit')
      edit.items.find((item: any) => item.label === 'Copy').command()
      edit.items.find((item: any) => item.label === 'Paste').command()

      expect(dispatched).toEqual(['copy', 'paste'])
    })

    it('makes About functional', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const help = vm.menuItems.find((item: any) => item.label === 'Help')
      const about = help.items.find((item: any) => item.label === 'About')

      expect(about.disabled).toBeFalsy()
      about.command()
      expect(vm.aboutDialogVisible).toBe(true)
    })
  })

  describe('Execution menu', () => {
    it('exposes workflow, retry, recompute, and stop entries', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const exec = vm.menuItems.find((item: any) => item.label === 'Execution')
      expect(exec.items.map((i: any) => i.label).filter(Boolean)).toEqual([
        'Run Workflow',
        'Run Selected',
        'Retry Failed Execution',
        'Invalidate Failed Nodes and Retry…',
        'Recompute Workflow…',
        'Stop',
      ])
    })

    it('Run Workflow is enabled when idle', () => {
      registerActiveRootWorkflow()
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const exec = vm.menuItems.find((item: any) => item.label === 'Execution')
      const run = exec.items.find((i: any) => i.label === 'Run Workflow')
      expect(run.disabled).toBe(false)
    })

    it('Run Selected is disabled when no nodes selected', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const exec = vm.menuItems.find((item: any) => item.label === 'Execution')
      const runSelected = exec.items.find(
        (i: any) => i.label === 'Run Selected',
      )
      expect(runSelected.disabled).toBe(true)
    })

    it('Run Selected is enabled when nodes are selected', async () => {
      registerActiveRootWorkflow()
      const store = useUIStore()
      store.setSelectedNodes(['n1'])
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const exec = vm.menuItems.find((item: any) => item.label === 'Execution')
      const runSelected = exec.items.find(
        (i: any) => i.label === 'Run Selected',
      )
      expect(runSelected.disabled).toBe(false)
    })

    it('disables Run commands for an active nested canvas', () => {
      const parentCanvasId = canvasIdFromPanelId('workflow:a')
      const nestedCanvasId = canvasIdFromPanelId('nested-workflow:nested-a')
      canvasSessionRegistry.register({
        kind: 'root',
        canvasId: parentCanvasId,
        workflowId: 'wf_a',
      })
      canvasSessionRegistry.register({
        kind: 'nested',
        canvasId: nestedCanvasId,
        sessionId: 'nested-a',
        parentCanvasId,
      })
      const ui = useUIStore()
      ui.setCanvasWorkflow(nestedCanvasId, 'wf_a', 'Nested A')
      ui.setCanvasSelectedNodes(nestedCanvasId, ['nested-node'])
      canvasSessionRegistry.activate(nestedCanvasId)
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const execution = vm.menuItems.find((item: any) => item.label === 'Execution')

      expect(execution.items.find((item: any) => item.label === 'Run Workflow').disabled)
        .toBe(true)
      expect(execution.items.find((item: any) => item.label === 'Run Selected').disabled)
        .toBe(true)
    })

    it.each(['starting', 'stopping'] as const)(
      'locks workflow and edit actions while execution is %s',
      async (phase) => {
        registerActiveRootWorkflow()
        useUIStore().setSelectedNodes(['n1'])
        useExecutionStore().state = phase
        const wrapper = mountMenuBar()
        const vm = wrapper.vm as any
        const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
        const edit = vm.menuItems.find((item: any) => item.label === 'Edit')
        const execution = vm.menuItems.find((item: any) => item.label === 'Execution')

        expect(workflow.items.every((item: any) => item.disabled)).toBe(true)
        expect(edit.items.filter((item: any) => !item.separator && item.label !== 'Preferences...')
          .every((item: any) => item.disabled)).toBe(true)
        expect(execution.items.find((item: any) => item.label === 'Run Workflow').disabled)
          .toBe(true)
        expect(execution.items.find((item: any) => item.label === 'Stop').disabled)
          .toBe(true)
        expect(wrapper.find('[data-testid="workflow-title-edit"]').attributes('disabled'))
          .toBeDefined()
      },
    )

    it.each(['starting', 'stopping'] as const)(
      'ignores workflow mutation commands while execution is %s',
      async (phase) => {
        registerActiveRootWorkflow()
        useExecutionStore().state = phase
        const wrapper = mountMenuBar()
        const vm = wrapper.vm as any
        const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
        canvasCommandMocks.routeSave.mockClear()

        workflow.items.find((item: any) => item.label === 'Save').command()
        await flushPromises()

        expect(canvasCommandMocks.routeSave).not.toHaveBeenCalled()
        wrapper.unmount()
      },
    )

    it('renders RunButton in the end slot', () => {
      const wrapper = mountMenuBar()
      expect(
        wrapper.find('[data-testid="run-button-group"]').exists(),
      ).toBe(true)
    })
  })

  describe('ErrorIndicator wiring', () => {
    it('renders the indicator when errors are reported', () => {
      const errors = useErrorStore()
      errors.report({ kind: 'graph_sync_error', detail: 'down' })
      const wrapper = mountMenuBar()
      expect(wrapper.find('.error-indicator').exists()).toBe(true)
    })

    it('clicking the indicator opens the history panel local state', async () => {
      const errors = useErrorStore()
      errors.report({ kind: 'graph_sync_error', detail: 'down' })
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as unknown as { historyPanelOpen: boolean }
      expect(vm.historyPanelOpen).toBe(false)
      await wrapper.find('.error-indicator').trigger('click')
      expect(vm.historyPanelOpen).toBe(true)
    })
  })
})
