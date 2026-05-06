import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { useWorkflowStore } from '@/stores/workflow'
import WorkflowsPanel from '../WorkflowsPanel.vue'
import type { WorkflowInfo } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn() },
}))

const workflows: WorkflowInfo[] = [
  {
    name: 'alpha_api',
    display_name: 'Alpha Workflow',
    description: 'Segment nuclei and measure intensities.',
    path: '/library/workflows/alpha_api/workflow.bioimageflow.json',
    storage_path: '/library/workflows/alpha_api',
    last_modified: '2026-04-30T12:34:56Z',
  },
  {
    name: 'beta_api',
    display_name: 'Beta Workflow',
    description: null,
    path: '/library/workflows/beta_api/workflow.bioimageflow.json',
    storage_path: '/library/workflows/beta_api',
    last_modified: '2026-05-01T08:00:00Z',
  },
]

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useWorkflowStore()
  store.workflows = [...workflows]
  store.current = workflows[0]

  return mount(WorkflowsPanel, {
    global: {
      plugins: [pinia, PrimeVue],
      stubs: {
        Button: true,
        InputText: true,
      },
    },
  })
}

describe('WorkflowsPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders compact workflow rows with display name and modified time only', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    const row = wrapper.find('[data-testid="workflow-row-alpha_api"]')
    expect(row.text()).toContain('Alpha Workflow')
    expect(row.find('[data-testid="workflow-row-time-alpha_api"]').text()).not.toBe('')
    expect(row.text()).not.toContain('alpha_api')
    expect(row.text()).not.toContain('/library/workflows/alpha_api')
    expect(row.text()).not.toContain('Segment nuclei')
  })

  it('shows selected workflow details with description, API name, file path, and storage path', async () => {
    const wrapper = mountPanel()
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('click')

    expect(wrapper.emitted('select-workflow')?.[0]).toEqual(['beta_api'])
    expect(wrapper.find('[data-testid="workflow-detail-description"]').text()).toContain(
      'No description.',
    )
    expect(wrapper.find('[data-testid="workflow-detail-api-name"]').text()).toContain('beta_api')
    expect(wrapper.find('[data-testid="workflow-detail-path"]').text()).toContain(
      '/library/workflows/beta_api/workflow.bioimageflow.json',
    )
    expect(wrapper.find('[data-testid="workflow-detail-storage-path"]').text()).toContain(
      '/library/workflows/beta_api',
    )
  })

  it('emits toolbar workflow actions using the selected workflow when required', async () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = mountPanel()
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('click')

    await wrapper.find('[data-testid="workflow-new-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-save-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-duplicate-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-import-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-export-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-delete-btn"]').trigger('click')

    expect(wrapper.emitted('new-workflow')).toHaveLength(1)
    expect(wrapper.emitted('save-workflow')).toHaveLength(1)
    expect(wrapper.emitted('duplicate-workflow')?.[0]).toEqual(['beta_api'])
    expect(wrapper.emitted('import-workflow')).toHaveLength(1)
    expect(wrapper.emitted('export-workflow')?.[0]).toEqual(['beta_api'])
    expect(wrapper.emitted('delete-workflow')?.[0]).toEqual(['beta_api'])
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({
      type: 'bioimageflow:workflow-command',
    }))
    dispatchSpy.mockRestore()
  })

  it('opens the selected workflow on double click, Enter, and Open', async () => {
    const wrapper = mountPanel()

    await wrapper.find('[data-testid="workflow-row-alpha_api"]').trigger('dblclick')
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('click')
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('keydown.enter')
    await wrapper.find('[data-testid="workflow-open-btn"]').trigger('click')

    expect(wrapper.emitted('open-workflow')).toEqual([
      ['alpha_api'],
      ['beta_api'],
      ['beta_api'],
    ])
  })

  it('only sets the workflow drag MIME type from the drag handle', async () => {
    const wrapper = mountPanel()
    const setData = vi.fn()
    const dataTransfer = { setData }

    expect(wrapper.find('[data-testid="workflow-row-alpha_api"]').attributes('draggable')).toBeUndefined()
    await wrapper.find('[data-testid="workflow-drag-alpha_api"]').trigger('dragstart', {
      dataTransfer,
    })

    expect(setData).toHaveBeenCalledTimes(1)
    expect(setData).toHaveBeenCalledWith('application/bioimageflow-workflow', 'alpha_api')
    expect(setData).not.toHaveBeenCalledWith('text/plain', expect.any(String))
  })
})
