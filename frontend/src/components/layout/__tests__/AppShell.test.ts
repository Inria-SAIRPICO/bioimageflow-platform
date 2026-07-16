import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import Aura from '@primevue/themes/aura'
import App from '@/App.vue'
import { api } from '@/api/client'
import MenuBar from '@/components/layout/MenuBar.vue'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useSubWorkflowSessionsStore } from '@/stores/subWorkflowSessions'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { useCanvasLifecycleStore } from '@/stores/canvasLifecycle'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import {
  _resetGraphSyncForTest,
  forgetRetainedNestedSnapshot,
  graphSyncCanvasSessions,
  useGraphSync,
} from '@/composables/useGraphSync'
import {
  CanvasDiscardRecoveryCleanupError,
  getRootCanvasPersistenceResource,
  useCanvasPersistence,
} from '@/composables/useCanvasPersistence'
import {
  useAutoSave,
  writeAutoSaveEntry,
} from '@/composables/useAutoSave'
import { openAcceptedNestedSession } from '@/test-utils/nestedSessionFixtures'
import { loadRootWorkflowPresentation } from '@/services/rootWorkflowPresentation'
import {
  WorkflowDeletionCommittedCleanupError,
  WorkflowDeletionTargetChangedError,
} from '@/services/workflowDeletion'

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

async function clickLatestTestId(testId: string): Promise<void> {
  await flushPromises()
  const matches = document.querySelectorAll<HTMLElement>(`[data-testid="${testId}"]`)
  const target = matches.item(matches.length - 1)
  expect(target).toBeTruthy()
  target.click()
  await flushPromises()
}

function capturedWorkflowDeletionTarget(
  workflowName: string,
  canvasId: ReturnType<typeof canvasIdFromPanelId> | null,
) {
  const workflow = useWorkflowStore()
  const session = canvasId === null ? null : canvasSessionRegistry.get(canvasId)
  return {
    workflowName,
    canvasId,
    localIdentityGeneration: workflow.workflowIdentityGeneration(workflowName),
    serverIdentityGeneration: workflow.workflowServerIdentityGeneration(workflowName),
    sessionRegistrationToken: session?.registrationToken ?? null,
  }
}

const {
  connectMock,
  disconnectMock,
  resolveStartupWorkflowMock,
  saveRootWorkflowTargetMock,
} = vi.hoisted(() => ({
  connectMock: vi.fn(),
  disconnectMock: vi.fn(),
  resolveStartupWorkflowMock: vi.fn(),
  saveRootWorkflowTargetMock: vi.fn(),
}))

const nestedSnapshotMocks = vi.hoisted(() => ({
  open: vi.fn(),
  get: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/services/startupWorkflow', () => ({
  resolveStartupWorkflow: resolveStartupWorkflowMock,
}))

vi.mock('@/services/rootWorkflowSave', () => ({
  saveRootWorkflowTarget: saveRootWorkflowTargetMock,
}))

vi.mock('@/api/nestedWorkflowSnapshots', () => ({
  openNestedWorkflowSnapshot: nestedSnapshotMocks.open,
  getNestedWorkflowSnapshot: nestedSnapshotMocks.get,
  putNestedWorkflowSnapshot: nestedSnapshotMocks.put,
  deleteNestedWorkflowSnapshot: nestedSnapshotMocks.delete,
}))

// Vue Flow uses ResizeObserver
globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock dockview-vue at module level
const mockDockviewApi = {
  addPanel: vi.fn(),
  addPopoutGroup: vi.fn(),
  getPanel: vi.fn(),
  removePanel: vi.fn(),
  onDidRemovePanel: vi.fn(),
  onDidActivePanelChange: vi.fn(),
}
vi.mock('dockview-vue', () => ({
  DockviewVue: {
    name: 'DockviewVue',
    template: '<div class="dockview-stub" data-testid="dockview-container"><slot /></div>',
    emits: ['ready'],
    mounted() {
      (this as any).$emit('ready', { api: mockDockviewApi })
    },
  },
}))

vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    connectionState: { value: 'disconnected' },
    connect: connectMock,
    disconnect: disconnectMock,
    sendSubscribeLogs: vi.fn(),
  }),
}))

// PrimeVue Menubar uses matchMedia
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

let pinia: ReturnType<typeof createPinia>
const panels = new Map<string, any>()
const removePanelListeners = new Set<(panel: any) => void>()
const activePanelListeners = new Set<(event: any) => void>()
const mountedWrappers: Array<{ unmount(): void }> = []

function emitDockviewPanelRemoved(panel: any) {
  panels.delete(panel.id)
  removePanelListeners.forEach((listener) => listener(panel))
}

function getViewMenuItem(wrapper: ReturnType<typeof mount>, label: string) {
  const menuBar = wrapper.findComponent(MenuBar)
  const vm = menuBar.vm as any
  const viewMenu = vm.menuItems.find((item: any) => item.label === 'View')
  return viewMenu.items.find((item: any) => item.label === label)
}

function mountApp() {
  // Reset mock state
  panels.clear()
  removePanelListeners.clear()
  activePanelListeners.clear()
  mockDockviewApi.addPanel.mockReset()
  mockDockviewApi.addPanel.mockImplementation((options: any) => {
    const panel = {
      id: options.id,
      title: options.title,
      params: options.params,
      api: {
        setVisible: vi.fn(),
        setTitle: vi.fn((title: string) => {
          panel.title = title
        }),
        setActive: vi.fn(() => {
          activePanelListeners.forEach((listener) => listener({ panel }))
        }),
      },
    }
    panels.set(options.id, panel)
    return panel
  })
  mockDockviewApi.addPopoutGroup.mockReset()
  mockDockviewApi.addPopoutGroup.mockResolvedValue(true)
  mockDockviewApi.getPanel.mockReset()
  mockDockviewApi.getPanel.mockImplementation((id: string) => panels.get(id))
  mockDockviewApi.removePanel.mockReset()
  mockDockviewApi.removePanel.mockImplementation((panel: any) => {
    panels.delete(panel.id)
    removePanelListeners.forEach((listener) => listener(panel))
  })
  mockDockviewApi.onDidRemovePanel.mockReset()
  mockDockviewApi.onDidRemovePanel.mockImplementation((listener: (panel: any) => void) => {
    removePanelListeners.add(listener)
    return {
      dispose: () => removePanelListeners.delete(listener),
    }
  })
  mockDockviewApi.onDidActivePanelChange.mockReset()
  mockDockviewApi.onDidActivePanelChange.mockImplementation((listener: (event: any) => void) => {
    activePanelListeners.add(listener)
    return {
      dispose: () => activePanelListeners.delete(listener),
    }
  })

  const wrapper = mount(App, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }], ConfirmationService],
      stubs: {
        ToolsPanel: { template: '<div data-testid="panel-tools">Tools stub</div>' },
        WorkflowsPanel: { template: '<div data-testid="panel-workflows">Workflows stub</div>' },
        CanvasView: { template: '<div data-testid="panel-canvas">Canvas stub</div>' },
      },
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('AppShell', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    window.localStorage.clear()
    document.documentElement.classList.remove('bif-dark-theme')
    document.documentElement.style.colorScheme = ''
    connectMock.mockClear()
    disconnectMock.mockClear()
    resolveStartupWorkflowMock.mockReset()
    resolveStartupWorkflowMock.mockResolvedValue({
      workflowName: 'startup',
      workflowDisplayName: 'Startup',
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      missingTools: [],
      dirty: false,
      identityGeneration: 0,
    })
    saveRootWorkflowTargetMock.mockReset()
    saveRootWorkflowTargetMock.mockResolvedValue({
      status: 'saved',
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      info: {
        id: 'startup',
        name: 'startup',
        display_name: 'Startup',
      },
    })
    useWorkflowStore().workflows = [{
      id: 'startup',
      name: 'startup',
      display_name: 'Startup',
    }] as any
    nestedSnapshotMocks.open.mockReset()
    nestedSnapshotMocks.get.mockReset()
    nestedSnapshotMocks.put.mockReset()
    nestedSnapshotMocks.delete.mockReset()
    _resetGraphSyncForTest()
  })

  afterEach(async () => {
    await flushPromises()
    for (const wrapper of mountedWrappers.splice(0)) wrapper.unmount()
    await flushPromises()
    await flushPromises()
  })

  it('renders #bioimageflow-app wrapper', () => {
    const wrapper = mountApp()
    expect(wrapper.find('#bioimageflow-app').exists()).toBe(true)
  })

  it('renders MenuBar', () => {
    const wrapper = mountApp()
    expect(wrapper.find('[data-testid="app-menubar"]').exists()).toBe(true)
  })

  it('renders DockviewVue container', () => {
    const wrapper = mountApp()
    expect(wrapper.find('.dockview-wrapper').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dockview-container"]').exists()).toBe(true)
  })

  it('applies the dark theme class from the UI store', async () => {
    useUIStore().setThemePreference('dark')
    mountApp()
    await flushPromises()

    expect(document.documentElement.classList.contains('bif-dark-theme')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('connects the WebSocket on startup', async () => {
    mountApp()
    await flushPromises()
    expect(connectMock).toHaveBeenCalledTimes(1)
  })

  it('registers the default panels on ready', async () => {
    const wrapper = mountApp()
    await flushPromises()
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(7)

    const panelIds = mockDockviewApi.addPanel.mock.calls.map((call: any) => call[0].id)
    expect(panelIds).toContain('tools')
    expect(panelIds).toContain('workflows')
    expect(panelIds).toContain('workflow:startup')
    expect(panelIds).toContain('canvas-loading')
    expect(panelIds).not.toContain('canvas')
    expect(panelIds).toContain('nodePanel')
    expect(panelIds).toContain('dataTable')
    expect(panelIds).toContain('logger')
    expect(panelIds).not.toContain('codeEditor')
  })

  it('makes the Data Table the active bottom panel by default', async () => {
    mountApp()
    await flushPromises()

    expect(panels.get('dataTable').api.setActive).toHaveBeenCalledTimes(1)
    expect(panels.get('logger').api.setActive).not.toHaveBeenCalled()
  })

  it('does not poll execution status while execution is running', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval')
    useExecutionStore().state = 'running'

    mountApp()
    await flushPromises()

    expect(setIntervalSpy).not.toHaveBeenCalled()
    setIntervalSpy.mockRestore()
  })

  it('tools panel has initialWidth of 320', async () => {
    mountApp()
    await flushPromises()
    const toolsCall = mockDockviewApi.addPanel.mock.calls.find(
      (call: any) => call[0].id === 'tools',
    )
    expect(toolsCall).toBeDefined()
    expect(toolsCall![0].initialWidth).toBe(320)
  })

  it('workflows panel docks with the tools panel', async () => {
    mountApp()
    await flushPromises()
    const workflowsCall = mockDockviewApi.addPanel.mock.calls.find(
      (call: any) => call[0].id === 'workflows',
    )
    expect(workflowsCall).toBeDefined()
    expect(workflowsCall![0]).toMatchObject({
      component: 'workflows',
      title: 'Workflows',
      position: { referencePanel: 'tools', direction: 'within' },
    })
  })

  it('nodePanel has initialWidth of 320', async () => {
    mountApp()
    await flushPromises()
    const nodePanelCall = mockDockviewApi.addPanel.mock.calls.find(
      (call: any) => call[0].id === 'nodePanel',
    )
    expect(nodePanelCall).toBeDefined()
    expect(nodePanelCall![0].initialWidth).toBe(320)
  })

  // Task 3: Panel Visibility Sync tests
  it('togglePanel removes panel from dockview', async () => {
    mountApp()
    await flushPromises()

    const store = useUIStore()
    store.togglePanel('tools') // tools: true -> false
    await flushPromises()

    expect(mockDockviewApi.removePanel).toHaveBeenCalled()
    const removedPanel = mockDockviewApi.removePanel.mock.calls
      .map((call: any) => call[0])
      .find((panel: any) => panel.id === 'tools')
    expect(removedPanel.id).toBe('tools')
  })

  it('togglePanel re-adds panel to dockview', async () => {
    mountApp()
    await flushPromises()

    const store = useUIStore()
    store.togglePanel('tools') // hide
    await flushPromises()
    store.togglePanel('tools') // show again
    await flushPromises()

    // Loading placeholder + five fixed panels + canonical startup + one re-add.
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(8)
    const lastCall = mockDockviewApi.addPanel.mock.calls[7][0]
    expect(lastCall.id).toBe('tools')
    expect(lastCall.initialWidth).toBe(320)
  })

  it('syncs direct Dockview panel close with store and View menu state', async () => {
    const wrapper = mountApp()
    await flushPromises()

    const store = useUIStore()
    expect(store.panels.tools).toBe(true)
    expect(store.panels.workflows).toBe(true)
    expect(getViewMenuItem(wrapper, 'Tools Panel').icon).toBe('pi pi-check')
    expect(getViewMenuItem(wrapper, 'Workflows Panel').icon).toBe('pi pi-check')

    emitDockviewPanelRemoved(panels.get('tools'))
    await flushPromises()

    expect(store.panels.tools).toBe(false)
    expect(getViewMenuItem(wrapper, 'Tools Panel').icon).toBeUndefined()

    getViewMenuItem(wrapper, 'Tools Panel').command()
    await flushPromises()

    expect(store.panels.tools).toBe(true)
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(8)
    expect(mockDockviewApi.addPanel.mock.calls[7][0].id).toBe('tools')
  })

  it('syncs the Workflows panel with the View menu', async () => {
    const wrapper = mountApp()
    await flushPromises()

    const store = useUIStore()
    const workflowsPanel = panels.get('workflows')
    getViewMenuItem(wrapper, 'Workflows Panel').command()
    await flushPromises()

    expect(store.panels.workflows).toBe(false)
    expect(mockDockviewApi.removePanel).toHaveBeenCalledWith(workflowsPanel)

    getViewMenuItem(wrapper, 'Workflows Panel').command()
    await flushPromises()

    expect(store.panels.workflows).toBe(true)
    const lastCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ][0]
    expect(lastCall).toMatchObject({
      id: 'workflows',
      component: 'workflows',
      title: 'Workflows',
    })
  })

  it('canvas panel is not toggleable', () => {
    const store = useUIStore()
    expect('canvas' in store.panels).toBe(false)
  })

  it('creates and activates the Code Editor panel on embedded open events', async () => {
    mountApp()
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: { url: 'http://127.0.0.1:32344', path: '/tmp/tool.py' },
    }))
    await flushPromises()

    expect(useUIStore().codeEditorUrl).toBe('http://127.0.0.1:32344')
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(8)
    const codeEditorCall = mockDockviewApi.addPanel.mock.calls[7][0]
    expect(codeEditorCall.id).toBe('codeEditor')
    expect(codeEditorCall.tabComponent).toBe('codeEditorTab')
    expect(codeEditorCall.initialWidth).toBe(520)
    expect(codeEditorCall.position).toEqual({
      referencePanel: 'nodePanel',
      direction: 'right',
    })
    expect(panels.get('codeEditor').api.setActive).toHaveBeenCalled()
  })

  it('does not reactivate the Code Editor panel when the editor URL is unchanged', async () => {
    mountApp()
    await flushPromises()
    const store = useUIStore()
    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: {
        url: 'http://127.0.0.1:32344/?folder=%2Fworkspace',
        path: '/workspace/tools/old.py',
        projectPath: '/workspace',
      },
    }))
    await flushPromises()
    panels.get('codeEditor').api.setActive.mockClear()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: {
        url: 'http://127.0.0.1:32344/?folder=%2Fworkspace',
        path: '/workspace/tools/new.py',
        projectPath: '/workspace',
      },
    }))
    await flushPromises()

    expect(store.codeEditorUrl).toBe('http://127.0.0.1:32344/?folder=%2Fworkspace')
    expect(store.codeEditorPath).toBe('/workspace/tools/new.py')
    expect(store.codeEditorProjectPath).toBe('/workspace')
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(8)
    expect(panels.get('codeEditor').api.setActive).not.toHaveBeenCalled()
  })

  it('reactivates the Code Editor panel when the editor URL changes', async () => {
    mountApp()
    await flushPromises()
    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: {
        url: 'http://127.0.0.1:32344/?folder=%2Fworkspace-a',
        path: '/workspace-a/tools/old.py',
        projectPath: '/workspace-a',
      },
    }))
    await flushPromises()
    panels.get('codeEditor').api.setActive.mockClear()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: {
        url: 'http://127.0.0.1:32344/?folder=%2Fworkspace-b',
        path: '/workspace-b/tools/new.py',
        projectPath: '/workspace-b',
      },
    }))
    await flushPromises()

    expect(useUIStore().codeEditorUrl).toBe('http://127.0.0.1:32344/?folder=%2Fworkspace-b')
    expect(panels.get('codeEditor').api.setActive).toHaveBeenCalled()
  })

  it('creates and activates the Code Editor panel while embedded editor is opening', async () => {
    mountApp()
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading', {
      detail: { path: '/tmp/tool.py' },
    }))
    await flushPromises()

    const store = useUIStore()
    expect(store.codeEditorPath).toBe('/tmp/tool.py')
    expect(store.codeEditorOpening).toBe(true)
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(8)
    expect(mockDockviewApi.addPanel.mock.calls[7][0].id).toBe('codeEditor')
    expect(mockDockviewApi.addPanel.mock.calls[7][0].tabComponent).toBe('codeEditorTab')
    expect(panels.get('codeEditor').api.setActive).toHaveBeenCalled()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading-finished'))
    await flushPromises()

    expect(store.codeEditorOpening).toBe(false)
  })

  it('keeps the active code editor path during pathless loading events', async () => {
    mountApp()
    await flushPromises()
    const store = useUIStore()
    window.dispatchEvent(new CustomEvent('bif:open-code-editor', {
      detail: {
        url: 'http://127.0.0.1:32344/?folder=%2Fworkspace',
        path: '/workspace/tools/tool.py',
      },
    }))
    await flushPromises()
    panels.get('codeEditor').api.setActive.mockClear()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading', {
      detail: { path: '' },
    }))
    await flushPromises()

    expect(store.codeEditorUrl).toBe('http://127.0.0.1:32344/?folder=%2Fworkspace')
    expect(store.codeEditorPath).toBe('/workspace/tools/tool.py')
    expect(store.codeEditorOpening).toBe(true)
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(8)
    expect(panels.get('codeEditor').api.setActive).not.toHaveBeenCalled()
  })

  it('keeps the active code editor path during loading events when an editor is mounted', async () => {
    mountApp()
    await flushPromises()
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Fworkspace',
      '/workspace/tools/old.py',
    )

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading', {
      detail: { path: '/workspace/tools/new.py' },
    }))
    await flushPromises()

    expect(store.codeEditorUrl).toBe('http://127.0.0.1:32344/?folder=%2Fworkspace')
    expect(store.codeEditorPath).toBe('/workspace/tools/old.py')
    expect(store.codeEditorOpening).toBe(true)

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading-finished', {
      detail: { path: '/workspace/tools/new.py' },
    }))
    await flushPromises()

    expect(store.codeEditorPath).toBe('/workspace/tools/old.py')
    expect(store.codeEditorOpening).toBe(false)
  })

  it('ignores stale code editor loading-finished events', async () => {
    mountApp()
    await flushPromises()
    const store = useUIStore()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading', {
      detail: { path: '/workspace/tools/old.py', requestId: 1 },
    }))
    await flushPromises()
    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading', {
      detail: { path: '/workspace/tools/new.py', requestId: 2 },
    }))
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading-finished', {
      detail: { path: '/workspace/tools/old.py', requestId: 1 },
    }))
    await flushPromises()

    expect(store.codeEditorOpening).toBe(true)
    expect(store.codeEditorOpeningPath).toBe('/workspace/tools/new.py')

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading-finished', {
      detail: { path: '/workspace/tools/new.py', requestId: 2 },
    }))
    await flushPromises()

    expect(store.codeEditorOpening).toBe(false)
  })

  it('opens Avivator in a Dockview panel from image-cell events', async () => {
    mountApp()
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bioimageflow:open-avivator', {
      detail: {
        url: 'http://avivator.gehlenborglab.org/?image_url=http%3A%2F%2Flocalhost%2Fimage.ome.tif',
        imageUrl: 'http://localhost/image.ome.tif',
        title: 'image.ome.tif',
      },
    }))
    await flushPromises()

    const avivatorCall = [...mockDockviewApi.addPanel.mock.calls]
      .reverse()
      .map((call: any) => call[0])
      .find((call: any) => call.id === 'avivator')
    expect(avivatorCall).toBeDefined()
    expect(avivatorCall).toMatchObject({
      id: 'avivator',
      component: 'avivator',
      tabComponent: 'avivatorTab',
      title: 'Avivator - image.ome.tif',
      params: {
        url: 'http://avivator.gehlenborglab.org/?image_url=http%3A%2F%2Flocalhost%2Fimage.ome.tif',
        imageUrl: 'http://localhost/image.ome.tif',
      },
      position: {
        referencePanel: 'dataTable',
        direction: 'within',
      },
    })
    expect(panels.get('avivator').api.setActive).toHaveBeenCalled()
  })

  it('opens a Dockview tab for sub-workflow sessions', async () => {
    mountApp()
    await flushPromises()
    const sessions = useSubWorkflowSessionsStore()
    const session = await openAcceptedNestedSession(sessions, nestedSnapshotMocks.open, {
      parentCanvasId: 'workflow:parent',
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: { nodes: [], edges: [] },
    })

    window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
      detail: {
        sessionId: session.id,
        parentCanvasPanelId: 'workflow:parent',
      },
    }))
    const nestedPanelId = `sub-workflow:${encodeURIComponent(session.id)}`
    const nestedCanvasId = canvasIdFromPanelId(nestedPanelId)
    useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId: nestedCanvasId,
        sessionId: session.id,
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
      nestedSnapshot: {
        initialSnapshot: sessions.snapshotForSession(session.id),
        onAccepted: snapshot => sessions.acceptSnapshot(session.id, snapshot),
      },
    })
    useUIStore().setCanvasSelectedNodes(nestedCanvasId, ['nested-node'])
    await flushPromises()

    const lastCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ]?.[0]
    expect(lastCall).toMatchObject({
      component: 'subWorkflowEditor',
      title: 'Sub 1',
      params: {
        sessionId: session.id,
        parentCanvasPanelId: 'workflow:parent',
      },
    })
    expect(lastCall.id).toContain('sub-workflow:')
    expect(panels.get(lastCall.id).api.setActive).toHaveBeenCalled()
    expect(useUIStore().activeWorkflowId).toBe('parent')
    expect(useUIStore().activeWorkflowName).toBe('Sub 1')
    expect(useUIStore().selectedNodeIds).toEqual(['nested-node'])
  })

  it('opens and activates a named canvas tab for a root workflow graph', async () => {
    mountApp()
    await flushPromises()
    const openedDraft = {
      draft_version: 1 as const,
      workflow_id: 'analysis',
      base_saved_revision: 'sha256:analysis',
      draft_revision: 4,
      updated_at: '2026-07-16T01:00:00Z',
      updated_by: 'agent' as const,
      dirty_against_saved: false,
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      validation: { valid: true, node_statuses: {}, errors: [] },
    }

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'analysis',
        workflowDisplayName: 'Analysis',
        graph: openedDraft.graph,
        draft: openedDraft,
        missingTools: [],
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('analysis'),
      },
    }))
    const analysisCanvasId = canvasIdFromPanelId('workflow:analysis')
    useGraphSync({
      descriptor: {
        kind: 'root',
        canvasId: analysisCanvasId,
        workflowId: 'analysis',
      },
      getWorkflowId: () => 'analysis',
    })
    await flushPromises()

    const lastCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ]?.[0]
    expect(lastCall).toMatchObject({
      component: 'canvasView',
      title: 'Analysis',
      params: expect.objectContaining({
        workflowName: 'analysis',
        workflowDisplayName: 'Analysis',
        draft: openedDraft,
      }),
    })
    expect(lastCall.id).toBe('workflow:analysis')
    expect(panels.get('workflow:analysis').api.setActive).toHaveBeenCalled()
    expect(useUIStore().activeWorkflowName).toBe('Analysis')
  })

  it('opens the first workflow in the explicit empty canvas group', async () => {
    resolveStartupWorkflowMock.mockResolvedValueOnce(null)
    mountApp()
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'analysis',
        workflowDisplayName: 'Analysis',
        graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
        missingTools: [],
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('analysis'),
      },
    }))
    await flushPromises()

    const lastCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ]?.[0]
    expect(lastCall).toMatchObject({
      id: 'workflow:analysis',
      position: {
        referencePanel: 'canvas-empty',
        direction: 'within',
      },
    })
  })

  it('rejects a root apply event that has no identity generation token', async () => {
    mountApp()
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'unversioned',
        workflowDisplayName: 'Unversioned',
        graph: { nodes: [], edges: [] },
        missingTools: [],
        dirty: false,
      },
    }))
    await flushPromises()

    expect(panels.has('workflow:unversioned')).toBe(false)
  })

  it('does not let a rejected stale open cancel fresh startup resolution', async () => {
    const workflow = useWorkflowStore()
    const drafts = useWorkflowDraftStore()
    const staleGraph = { nodes: [], edges: [] }
    vi.spyOn(workflow, 'loadWorkflow').mockResolvedValueOnce(staleGraph)
    vi.spyOn(drafts, 'loadDraft').mockRejectedValueOnce(new Error('no draft'))
    const stalePresentation = await loadRootWorkflowPresentation('startup')
    await workflow.forgetDeletedWorkflow('startup')
    const startupResolution = deferred<any>()
    resolveStartupWorkflowMock.mockReturnValueOnce(startupResolution.promise)

    mountApp()
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: stalePresentation,
    }))
    startupResolution.resolve({
      workflowName: 'startup',
      workflowDisplayName: 'Fresh startup',
      graph: { nodes: [], edges: [] },
      missingTools: [],
      dirty: false,
      identityGeneration: workflow.workflowIdentityGeneration('startup'),
    })
    await flushPromises()

    expect(panels.has('workflow:startup')).toBe(true)
    expect(panels.get('workflow:startup').title).toBe('Fresh startup')
    expect(panels.has('canvas-empty')).toBe(false)
  })

  it('places B beside A after every root canvas was closed', async () => {
    mountApp()
    await flushPromises()
    mockDockviewApi.removePanel(panels.get('workflow:startup'))
    await flushPromises()

    const graph = { nodes: [], edges: [], published_inputs: [], published_outputs: [] }
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'a',
        workflowDisplayName: 'A',
        graph,
        missingTools: [],
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('a'),
      },
    }))
    await flushPromises()
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'b',
        workflowDisplayName: 'B',
        graph,
        missingTools: [],
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('b'),
      },
    }))
    await flushPromises()

    const bCall = mockDockviewApi.addPanel.mock.calls
      .map((call: any) => call[0])
      .find((options: any) => options.id === 'workflow:b')
    expect(bCall.position).toEqual({
      referencePanel: 'workflow:a',
      direction: 'within',
    })
  })

  it('activating a non-canvas panel keeps the current node selection', async () => {
    mountApp()
    await flushPromises()
    const ui = useUIStore()
    const startupCanvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: {
        kind: 'root',
        canvasId: startupCanvasId,
        workflowId: 'startup',
      },
      getWorkflowId: () => 'startup',
    })
    panels.get('workflow:startup').api.setActive()
    ui.setSelectedNodes(['node_1'])

    panels.get('tools').api.setActive()
    await flushPromises()

    expect(ui.selectedNodeIds).toEqual(['node_1'])
  })

  it('activates graph sync only for canvas panels and retains it for side panels', async () => {
    mountApp()
    await flushPromises()
    const canvasId = canvasIdFromPanelId('workflow:startup')

    panels.get('workflow:startup').api.setActive()
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    await flushPromises()

    expect(graphSyncCanvasSessions.activeCanvasId.value).toBe(canvasId)

    panels.get('tools').api.setActive()
    expect(graphSyncCanvasSessions.activeCanvasId.value).toBe(canvasId)
  })

  it('removing a canvas unregisters only that canvas graph sync session', async () => {
    mountApp()
    await flushPromises()
    const startupCanvasId = canvasIdFromPanelId('workflow:startup')
    const workflowCanvasId = canvasIdFromPanelId('workflow:analysis')
    useGraphSync({
      descriptor: { kind: 'root', canvasId: startupCanvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    useGraphSync({
      descriptor: {
        kind: 'root',
        canvasId: workflowCanvasId,
        workflowId: 'analysis',
      },
      getWorkflowId: () => 'analysis',
    })
    graphSyncCanvasSessions.activate(workflowCanvasId)

    mockDockviewApi.removePanel(panels.get('workflow:startup'))
    await flushPromises()

    expect(graphSyncCanvasSessions.get(startupCanvasId)).toBeNull()
    expect(graphSyncCanvasSessions.get(workflowCanvasId)).not.toBeNull()
    expect(graphSyncCanvasSessions.activeCanvasId.value).toBe(workflowCanvasId)
  })

  it('updates the canonical startup tab title from its workflow context', async () => {
    mountApp()
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bioimageflow:canvas-context-updated', {
      detail: {
        panelId: 'workflow:startup',
        workflowName: 'startup',
        workflowDisplayName: 'Startup renamed',
      },
    }))
    await flushPromises()

    expect(panels.get('workflow:startup').api.setTitle).toHaveBeenCalledWith('Startup renamed')
    expect(panels.get('workflow:startup').title).toBe('Startup renamed')
  })

  it('reactivating the canonical startup canvas restores its workflow context', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    workflow.workflows = [
      { name: 'startup', display_name: 'Startup' },
      { name: 'other', display_name: 'Other' },
    ] as any
    workflow.activateWorkflow('other')

    window.dispatchEvent(new CustomEvent('bioimageflow:canvas-context-updated', {
      detail: {
        panelId: 'workflow:startup',
        workflowName: 'startup',
        workflowDisplayName: 'Startup',
      },
    }))
    const startupCanvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: {
        kind: 'root',
        canvasId: startupCanvasId,
        workflowId: 'startup',
      },
      getWorkflowId: () => 'startup',
    })
    panels.get('workflow:startup').api.setActive()
    await flushPromises()

    expect(workflow.currentName).toBe('startup')
    expect(useUIStore().activeWorkflowName).toBe('Startup')
  })

  it('switches active presentation context and retains it on side panels', async () => {
    mountApp()
    await flushPromises()
    const startupCanvasId = canvasIdFromPanelId('workflow:startup')
    const workflowCanvasId = canvasIdFromPanelId('workflow:analysis')
    useGraphSync({
      descriptor: {
        kind: 'root',
        canvasId: startupCanvasId,
        workflowId: 'startup',
      },
      getWorkflowId: () => 'startup',
    })
    window.dispatchEvent(new CustomEvent('bioimageflow:canvas-context-updated', {
      detail: {
        panelId: 'workflow:startup',
        workflowName: 'startup',
        workflowDisplayName: 'Startup',
      },
    }))
    const ui = useUIStore()
    ui.setCanvasSelectedNodes(startupCanvasId, ['shared'])
    ui.setCanvasGraphNodes(startupCanvasId, [{ id: 'shared', data: { name: 'Startup node' } }])
    ui.markCanvasDirty(startupCanvasId)

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'analysis',
        workflowDisplayName: 'Analysis',
        graph: { nodes: [], edges: [] },
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('analysis'),
      },
    }))
    useGraphSync({
      descriptor: {
        kind: 'root',
        canvasId: workflowCanvasId,
        workflowId: 'analysis',
      },
      getWorkflowId: () => 'analysis',
    })
    ui.setCanvasSelectedNodes(workflowCanvasId, ['shared'])
    ui.setCanvasGraphNodes(workflowCanvasId, [{ id: 'shared', data: { name: 'Analysis node' } }])
    ui.markCanvasClean(workflowCanvasId)
    await flushPromises()

    expect(ui.activeWorkflowId).toBe('analysis')
    expect(ui.graphNodes[0]?.data.name).toBe('Analysis node')
    expect(ui.hasUnsavedChanges).toBe(false)
    expect(document.title).toBe('BioImageFlow \u2014 Analysis')

    panels.get('workflow:startup').api.setActive()
    await flushPromises()
    expect(ui.activeWorkflowId).toBe('startup')
    expect(ui.selectedNodeIds).toEqual(['shared'])
    expect(ui.graphNodes[0]?.data.name).toBe('Startup node')
    expect(ui.hasUnsavedChanges).toBe(true)
    expect(document.title).toBe('BioImageFlow \u2014 Startup *')

    panels.get('tools').api.setActive()
    expect(ui.activeWorkflowId).toBe('startup')
    expect(ui.selectedNodeIds).toEqual(['shared'])
  })

  it('reopening the startup workflow activates its canonical tab without replacing it', async () => {
    mountApp()
    await flushPromises()
    const detail = {
      workflowName: 'startup',
      workflowDisplayName: 'Startup',
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      missingTools: [],
      dirty: false,
      identityGeneration: useWorkflowStore().workflowIdentityGeneration('startup'),
    }

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail }))
    await flushPromises()
    const addCount = mockDockviewApi.addPanel.mock.calls.length
    const removeCount = mockDockviewApi.removePanel.mock.calls.length
    const activeCount = panels.get('workflow:startup').api.setActive.mock.calls.length

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail }))
    await flushPromises()

    expect(mockDockviewApi.addPanel.mock.calls.length).toBe(addCount)
    expect(mockDockviewApi.removePanel.mock.calls.length).toBe(removeCount)
    expect(panels.get('workflow:startup').api.setActive.mock.calls.length)
      .toBeGreaterThan(activeCount)
  })

  it('closes a clean canonical root immediately through the shared close request', async () => {
    mountApp()
    await flushPromises()
    const panel = panels.get('workflow:startup')

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: 'workflow:startup' },
    }))
    await flushPromises()

    expect(mockDockviewApi.removePanel).toHaveBeenCalledWith(panel)
  })

  it('keeps a dirty root open when its close decision is cancelled', async () => {
    mountApp()
    await flushPromises()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useUIStore().markCanvasDirty(canvasId)
    const panel = panels.get('workflow:startup')

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: 'workflow:startup' },
    }))
    await flushPromises()

    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(panel)
    await clickLatestTestId('root-workflow-close-cancel')
    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(panel)
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
  })

  it('binds delayed Save-and-close to the root that opened the dialog', async () => {
    mountApp()
    await flushPromises()
    const graph = { nodes: [], edges: [], published_inputs: [], published_outputs: [] }
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'other',
        workflowDisplayName: 'Other',
        graph,
        missingTools: [],
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('other'),
      },
    }))
    await flushPromises()
    const startupCanvasId = canvasIdFromPanelId('workflow:startup')
    useUIStore().markCanvasDirty(startupCanvasId)
    const startupPanel = panels.get('workflow:startup')
    const otherPanel = panels.get('workflow:other')

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: 'workflow:startup' },
    }))
    otherPanel.api.setActive()
    await clickLatestTestId('root-workflow-close-save')

    expect(saveRootWorkflowTargetMock).toHaveBeenCalledWith({
      canvasId: startupCanvasId,
      workflowName: 'startup',
    })
    expect(mockDockviewApi.removePanel).toHaveBeenCalledWith(startupPanel)
    expect(panels.get('workflow:other')).toBe(otherPanel)
  })

  it('defers a generation replacement until a pending Save-and-close releases its gate', async () => {
    const saving = deferred<any>()
    saveRootWorkflowTargetMock.mockReturnValueOnce(saving.promise)
    const workflow = useWorkflowStore()
    const drafts = useWorkflowDraftStore()
    workflow.observeWorkflowServerIdentityGeneration('startup', 2)
    workflow.workflows = [{
      id: 'startup',
      name: 'startup',
      display_name: 'Fresh startup',
      identity_generation: 2,
    }] as any
    const resetPresentation = vi.spyOn(
      workflow,
      'resetWorkflowPresentationGeneration',
    ).mockResolvedValueOnce()
    vi.spyOn(workflow, 'loadWorkflow').mockResolvedValueOnce({ nodes: [], edges: [] })
    vi.spyOn(drafts, 'loadDraft').mockRejectedValueOnce(new Error('no retained draft'))
    mountApp()
    await flushPromises()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useUIStore().markCanvasDirty(canvasId)
    const panel = panels.get('workflow:startup')

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: 'workflow:startup' },
    }))
    void clickLatestTestId('root-workflow-close-save')
    await flushPromises()
    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-identities-refreshed', {
      detail: {
        workflows: [{ workflowName: 'startup', identityGeneration: 2 }],
      },
    }))
    await flushPromises()

    expect(panels.get('workflow:startup')).toBe(panel)
    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(panel)
    expect(resetPresentation).not.toHaveBeenCalled()

    saving.resolve({ status: 'newer-edit' })
    await vi.waitFor(() => {
      expect(resetPresentation).toHaveBeenCalledOnce()
      expect(panels.get('workflow:startup')).not.toBe(panel)
    })
    expect(mockDockviewApi.removePanel).toHaveBeenCalledWith(panel)
  })

  it('keeps a root open when Save detects a newer edit', async () => {
    saveRootWorkflowTargetMock.mockResolvedValueOnce({ status: 'newer-edit' })
    mountApp()
    await flushPromises()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useUIStore().markCanvasDirty(canvasId)
    const panel = panels.get('workflow:startup')

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: 'workflow:startup' },
    }))
    await clickLatestTestId('root-workflow-close-save')

    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(panel)
    expect(document.body.textContent).toContain('changed while it was being saved')
  })

  it('keeps a dirty root open and reports an ordinary Save failure', async () => {
    saveRootWorkflowTargetMock.mockRejectedValueOnce(new Error('disk is unavailable'))
    mountApp()
    await flushPromises()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useUIStore().markCanvasDirty(canvasId)
    const panel = panels.get('workflow:startup')

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: 'workflow:startup' },
    }))
    await clickLatestTestId('root-workflow-close-save')

    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(panel)
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
    expect(document.body.textContent).toContain('disk is unavailable')
  })

  it('restores the accepted saved draft before discarding and closing', async () => {
    mountApp()
    await flushPromises()
    const panelId = 'workflow:startup'
    const canvasId = canvasIdFromPanelId(panelId)
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    const savedDraft = {
      draft_version: 1 as const,
      workflow_id: 'startup',
      base_saved_revision: 'sha256:saved',
      draft_revision: 4,
      updated_at: '2026-07-16T12:00:00Z',
      updated_by: 'frontend' as const,
      dirty_against_saved: false,
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      validation: { valid: true, node_statuses: {}, errors: [] },
    }
    persistence.initializeFromDraft({ ...savedDraft, draft_revision: 3 })
    const discard = vi.spyOn(persistence, 'discardToSaved').mockResolvedValue(savedDraft)
    useUIStore().markCanvasDirty(canvasId)
    const panel = panels.get(panelId)

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: panelId },
    }))
    await clickLatestTestId('root-workflow-close-discard')

    expect(discard).toHaveBeenCalledOnce()
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(false)
    expect(mockDockviewApi.removePanel).toHaveBeenCalledWith(panel)
  })

  it('keeps a dirty root open when restoring its saved draft fails', async () => {
    mountApp()
    await flushPromises()
    const panelId = 'workflow:startup'
    const canvasId = canvasIdFromPanelId(panelId)
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'discardToSaved').mockRejectedValueOnce(
      new Error('draft revision conflict'),
    )
    useUIStore().markCanvasDirty(canvasId)
    const panel = panels.get(panelId)

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: panelId },
    }))
    await clickLatestTestId('root-workflow-close-discard')

    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(panel)
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
    expect(document.body.textContent).toContain('draft revision conflict')
  })

  it('restores the accepted saved graph but keeps the tab open when recovery cleanup fails', async () => {
    mountApp()
    await flushPromises()
    const panelId = 'workflow:startup'
    const canvasId = canvasIdFromPanelId(panelId)
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    const savedDraft = {
      draft_version: 1 as const,
      workflow_id: 'startup',
      base_saved_revision: 'sha256:saved',
      draft_revision: 5,
      updated_at: '2026-07-16T12:00:00Z',
      updated_by: 'frontend' as const,
      dirty_against_saved: false,
      graph: { nodes: [{ id: 'saved' }], edges: [] },
      validation: { valid: true, node_statuses: {}, errors: [] },
    }
    vi.spyOn(persistence, 'discardToSaved').mockRejectedValueOnce(
      new CanvasDiscardRecoveryCleanupError(
        savedDraft as any,
        new Error('IndexedDB clear failed'),
      ),
    )
    useUIStore().markCanvasDirty(canvasId)
    const restored = vi.fn()
    window.addEventListener('bioimageflow:restore-saved-canvas', restored)
    const panel = panels.get(panelId)

    window.dispatchEvent(new CustomEvent('bioimageflow:request-close-canvas', {
      detail: { canvasId: panelId },
    }))
    await clickLatestTestId('root-workflow-close-discard')

    expect(restored).toHaveBeenCalledOnce()
    expect((restored.mock.calls[0]![0] as CustomEvent).detail.draft).toEqual(savedDraft)
    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(panel)
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
    expect(document.body.textContent).toContain('local recovery snapshot could not be cleared')
    window.removeEventListener('bioimageflow:restore-saved-canvas', restored)
  })

  it('closes the originally confirmed workflow after delayed deletion and activates an existing root', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    workflow.workflows = [
      { id: 'startup', name: 'startup', display_name: 'Startup' },
      { id: 'other', name: 'other', display_name: 'Other' },
    ] as any
    const graph = { nodes: [], edges: [], published_inputs: [], published_outputs: [] }
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'other',
        workflowDisplayName: 'Other',
        graph,
        missingTools: [],
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('other'),
      },
    }))
    await flushPromises()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    const startupPanel = panels.get('workflow:startup')
    const deletion = deferred<void>()
    vi.spyOn(workflow, 'deleteWorkflow').mockReturnValueOnce(deletion.promise)
    const request = deferred<void>()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...capturedWorkflowDeletionTarget('startup', canvasId),
        resolve: request.resolve,
        reject: request.reject,
      },
    }))
    panels.get('workflow:other').api.setActive()
    await flushPromises()
    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-identities-refreshed', {
      detail: {
        workflows: [
          { workflowName: 'startup', identityGeneration: 3 },
          { workflowName: 'other', identityGeneration: null },
        ],
      },
    }))
    await flushPromises()
    expect(panels.get('workflow:startup')).toBe(startupPanel)
    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(startupPanel)

    deletion.resolve()
    await request.promise
    await flushPromises()

    expect(panels.has('workflow:startup')).toBe(false)
    expect(panels.has('workflow:other')).toBe(true)
    expect(panels.get('workflow:other').api.setActive).toHaveBeenCalled()
    expect(panels.has('workflow:workflow')).toBe(false)
  })

  it('never activates or reopens an older loaded generation across deletion', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const drafts = useWorkflowDraftStore()
    const staleGraph = { nodes: [], edges: [] }
    vi.spyOn(workflow, 'loadWorkflow').mockResolvedValueOnce(staleGraph)
    vi.spyOn(drafts, 'loadDraft').mockRejectedValueOnce(new Error('no draft'))
    const stalePresentation = await loadRootWorkflowPresentation('startup')
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    const deletion = deferred<void>()
    vi.spyOn(workflow, 'deleteWorkflow').mockReturnValueOnce(deletion.promise)
    const request = deferred<void>()
    const startupPanel = panels.get('workflow:startup')
    startupPanel.api.setActive.mockClear()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...capturedWorkflowDeletionTarget('startup', canvasId),
        resolve: request.resolve,
        reject: request.reject,
      },
    }))
    await flushPromises()
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: stalePresentation,
    }))
    await flushPromises()

    expect(startupPanel.api.setActive).not.toHaveBeenCalled()

    deletion.resolve()
    await request.promise
    await flushPromises()
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: stalePresentation,
    }))
    await flushPromises()

    expect(panels.has('workflow:startup')).toBe(false)
    expect(panels.has('workflow:workflow')).toBe(false)
    expect(panels.has('canvas-empty')).toBe(true)
  })

  it('gates a root and its nested canvases until workflow deletion completes', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const sessions = useSubWorkflowSessionsStore()
    const lifecycle = useCanvasLifecycleStore()
    const rootCanvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId: rootCanvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(rootCanvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    const session = await openAcceptedNestedSession(sessions, nestedSnapshotMocks.open, {
      parentCanvasId: 'workflow:startup',
      parentWorkflowName: 'startup',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
    })
    window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
      detail: {
        sessionId: session.id,
        parentCanvasPanelId: 'workflow:startup',
      },
    }))
    await flushPromises()
    const nestedPanelId = `sub-workflow:${encodeURIComponent(session.id)}`
    const nestedCanvasId = canvasIdFromPanelId(nestedPanelId)
    const deletion = deferred<void>()
    vi.spyOn(workflow, 'deleteWorkflow').mockReturnValueOnce(deletion.promise)
    const request = deferred<void>()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...capturedWorkflowDeletionTarget('startup', rootCanvasId),
        resolve: request.resolve,
        reject: request.reject,
      },
    }))
    await flushPromises()

    expect(lifecycle.operationFor(rootCanvasId)).toBe('deleting')
    expect(lifecycle.operationFor(nestedCanvasId)).toBe('deleting')
    expect(panels.has('workflow:startup')).toBe(true)
    expect(panels.has(nestedPanelId)).toBe(true)

    deletion.resolve()
    await request.promise
    await flushPromises()

    expect(panels.has('workflow:startup')).toBe(false)
    expect(panels.has(nestedPanelId)).toBe(false)
    expect(forgetRetainedNestedSnapshot(session.id)).toBe(false)
    expect(lifecycle.operationFor(rootCanvasId)).toBeNull()
    expect(lifecycle.operationFor(nestedCanvasId)).toBeNull()
  })

  it('keeps the exact target mounted when backend deletion fails', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    vi.spyOn(workflow, 'deleteWorkflow').mockRejectedValueOnce(new Error('delete failed'))
    const request = deferred<void>()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...capturedWorkflowDeletionTarget('startup', canvasId),
        resolve: request.resolve,
        reject: request.reject,
      },
    }))

    await expect(request.promise).rejects.toThrow('delete failed')
    expect(panels.has('workflow:startup')).toBe(true)
  })

  it('retries the same confirmed deletion after backend DELETE fails', async () => {
    const wrapper = mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    workflow.observeWorkflowServerIdentityGeneration('startup', 7)
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    canvasSessionRegistry.activate(canvasId)
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    const deleteRequest = vi.spyOn(api, 'delete')
      .mockRejectedValueOnce(new Error('backend unavailable'))
      .mockResolvedValueOnce({
        data: { deleted: true, identity_generation: 8 },
      } as any)
    const localIdentityGeneration = workflow.workflowIdentityGeneration('startup')
    const sessionRegistrationToken = canvasSessionRegistry.get(canvasId)?.registrationToken
    const menuBar = wrapper.findComponent(MenuBar)
    const vm = menuBar.vm as any
    const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')

    workflowMenu.items.find((item: any) => item.label === 'Delete').command()
    expect(vm.deleteCanvasTarget).toMatchObject({
      workflowName: 'startup',
      canvasId,
      localIdentityGeneration,
      serverIdentityGeneration: 7,
      sessionRegistrationToken,
    })

    await clickLatestTestId('delete-workflow-confirm')

    expect(deleteRequest).toHaveBeenCalledTimes(1)
    expect(deleteRequest).toHaveBeenNthCalledWith(1, '/api/v1/workflows/startup', {
      params: { expected_identity_generation: 7 },
    })
    expect(workflow.workflowIdentityGeneration('startup')).toBe(localIdentityGeneration)
    expect(canvasSessionRegistry.get(canvasId)?.registrationToken)
      .toBe(sessionRegistrationToken)
    expect(vm.deleteDialogVisible).toBe(true)
    expect(vm.deleteCanvasTarget).toMatchObject({
      workflowName: 'startup',
      canvasId,
      localIdentityGeneration,
      serverIdentityGeneration: 7,
      sessionRegistrationToken,
    })

    await clickLatestTestId('delete-workflow-confirm')
    await vi.waitFor(() => {
      expect(vm.deleteDialogVisible).toBe(false)
    })

    expect(deleteRequest).toHaveBeenCalledTimes(2)
    expect(deleteRequest).toHaveBeenNthCalledWith(2, '/api/v1/workflows/startup', {
      params: { expected_identity_generation: 7 },
    })
    expect(vm.deleteCanvasTarget).toBeNull()
    expect(panels.has('workflow:startup')).toBe(false)
    expect(canvasSessionRegistry.get(canvasId)).toBeNull()
    expect(workflow.workflows).toEqual([])
    deleteRequest.mockRestore()
  })

  it('rejects a stale delete request after the same canvas id remounts', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const staleTarget = capturedWorkflowDeletionTarget('startup', canvasId)
    canvasSessionRegistry.unregister(canvasId)
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const freshToken = canvasSessionRegistry.get(canvasId)?.registrationToken
    const deleteWorkflow = vi.spyOn(workflow, 'deleteWorkflow')
    const request = deferred<void>()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...staleTarget,
        resolve: request.resolve,
        reject: request.reject,
      },
    }))

    await expect(request.promise).rejects.toBeInstanceOf(
      WorkflowDeletionTargetChangedError,
    )
    expect(freshToken).not.toBe(staleTarget.sessionRegistrationToken)
    expect(canvasSessionRegistry.get(canvasId)?.registrationToken).toBe(freshToken)
    expect(deleteWorkflow).not.toHaveBeenCalled()
    expect(panels.has('workflow:startup')).toBe(true)
  })

  it('maps the backend generation precondition conflict to a stale target', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    vi.spyOn(workflow, 'deleteWorkflow').mockRejectedValueOnce({
      response: {
        status: 409,
        data: { error: 'workflow_identity_generation_conflict' },
      },
    })
    const request = deferred<void>()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...capturedWorkflowDeletionTarget('startup', canvasId),
        resolve: request.resolve,
        reject: request.reject,
      },
    }))

    await expect(request.promise).rejects.toBeInstanceOf(
      WorkflowDeletionTargetChangedError,
    )
    expect(panels.has('workflow:startup')).toBe(true)
  })

  it('reports cleanup failure as committed after deletion disposed the target', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    vi.spyOn(workflow, 'deleteWorkflow').mockImplementationOnce(async (
      _workflowName,
      options,
    ) => {
      await options?.beforeRecoveryCleanup?.()
      throw new Error('IndexedDB unavailable')
    })
    const request = deferred<void>()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...capturedWorkflowDeletionTarget('startup', canvasId),
        resolve: request.resolve,
        reject: request.reject,
      },
    }))

    await expect(request.promise).rejects.toBeInstanceOf(
      WorkflowDeletionCommittedCleanupError,
    )
    expect(panels.has('workflow:startup')).toBe(false)
  })

  it('shows a non-persistent empty state after deleting the final workflow', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useGraphSync({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
    })
    const persistence = getRootCanvasPersistenceResource(canvasId)!
    vi.spyOn(persistence, 'ensureFreshForCriticalOperation').mockResolvedValue(true)
    vi.spyOn(workflow, 'deleteWorkflow').mockResolvedValueOnce()
    const request = deferred<void>()

    window.dispatchEvent(new CustomEvent('bioimageflow:request-delete-workflow', {
      detail: {
        ...capturedWorkflowDeletionTarget('startup', canvasId),
        resolve: request.resolve,
        reject: request.reject,
      },
    }))
    await request.promise
    await flushPromises()

    expect(panels.has('workflow:startup')).toBe(false)
    expect(panels.has('canvas-empty')).toBe(true)
    expect(panels.has('workflow:workflow')).toBe(false)
    expect(mockDockviewApi.addPanel.mock.calls.some(
      (call: any) => call[0].id === 'workflow:workflow',
    )).toBe(false)
  })

  it('converges a remote workflow deletion through the same exact-tab fallback', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    workflow.workflows = [
      { id: 'startup', name: 'startup', display_name: 'Startup' },
      { id: 'other', name: 'other', display_name: 'Other' },
    ] as any
    const graph = { nodes: [], edges: [], published_inputs: [], published_outputs: [] }
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'other',
        workflowDisplayName: 'Other',
        graph,
        missingTools: [],
        dirty: false,
        identityGeneration: useWorkflowStore().workflowIdentityGeneration('other'),
      },
    }))
    await flushPromises()
    panels.get('workflow:other').api.setActive.mockClear()

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-removed', {
      detail: { workflowName: 'startup' },
    }))
    await vi.waitFor(() => {
      expect(panels.get('workflow:other').api.setActive).toHaveBeenCalledOnce()
    })

    expect(panels.has('workflow:startup')).toBe(false)
    expect(panels.has('workflow:other')).toBe(true)
  })

  it('disposes and fences a delayed recovery write before remote deletion clears it', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    const canvasId = canvasIdFromPanelId('workflow:startup')
    const writeGate = deferred<void>()
    const writeStarted = deferred<void>()
    const initialDraft = {
      draft_version: 1 as const,
      workflow_id: 'startup',
      base_saved_revision: 'sha256:saved',
      draft_revision: 1,
      updated_at: '2026-07-16T12:00:00Z',
      updated_by: 'frontend' as const,
      dirty_against_saved: false,
      graph: { nodes: [], edges: [] },
      validation: { valid: true, node_statuses: {}, errors: [] },
    }
    const persistence = useCanvasPersistence({
      descriptor: { kind: 'root', canvasId, workflowId: 'startup' },
      getWorkflowId: () => 'startup',
      transports: {
        fetchDraft: vi.fn(async () => initialDraft),
        putDraft: vi.fn(async (_workflowId, body) => ({
          ...initialDraft,
          draft_revision: body.expected_revision + 1,
          dirty_against_saved: true,
          graph: body.graph,
        })),
        writeRecovery: vi.fn(async (entry) => {
          writeStarted.resolve()
          await writeGate.promise
          await writeAutoSaveEntry(entry)
        }),
      },
    })
    persistence.initializeFromDraft(initialDraft)
    persistence.queueGraph({ nodes: [{ id: 'late' }] as any, edges: [] })
    const flushing = persistence.flush()
    const flushingOutcome = flushing.then(
      () => undefined,
      () => undefined,
    )
    await writeStarted.promise

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-removed', {
      detail: { workflowName: 'startup' },
    }))
    await flushPromises()

    expect(panels.has('workflow:startup')).toBe(false)
    expect(workflow.isWorkflowDeletionInFlight('startup')).toBe(true)
    writeGate.resolve()
    await flushingOutcome
    await vi.waitFor(() => {
      expect(workflow.isWorkflowDeletionInFlight('startup')).toBe(false)
    })

    await expect(useAutoSave().loadAutoSave('startup')).resolves.toBeNull()
  })

  it('does not steal canvas focus when a remotely deleted workflow was not mounted', async () => {
    mountApp()
    await flushPromises()
    const startupPanel = panels.get('workflow:startup')
    startupPanel.api.setActive.mockClear()

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-removed', {
      detail: { workflowName: 'not-mounted' },
    }))
    await flushPromises()

    expect(panels.has('workflow:startup')).toBe(true)
    expect(startupPanel.api.setActive).not.toHaveBeenCalled()
  })

  it('ignores a delayed deletion event from before same-id recreation', async () => {
    const workflow = useWorkflowStore()
    workflow.observeWorkflowServerIdentityGeneration('startup', 12)
    mountApp()
    await flushPromises()
    const startupPanel = panels.get('workflow:startup')

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-removed', {
      detail: {
        workflowName: 'startup',
        identityGeneration: 11,
      },
    }))
    await flushPromises()

    expect(panels.get('workflow:startup')).toBe(startupPanel)
    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(startupPanel)
    expect(workflow.workflows.map(item => item.id)).toContain('startup')
  })

  it('replaces a mounted old generation with the refreshed same-id workflow exactly once', async () => {
    const workflow = useWorkflowStore()
    const drafts = useWorkflowDraftStore()
    workflow.observeWorkflowServerIdentityGeneration('startup', 10)
    resolveStartupWorkflowMock.mockResolvedValueOnce({
      workflowName: 'startup',
      workflowDisplayName: 'Old startup',
      graph: { nodes: [{ id: 'old' }], edges: [] },
      missingTools: [],
      dirty: false,
      identityGeneration: workflow.workflowIdentityGeneration('startup'),
      serverIdentityGeneration: 10,
    })
    mountApp()
    await flushPromises()
    const oldPanel = panels.get('workflow:startup')
    const sessions = useSubWorkflowSessionsStore()
    const nestedSession = await openAcceptedNestedSession(
      sessions,
      nestedSnapshotMocks.open,
      {
        parentCanvasId: 'workflow:startup',
        parentWorkflowName: 'startup',
        parentNodeId: 'sub_1',
        graph: { nodes: [], edges: [] },
      },
    )
    window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
      detail: {
        sessionId: nestedSession.id,
        parentCanvasPanelId: 'workflow:startup',
      },
    }))
    await flushPromises()
    const nestedPanelId = `sub-workflow:${encodeURIComponent(nestedSession.id)}`
    const nestedSync = useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId: canvasIdFromPanelId(nestedPanelId),
        sessionId: nestedSession.id,
        parentCanvasId: canvasIdFromPanelId('workflow:startup'),
      },
      getWorkflowId: () => 'startup',
      nestedSnapshot: {
        initialSnapshot: sessions.snapshotForSession(nestedSession.id),
      },
    })
    vi.useFakeTimers()
    nestedSync.syncGraphState({ nodes: [{ id: 'queued-old-generation' }] as any, edges: [] })
    nestedSnapshotMocks.put.mockClear()
    workflow.workflows = [{
      id: 'startup',
      name: 'startup',
      display_name: 'Fresh startup',
      identity_generation: 12,
    }] as any
    workflow.observeWorkflowServerIdentityGeneration('startup', 12)
    vi.spyOn(workflow, 'loadWorkflow').mockResolvedValueOnce({
      nodes: [{ id: 'fresh' }],
      edges: [],
    } as any)
    vi.spyOn(drafts, 'loadDraft').mockRejectedValueOnce(new Error('no retained draft'))

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-identities-refreshed', {
      detail: {
        workflows: [{ workflowName: 'startup', identityGeneration: 12 }],
      },
    }))
    await vi.waitFor(() => {
      expect(panels.get('workflow:startup')).not.toBe(oldPanel)
      expect(panels.get('workflow:startup')?.title).toBe('Fresh startup')
    })

    const freshPanel = panels.get('workflow:startup')
    expect(freshPanel.params.serverIdentityGeneration).toBe(12)
    expect(mockDockviewApi.removePanel).toHaveBeenCalledWith(oldPanel)
    expect(panels.has(nestedPanelId)).toBe(false)
    expect(forgetRetainedNestedSnapshot(nestedSession.id)).toBe(false)
    await vi.advanceTimersByTimeAsync(500)
    expect(nestedSnapshotMocks.put).not.toHaveBeenCalled()
    vi.useRealTimers()
    const removeCount = mockDockviewApi.removePanel.mock.calls.length

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-removed', {
      detail: { workflowName: 'startup', identityGeneration: 11 },
    }))
    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-identities-refreshed', {
      detail: {
        workflows: [{ workflowName: 'startup', identityGeneration: 12 }],
      },
    }))
    await flushPromises()

    expect(panels.get('workflow:startup')).toBe(freshPanel)
    expect(mockDockviewApi.removePanel).toHaveBeenCalledTimes(removeCount)
  })

  it('does not reopen a fresh same-id workflow when old recovery cleanup fails', async () => {
    const workflow = useWorkflowStore()
    workflow.observeWorkflowServerIdentityGeneration('startup', 10)
    resolveStartupWorkflowMock.mockResolvedValueOnce({
      workflowName: 'startup',
      workflowDisplayName: 'Old startup',
      graph: { nodes: [], edges: [] },
      missingTools: [],
      dirty: false,
      identityGeneration: workflow.workflowIdentityGeneration('startup'),
      serverIdentityGeneration: 10,
    })
    mountApp()
    await flushPromises()
    const oldPanel = panels.get('workflow:startup')
    workflow.workflows = [{
      id: 'startup',
      name: 'startup',
      display_name: 'Fresh startup',
      identity_generation: 12,
    }] as any
    workflow.observeWorkflowServerIdentityGeneration('startup', 12)
    vi.spyOn(workflow, 'resetWorkflowPresentationGeneration').mockRejectedValueOnce(
      new Error('old recovery cleanup failed'),
    )
    const loadFresh = vi.spyOn(workflow, 'loadWorkflow')

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-identities-refreshed', {
      detail: {
        workflows: [{ workflowName: 'startup', identityGeneration: 12 }],
      },
    }))
    await vi.waitFor(() => expect(panels.has('canvas-empty')).toBe(true))

    expect(mockDockviewApi.removePanel).toHaveBeenCalledWith(oldPanel)
    expect(panels.has('workflow:startup')).toBe(false)
    expect(loadFresh).not.toHaveBeenCalled()
  })

  it('preserves a dirty mounted identity when reconnect reports the same durable generation', async () => {
    const workflow = useWorkflowStore()
    workflow.observeWorkflowServerIdentityGeneration('startup', 0)
    resolveStartupWorkflowMock.mockResolvedValueOnce({
      workflowName: 'startup',
      workflowDisplayName: 'Before restart',
      graph: { nodes: [], edges: [] },
      missingTools: [],
      dirty: false,
      identityGeneration: workflow.workflowIdentityGeneration('startup'),
      serverIdentityGeneration: 0,
    })
    mountApp()
    await flushPromises()
    const oldPanel = panels.get('workflow:startup')
    const canvasId = canvasIdFromPanelId('workflow:startup')
    useUIStore().markCanvasDirty(canvasId)

    workflow.workflows = [{
      id: 'startup',
      name: 'startup',
      display_name: 'After restart',
      identity_generation: 0,
    }] as any

    window.dispatchEvent(new CustomEvent('bioimageflow:workflow-identities-refreshed', {
      detail: {
        workflows: [{
          workflowName: 'startup',
          identityGeneration: 0,
        }],
      },
    }))
    await flushPromises()

    expect(panels.get('workflow:startup')).toBe(oldPanel)
    expect(mockDockviewApi.removePanel).not.toHaveBeenCalledWith(oldPanel)
    expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(true)
  })

  it('keeps a dirty sub-workflow session open when direct tab close is cancelled', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mountApp()
    await flushPromises()
    const sessions = useSubWorkflowSessionsStore()
    const session = await openAcceptedNestedSession(sessions, nestedSnapshotMocks.open, {
      parentCanvasId: 'workflow:parent',
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: { nodes: [], edges: [] },
    })
    sessions.updateDraft(session.id, {
      nodes: [{
        id: 'inner',
        name: 'inner',
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
    window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
      detail: {
        sessionId: session.id,
        parentCanvasPanelId: 'workflow:parent',
      },
    }))
    await flushPromises()
    const panel = panels.get(
      mockDockviewApi.addPanel.mock.calls[
        mockDockviewApi.addPanel.mock.calls.length - 1
      ]?.[0].id,
    )

    emitDockviewPanelRemoved(panel)
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(sessions.sessionById(session.id)).toBeDefined()
    const reopenedCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ]?.[0]
    expect(reopenedCall.params).toEqual(expect.objectContaining({
      sessionId: session.id,
    }))
    confirmSpy.mockRestore()
  })

  it('deletes a confirmed discarded nested snapshot before dropping the session', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mountApp()
    await flushPromises()
    const sessions = useSubWorkflowSessionsStore()
    const session = await openAcceptedNestedSession(sessions, nestedSnapshotMocks.open, {
      parentCanvasId: 'workflow:startup',
      parentWorkflowName: null,
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
    })
    sessions.updateDraft(session.id, {
      nodes: [],
      edges: [],
      published_inputs: [],
      published_outputs: [{
        name: 'result',
        internal_node_id: 'inner',
        internal_output: 'result',
        schema: { type: 'Path' },
      }],
    })
    const deleteSession = vi.spyOn(sessions, 'deleteDurableSession').mockResolvedValue()
    window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
      detail: {
        sessionId: session.id,
        parentCanvasPanelId: 'workflow:startup',
      },
    }))
    await flushPromises()
    const panel = panels.get(`sub-workflow:${encodeURIComponent(session.id)}`)

    emitDockviewPanelRemoved(panel)
    await flushPromises()

    expect(deleteSession).toHaveBeenCalledWith(session.id)
    expect(sessions.sessionById(session.id)).toBeUndefined()
  })

  it('reopens a nested session when durable deletion fails', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mountApp()
    await flushPromises()
    const sessions = useSubWorkflowSessionsStore()
    const session = await openAcceptedNestedSession(sessions, nestedSnapshotMocks.open, {
      parentCanvasId: 'workflow:startup',
      parentWorkflowName: null,
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
    })
    sessions.updateDraft(session.id, {
      nodes: [{
        id: 'inner',
        name: 'inner',
        tool_name: 'tool',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
      published_inputs: [],
      published_outputs: [],
    })
    vi.spyOn(sessions, 'deleteDurableSession').mockRejectedValue(new Error('delete failed'))
    window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
      detail: {
        sessionId: session.id,
        parentCanvasPanelId: 'workflow:startup',
      },
    }))
    await flushPromises()
    const panel = panels.get(`sub-workflow:${encodeURIComponent(session.id)}`)
    const callsBeforeClose = mockDockviewApi.addPanel.mock.calls.length

    emitDockviewPanelRemoved(panel)
    await flushPromises()

    expect(sessions.sessionById(session.id)).toBeDefined()
    expect(mockDockviewApi.addPanel.mock.calls.length).toBeGreaterThan(callsBeforeClose)
    const lastCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ]
    expect(lastCall?.[0].params).toEqual(
      expect.objectContaining({ sessionId: session.id }),
    )
    expect(warning).toHaveBeenCalledWith(
      '[nested-snapshot] failed to discard snapshot:',
      expect.objectContaining({ message: 'delete failed' }),
    )
  })
})
