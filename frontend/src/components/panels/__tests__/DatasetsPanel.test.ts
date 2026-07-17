import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'

const mocks = vi.hoisted(() => ({
  listDatasets: vi.fn().mockResolvedValue([]),
  listFolders: vi.fn().mockResolvedValue([]),
  resolveSelection: vi.fn(),
  addToolNode: vi.fn().mockReturnValue('files_1'),
}))

vi.mock('@/api/datasets', () => ({
  listDatasets: mocks.listDatasets,
  listDatasetFolders: mocks.listFolders,
  createDatasetFolder: vi.fn(),
  updateDatasetFolder: vi.fn(),
  updateDataset: vi.fn(),
  previewDatasetDelete: vi.fn(),
  deleteDatasetSelection: vi.fn(),
  resolveDatasetSelection: mocks.resolveSelection,
  uploadDataset: vi.fn(),
}))

vi.mock('@/composables/useCanvasCommands', () => ({
  useCanvasCommands: () => ({ addToolNode: mocks.addToolNode }),
}))

import DatasetsPanel from '../DatasetsPanel.vue'
import { useDatasetsStore } from '@/stores/datasets'

const stubs = {
  Tree: {
    props: ['value'],
    template: '<div data-testid="datasets-tree"><div v-for="node in value" :key="node.key">{{ node.label }}</div></div>',
  },
  Button: {
    props: ['label', 'disabled'],
    emits: ['click'],
    template: '<button :data-testid="$attrs[\'data-testid\']" :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
  },
  InputText: { props: ['modelValue'], template: '<input data-testid="datasets-search" />' },
  ProgressBar: { props: ['value'], template: '<div data-testid="datasets-progress">{{ value }}</div>' },
  Dialog: { template: '<div><slot/><slot name="footer"/></div>' },
}

describe('DatasetsPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mocks.listDatasets.mockResolvedValue([])
    mocks.listFolders.mockResolvedValue([])
  })

  it('renders tree management without a synthetic root or row menus', async () => {
    const wrapper = mount(DatasetsPanel, { global: { plugins: [createPinia()], stubs } })
    await flushPromises()

    expect(wrapper.find('[data-testid="dataset-add-folder"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dataset-rename"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dataset-delete"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dataset-create-files-node"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Datasets root')
    expect(wrapper.find('[data-testid="dataset-row-menu"]').exists()).toBe(false)
  })

  it('resolves files and folders into an explicit Files-node snapshot', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDatasetsStore()
    store.datasets = [{
      id: 'd_a', original_filename: 'a.tif', display_name: 'A image',
      path: '/managed/a.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: 'f_group',
    }]
    store.folders = [{ id: 'f_group', name: 'Group', parent_id: null, created_at: '2026-01-01T00:00:00Z' }]
    store.selectionKeys = { f_group: true }
    mocks.listDatasets.mockResolvedValue(store.datasets)
    mocks.listFolders.mockResolvedValue(store.folders)
    mocks.resolveSelection.mockResolvedValue(store.datasets)
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia], stubs } })
    await flushPromises()

    await wrapper.find('[data-testid="dataset-create-files-node"]').trigger('click')
    await flushPromises()

    expect(mocks.resolveSelection).toHaveBeenCalledWith({ dataset_ids: [], folder_ids: ['f_group'] })
    expect(mocks.addToolNode).toHaveBeenCalledWith('Files', { files: ['/managed/a.tif'] })
  })

  it('selects a real PrimeVue tree row from its visible label', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const dataset = {
      id: 'd_a', original_filename: 'a.tif', display_name: 'A image',
      path: '/managed/a.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: null,
    }
    mocks.listDatasets.mockResolvedValue([dataset])
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia, PrimeVue] } })
    await flushPromises()

    await wrapper.find('.dataset-node-label').trigger('click')

    expect(useDatasetsStore().selectionKeys).toEqual({ d_a: true })
    expect(wrapper.find('[data-testid="dataset-rename"]').attributes('disabled')).toBeUndefined()
  })
})
