import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import MenuBar from '../MenuBar.vue'
import { useUIStore } from '@/stores/ui'
import { useErrorStore } from '@/stores/errors'

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

let pinia: ReturnType<typeof createPinia>

function mountMenuBar() {
  return mount(MenuBar, {
    global: {
      plugins: [pinia, [PrimeVue, { theme: { preset: Aura } }]],
    },
  })
}

describe('MenuBar', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
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

  it('View menu has 4 panel toggle items', () => {
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any
    const viewMenu = vm.menuItems.find((item: any) => item.label === 'View')
    expect(viewMenu.items).toHaveLength(4)
    const toggleLabels = viewMenu.items.map((item: any) => item.label)
    expect(toggleLabels).toEqual(['Tools Panel', 'Nodes', 'Data Table', 'Logger'])
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

  describe('Execution menu', () => {
    it('exposes Run Workflow / Run Selected / Stop entries', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const exec = vm.menuItems.find((item: any) => item.label === 'Execution')
      expect(exec.items.map((i: any) => i.label)).toEqual([
        'Run Workflow',
        'Run Selected',
        'Stop',
      ])
    })

    it('Run Workflow is enabled when idle', () => {
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
