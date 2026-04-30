import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import Aura from '@primevue/themes/aura'
import App from '@/App.vue'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'

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
const mockDockviewApi = { addPanel: vi.fn(), getPanel: vi.fn(), removePanel: vi.fn() }
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

function mountApp() {
  // Reset mock state
  panels.clear()
  mockDockviewApi.addPanel.mockReset()
  mockDockviewApi.addPanel.mockImplementation((options: any) => {
    const panel = { id: options.id, api: { setVisible: vi.fn(), setActive: vi.fn() } }
    panels.set(options.id, panel)
    return panel
  })
  mockDockviewApi.getPanel.mockReset()
  mockDockviewApi.getPanel.mockImplementation((id: string) => panels.get(id))
  mockDockviewApi.removePanel.mockReset()
  mockDockviewApi.removePanel.mockImplementation((panel: any) => panels.delete(panel.id))

  return mount(App, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }], ConfirmationService],
      stubs: {
        ToolsPanel: { template: '<div data-testid="panel-tools">Tools stub</div>' },
        CanvasView: { template: '<div data-testid="panel-canvas">Canvas stub</div>' },
      },
    },
  })
}

describe('AppShell', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
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

  it('connects the WebSocket on startup', async () => {
    mountApp()
    await flushPromises()
    expect(connectMock).toHaveBeenCalledTimes(1)
  })

  it('registers all 5 panels on ready', async () => {
    const wrapper = mountApp()
    await flushPromises()
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(5)

    const panelIds = mockDockviewApi.addPanel.mock.calls.map((call: any) => call[0].id)
    expect(panelIds).toContain('tools')
    expect(panelIds).toContain('canvas')
    expect(panelIds).toContain('nodePanel')
    expect(panelIds).toContain('dataTable')
    expect(panelIds).toContain('logger')
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

    // addPanel called 5 times initially + 1 re-add = 6
    expect(mockDockviewApi.addPanel).toHaveBeenCalledTimes(6)
    const lastCall = mockDockviewApi.addPanel.mock.calls[5][0]
    expect(lastCall.id).toBe('tools')
    expect(lastCall.initialWidth).toBe(320)
  })

  it('canvas panel is not toggleable', () => {
    const store = useUIStore()
    expect('canvas' in store.panels).toBe(false)
  })
})
