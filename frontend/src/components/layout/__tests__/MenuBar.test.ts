import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'

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
  setLastOpenedWorkflow: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: toastAdd }),
}))

vi.mock('@/api/client', () => ({
  api: apiMocks,
}))

vi.mock('@/composables/useAutoSave', () => ({
  useAutoSave: () => autoSaveMocks,
}))

import MenuBar from '../MenuBar.vue'
import { useUIStore } from '@/stores/ui'
import { useErrorStore } from '@/stores/errors'
import { useWorkflowStore } from '@/stores/workflow'

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
    autoSaveMocks.setLastOpenedWorkflow.mockClear()
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

  it('View menu has 6 panel toggle items', () => {
    const wrapper = mountMenuBar()
    const vm = wrapper.vm as any
    const viewMenu = vm.menuItems.find((item: any) => item.label === 'View')
    expect(viewMenu.items).toHaveLength(6)
    const toggleLabels = viewMenu.items.map((item: any) => item.label)
    expect(toggleLabels).toEqual([
      'Tools Panel',
      'Workflows Panel',
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
    it('omits dependency-only entries and shows an icon for Save As', () => {
      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflow = vm.menuItems.find((item: any) => item.label === 'Workflow')
      const labels = workflow.items.map((item: any) => item.label)

      expect(labels).toEqual(['New', 'Open', 'Save', 'Save As', 'Import', 'Export', 'Delete'])
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
      const workflow = useWorkflowStore()
      workflow.current = {
        name: 'cell_segmentation',
        display_name: 'Cell segmentation',
        path: '/tmp/cell_segmentation.json',
        last_modified: '2026-04-29T00:00:00Z',
      }
      const exportWorkflow = vi
        .spyOn(workflow, 'exportWorkflow')
        .mockResolvedValue(undefined)

      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      await workflowMenu.items.find((item: any) => item.label === 'Export').command()

      expect(exportWorkflow).toHaveBeenCalledWith('cell_segmentation')
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
        },
      })
      const wrapper = mountMenuBar()

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

    it('shows an edit-name affordance when a workflow is active', async () => {
      const workflow = useWorkflowStore()
      workflow.current = {
        name: 'cell_segmentation',
        display_name: 'Cell segmentation',
        path: '/tmp/cell_segmentation.json',
        last_modified: '2026-04-29T00:00:00Z',
      }
      useUIStore().setActiveWorkflow('Cell segmentation')

      const wrapper = mountMenuBar()
      await wrapper.vm.$nextTick()

      const edit = wrapper.find('[data-testid="workflow-title-edit"]')
      expect(edit.exists()).toBe(true)
      expect(edit.attributes('aria-label')).toBe('Rename workflow')
    })

    it('save success toast uses the workflow display name', async () => {
      const workflow = useWorkflowStore()
      workflow.current = {
        name: 'new_workflow',
        display_name: 'New workflow',
        path: '/tmp/new_workflow.json',
        last_modified: '2026-04-29T00:00:00Z',
      }
      useUIStore().setActiveWorkflow('New workflow')
      apiMocks.put.mockResolvedValue({
        data: {
          name: 'new_workflow',
          display_name: 'New workflow',
          path: '/tmp/new_workflow.json',
          last_modified: '2026-04-29T00:00:01Z',
        },
      })

      const wrapper = mountMenuBar()
      const vm = wrapper.vm as any
      const workflowMenu = vm.menuItems.find((item: any) => item.label === 'Workflow')
      await workflowMenu.items.find((item: any) => item.label === 'Save').command()

      expect(apiMocks.put).toHaveBeenCalledWith(
        '/api/v1/workflows/new_workflow',
        { graph: { nodes: [], edges: [] } },
      )
      expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
        summary: 'Workflow saved',
        detail: 'New workflow',
      }))
    })
  })

  describe('Edit menu', () => {
    it('enables commands that are implemented by the canvas', () => {
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
