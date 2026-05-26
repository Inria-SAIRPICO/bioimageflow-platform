import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import Aura from '@primevue/themes/aura'
import App from '@/App.vue'
import MenuBar from '@/components/layout/MenuBar.vue'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useSubWorkflowSessionsStore } from '@/stores/subWorkflowSessions'
import { useWorkflowStore } from '@/stores/workflow'

const { connectMock, disconnectMock } = vi.hoisted(() => ({
  connectMock: vi.fn(),
  disconnectMock: vi.fn(),
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

  return mount(App, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }], ConfirmationService],
      stubs: {
        ToolsPanel: { template: '<div data-testid="panel-tools">Tools stub</div>' },
        WorkflowsPanel: { template: '<div data-testid="panel-workflows">Workflows stub</div>' },
        CanvasView: { template: '<div data-testid="panel-canvas">Canvas stub</div>' },
      },
    },
  })
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
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(6)

    const panelIds = mockDockviewApi.addPanel.mock.calls.map((call: any) => call[0].id)
    expect(panelIds).toContain('tools')
    expect(panelIds).toContain('workflows')
    expect(panelIds).toContain('canvas')
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
    const removedPanel = mockDockviewApi.removePanel.mock.calls[0][0]
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

    // addPanel called 6 times initially + 1 re-add = 7
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(7)
    const lastCall = mockDockviewApi.addPanel.mock.calls[6][0]
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
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(7)
    expect(mockDockviewApi.addPanel.mock.calls[6][0].id).toBe('tools')
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
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(7)
    const codeEditorCall = mockDockviewApi.addPanel.mock.calls[6][0]
    expect(codeEditorCall.id).toBe('codeEditor')
    expect(codeEditorCall.tabComponent).toBe('codeEditorTab')
    expect(codeEditorCall.initialWidth).toBe(520)
    expect(codeEditorCall.position).toEqual({
      referencePanel: 'nodePanel',
      direction: 'right',
    })
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
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(7)
    expect(mockDockviewApi.addPanel.mock.calls[6][0].id).toBe('codeEditor')
    expect(mockDockviewApi.addPanel.mock.calls[6][0].tabComponent).toBe('codeEditorTab')
    expect(panels.get('codeEditor').api.setActive).toHaveBeenCalled()

    window.dispatchEvent(new CustomEvent('bif:open-code-editor-loading-finished'))
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
    const session = sessions.openSession({
      parentWorkflowName: 'parent',
      parentNodeId: 'sub_1',
      parentNodeName: 'Sub 1',
      graph: { nodes: [], edges: [] },
    })

    window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
      detail: { sessionId: session.id },
    }))
    await flushPromises()

    const lastCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ]?.[0]
    expect(lastCall).toMatchObject({
      component: 'subWorkflowEditor',
      title: 'Sub 1',
      params: { sessionId: session.id },
    })
    expect(lastCall.id).toContain('sub-workflow:')
    expect(panels.get(lastCall.id).api.setActive).toHaveBeenCalled()
  })

  it('opens and activates a named canvas tab for a root workflow graph', async () => {
    mountApp()
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'analysis',
        workflowDisplayName: 'Analysis',
        graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
        missingTools: [],
        dirty: false,
      },
    }))
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
      }),
    })
    expect(lastCall.id).toBe('workflow:analysis')
    expect(panels.get('workflow:analysis').api.setActive).toHaveBeenCalled()
    expect(useUIStore().activeWorkflowName).toBe('Analysis')
  })

  it('opens a workflow tab above bottom panels when no canvas tab remains', async () => {
    mountApp()
    await flushPromises()
    panels.delete('canvas')

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        workflowName: 'analysis',
        workflowDisplayName: 'Analysis',
        graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
        missingTools: [],
        dirty: false,
      },
    }))
    await flushPromises()

    const lastCall = mockDockviewApi.addPanel.mock.calls[
      mockDockviewApi.addPanel.mock.calls.length - 1
    ]?.[0]
    expect(lastCall).toMatchObject({
      id: 'workflow:analysis',
      position: {
        referencePanel: 'dataTable',
        direction: 'above',
      },
    })
  })

  it('activating a non-canvas panel keeps the current node selection', async () => {
    mountApp()
    await flushPromises()
    const ui = useUIStore()
    ui.setSelectedNodes(['node_1'])

    panels.get('tools').api.setActive()
    await flushPromises()

    expect(ui.selectedNodeIds).toEqual(['node_1'])
  })

  it('reactivating the startup canvas restores that canvas workflow context', async () => {
    mountApp()
    await flushPromises()
    const workflow = useWorkflowStore()
    workflow.workflows = [
      { name: 'analysis', display_name: 'Analysis' },
      { name: 'other', display_name: 'Other' },
    ] as any
    workflow.activateWorkflow('other')

    window.dispatchEvent(new CustomEvent('bioimageflow:canvas-context-updated', {
      detail: {
        panelId: 'canvas',
        workflowName: 'analysis',
        workflowDisplayName: 'Analysis',
      },
    }))
    panels.get('canvas').api.setActive()
    await flushPromises()

    expect(workflow.currentName).toBe('analysis')
    expect(useUIStore().activeWorkflowName).toBe('Analysis')
  })

  it('reopening an already open workflow tab activates it without replacing it', async () => {
    mountApp()
    await flushPromises()
    const detail = {
      workflowName: 'analysis',
      workflowDisplayName: 'Analysis',
      graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      missingTools: [],
      dirty: false,
    }

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail }))
    await flushPromises()
    const addCount = mockDockviewApi.addPanel.mock.calls.length
    const removeCount = mockDockviewApi.removePanel.mock.calls.length
    const activeCount = panels.get('workflow:analysis').api.setActive.mock.calls.length

    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail }))
    await flushPromises()

    expect(mockDockviewApi.addPanel.mock.calls.length).toBe(addCount)
    expect(mockDockviewApi.removePanel.mock.calls.length).toBe(removeCount)
    expect(panels.get('workflow:analysis').api.setActive.mock.calls.length)
      .toBeGreaterThan(activeCount)
  })

  it('keeps a dirty sub-workflow session open when direct tab close is cancelled', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mountApp()
    await flushPromises()
    const sessions = useSubWorkflowSessionsStore()
    const session = sessions.openSession({
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
      detail: { sessionId: session.id },
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
})
