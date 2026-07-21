import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Tree from 'primevue/tree'

const mocks = vi.hoisted(() => ({
  listDatasets: vi.fn().mockResolvedValue([]),
  listFolders: vi.fn().mockResolvedValue([]),
  resolveSelection: vi.fn(),
  addToolNode: vi.fn().mockReturnValue('files_1'),
  updateParameter: vi.fn().mockReturnValue(true),
  updateDataset: vi.fn(),
  updateFolder: vi.fn(),
}))

vi.mock('@/api/datasets', () => ({
  listDatasets: mocks.listDatasets,
  listDatasetFolders: mocks.listFolders,
  createDatasetFolder: vi.fn(),
  updateDatasetFolder: mocks.updateFolder,
  updateDataset: mocks.updateDataset,
  previewDatasetDelete: vi.fn(),
  deleteDatasetSelection: vi.fn(),
  resolveDatasetSelection: mocks.resolveSelection,
  uploadDataset: vi.fn(),
}))

vi.mock('@/composables/useCanvasCommands', () => ({
  useCanvasCommands: () => ({
    addToolNode: mocks.addToolNode,
    updateParameter: mocks.updateParameter,
  }),
}))

import DatasetsPanel from '../DatasetsPanel.vue'
import { useDatasetsStore } from '@/stores/datasets'
import { useUIStore } from '@/stores/ui'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import {
  DATASET_TREE_DRAG_MIME,
  decodeDatasetTreeDrag,
} from '@/utils/datasetDrag'

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
  Checkbox: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template: '<input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.checked)">',
  },
  Dialog: { template: '<div><slot/><slot name="footer"/></div>' },
}

describe('DatasetsPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mocks.listDatasets.mockResolvedValue([])
    mocks.listFolders.mockResolvedValue([])
    canvasSessionRegistry.dispose()
  })

  it('renders tree management without a synthetic root or row menus', async () => {
    const wrapper = mount(DatasetsPanel, { global: { plugins: [createPinia()], stubs } })
    await flushPromises()

    expect(wrapper.find('[data-testid="dataset-add-folder"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dataset-rename"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dataset-delete"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dataset-clear-selection"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dataset-create-files-node"]').exists()).toBe(true)
    expect(wrapper.find('.dataset-toolbar').attributes('aria-label')).toBe('Dataset editing actions')
    for (const [testId, label] of [
      ['dataset-add-folder', 'Add folder'],
      ['dataset-rename', 'Rename'],
      ['dataset-delete', 'Delete'],
    ]) {
      const button = wrapper.find(`[data-testid="${testId}"]`)
      expect(button.text()).toBe('')
      expect(button.attributes('aria-label')).toBe(label)
      expect(button.attributes('title')).toBe(label)
    }
    const clearSelection = wrapper.find('[data-testid="dataset-clear-selection"]')
    expect(clearSelection.text()).toBe('Unselect all')
    expect(clearSelection.element.parentElement?.classList).toContain('dataset-selection-actions')
    expect(wrapper.text()).not.toContain('Datasets root')
    expect(wrapper.text()).not.toContain('Move to top level')
    expect(wrapper.find('[data-testid="dataset-row-menu"]').exists()).toBe(false)
  })

  it('offers batch cancellation, completed-message cleanup, and inline error actions', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDatasetsStore()
    store.uploads = [
      { id: 'uploading', batchId: 1, file: new File(['a'], 'active.tif'), loaded: 1, total: 10, status: 'uploading' },
      { id: 'success', batchId: 1, file: new File(['b'], 'done.tif'), loaded: 1, total: 1, status: 'success' },
      { id: 'error', batchId: 1, file: new File(['c'], 'failed.tif'), loaded: 1, total: 1, status: 'error', message: 'No space left on device' },
    ]
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia], stubs } })
    await flushPromises()

    expect(wrapper.find('[data-testid="upload-cancel-all"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="upload-clear-completed"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('No space left on device')
    expect(wrapper.find('[data-testid="upload-retry-error"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="upload-dismiss-error"]').exists()).toBe(true)

    await wrapper.find('[data-testid="upload-clear-completed"]').trigger('click')
    expect(store.uploads.map(upload => upload.id)).toEqual(['uploading', 'error'])
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

  it('keeps row labels inert and uses the checkbox for selection', async () => {
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

    expect(useDatasetsStore().selectionKeys).toEqual({})
    await wrapper.find('[data-testid="dataset-checkbox-d_a"] input').setValue(true)

    expect(useDatasetsStore().selectionKeys).toEqual({ d_a: true })
    expect(wrapper.find('[data-testid="dataset-rename"]').attributes('disabled')).toBeUndefined()

    await wrapper.find('[data-testid="dataset-clear-selection"]').trigger('click')
    expect(useDatasetsStore().selectionKeys).toEqual({})
  })

  it('expands matching files parent folders while searching', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    mocks.listFolders.mockResolvedValue([
      { id: 'f_parent', name: 'Parent', parent_id: null, created_at: '2026-01-01T00:00:00Z' },
    ])
    mocks.listDatasets.mockResolvedValue([{
      id: 'd_a', original_filename: 'needle.tif', display_name: 'Needle image',
      path: '/managed/needle.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: 'f_parent',
    }])
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia, PrimeVue] } })
    await flushPromises()

    await wrapper.find('input.dataset-search').setValue('needle')
    await flushPromises()

    expect(wrapper.findComponent(Tree).props('expandedKeys')).toMatchObject({ f_parent: true })
    expect(wrapper.text()).toContain('Needle image')
  })

  it('selects a folder subtree in one click and exposes partial selection', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const folder = { id: 'f_parent', name: 'Parent', parent_id: null, created_at: '2026-01-01T00:00:00Z' }
    const first = {
      id: 'd_a', original_filename: 'a.tif', display_name: 'A',
      path: '/managed/a.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: 'f_parent',
    }
    const second = { ...first, id: 'd_b', original_filename: 'b.tif', display_name: 'B', path: '/managed/b.tif' }
    mocks.listFolders.mockResolvedValue([folder])
    mocks.listDatasets.mockResolvedValue([first, second])
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia], stubs } })
    await flushPromises()
    const vm = wrapper.vm as any
    const folderNode = vm.nodeMap.get('f_parent')

    vm.setNodeSelected(folderNode, true)
    await wrapper.vm.$nextTick()

    expect(useDatasetsStore().selectionKeys).toEqual({
      f_parent: true,
      d_a: true,
      d_b: true,
    })
    expect(vm.nodeSelectionState(folderNode)).toBe('all')
    expect((wrapper.find('[data-testid="dataset-rename"]').element as HTMLButtonElement).disabled).toBe(false)

    vm.setNodeSelected(vm.nodeMap.get('d_a'), false)

    expect(useDatasetsStore().selectionKeys).toEqual({ d_b: true })
    expect(vm.nodeSelectionState(folderNode)).toBe('partial')
  })

  it('moves every checked root without accepting PrimeVue tree mutation', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const folder = { id: 'f_parent', name: 'Parent', parent_id: null, created_at: '2026-01-01T00:00:00Z' }
    const first = {
      id: 'd_a', original_filename: 'a.tif', display_name: 'Zulu',
      path: '/managed/a.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: null,
    }
    const second = { ...first, id: 'd_b', original_filename: 'b.tif', display_name: 'Alpha', path: '/managed/b.tif' }
    mocks.listFolders.mockResolvedValue([folder])
    mocks.listDatasets.mockResolvedValue([first, second])
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia], stubs } })
    await flushPromises()
    useDatasetsStore().selectionKeys = { d_a: true, d_b: true }
    const vm = wrapper.vm as any
    const folderNode = vm.nodeMap.get('f_parent')
    const accept = vi.fn()

    vm.onNodeDrop({
      dragNode: vm.nodeMap.get('d_a'),
      dropNode: folderNode,
      originalEvent: new Event('drop'),
      value: vm.visibleNodes,
      accept,
    })
    await flushPromises()

    expect(accept).not.toHaveBeenCalled()
    expect(mocks.updateDataset).toHaveBeenCalledTimes(2)
    expect(mocks.updateDataset).toHaveBeenCalledWith('d_a', { folder_id: 'f_parent' })
    expect(mocks.updateDataset).toHaveBeenCalledWith('d_b', { folder_id: 'f_parent' })
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('Zulu')
  })

  it('keeps sorted siblings visible when a same-folder drop is a no-op', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const folder = { id: 'f_parent', name: 'Parent', parent_id: null, created_at: '2026-01-01T00:00:00Z' }
    const first = {
      id: 'd_a', original_filename: 'a.tif', display_name: 'A',
      path: '/managed/a.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: 'f_parent',
    }
    const second = { ...first, id: 'd_b', original_filename: 'b.tif', display_name: 'B', path: '/managed/b.tif' }
    mocks.listFolders.mockResolvedValue([folder])
    mocks.listDatasets.mockResolvedValue([first, second])
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia], stubs } })
    await flushPromises()
    const vm = wrapper.vm as any
    const accept = vi.fn()

    vm.onNodeDrop({
      dragNode: vm.nodeMap.get('d_a'),
      dropNode: vm.nodeMap.get('d_b'),
      originalEvent: new Event('drop'),
      value: vm.visibleNodes,
      accept,
    })
    await flushPromises()

    expect(accept).not.toHaveBeenCalled()
    expect(mocks.updateDataset).not.toHaveBeenCalled()
    expect(vm.visibleNodes[0].children.map((node: any) => node.label)).toEqual(['A', 'B'])
  })

  it('puts every checked file path on the canvas drag payload', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const first = {
      id: 'd_a', original_filename: 'a.tif', display_name: 'A',
      path: '/managed/a.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: null,
    }
    const second = { ...first, id: 'd_b', original_filename: 'b.tif', display_name: 'B', path: '/managed/b.tif' }
    mocks.listDatasets.mockResolvedValue([first, second])
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia], stubs } })
    await flushPromises()
    useDatasetsStore().selectionKeys = { d_a: true, d_b: true }
    const vm = wrapper.vm as any
    const setData = vi.fn()

    vm.onDatasetDragStart({ dataTransfer: { setData } }, vm.nodeMap.get('d_a'))

    expect(setData).toHaveBeenCalledOnce()
    expect(setData.mock.calls[0]![0]).toBe(DATASET_TREE_DRAG_MIME)
    expect(decodeDatasetTreeDrag(setData.mock.calls[0]![1])).toEqual([
      '/managed/a.tif',
      '/managed/b.tif',
    ])
  })

  it('sets resolved files on the single selected Files node', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const canvasId = canvasIdFromPanelId('workflow:test')
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'test' })
    canvasSessionRegistry.activate(canvasId)
    const ui = useUIStore()
    ui.setCanvasGraphNodes(canvasId, [{
      id: 'files_7',
      data: { name: 'Input images', toolName: 'Files' },
    }])
    ui.setCanvasSelectedNodes(canvasId, ['files_7'])
    const dataset = {
      id: 'd_a', original_filename: 'a.tif', display_name: 'A image',
      path: '/managed/a.tif', size: 1, upload_date: '2026-01-01T00:00:00Z',
      content_type: 'image/tiff', folder_id: null,
    }
    mocks.listDatasets.mockResolvedValue([dataset])
    mocks.resolveSelection.mockResolvedValue([dataset])
    const store = useDatasetsStore()
    store.selectionKeys = { d_a: true }
    const wrapper = mount(DatasetsPanel, { global: { plugins: [pinia], stubs } })
    await flushPromises()

    const button = wrapper.find('[data-testid="dataset-set-files-node"]')
    expect(button.text()).toBe('Set files on “Input images”')
    await button.trigger('click')
    await flushPromises()

    expect(mocks.updateParameter).toHaveBeenNthCalledWith(1, 'files_7', 'path', null)
    expect(mocks.updateParameter).toHaveBeenNthCalledWith(2, 'files_7', 'files', ['/managed/a.tif'])
  })
})
