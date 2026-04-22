import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Dataset, UploadResponse } from '@/api/types'

vi.mock('@/api/datasets', () => ({
  listDatasets: vi.fn(),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))

import { listDatasets, uploadDataset, deleteDataset } from '@/api/datasets'
import DatasetBrowser from '../DatasetBrowser.vue'

const mockedList = vi.mocked(listDatasets)
const mockedUpload = vi.mocked(uploadDataset)
const mockedDelete = vi.mocked(deleteDataset)

function makeDataset(overrides: Partial<Dataset> = {}): Dataset {
  return {
    id: 'd_abc',
    original_filename: 'cells.tif',
    path: '/srv/datasets/20260421T120000_cells.tif',
    size: 1024,
    upload_date: '2026-04-21T12:00:00Z',
    content_type: 'image/tiff',
    ...overrides,
  }
}

function stubs() {
  return {
    Dialog: {
      template:
        '<div v-if="visible" :data-testid="$attrs[\'data-testid\']"><slot /><slot name="footer" /></div>',
      props: ['visible', 'header'],
    },
    DataTable: {
      template:
        '<div :data-testid="$attrs[\'data-testid\']"><slot /><div v-for="row in value" :key="row.id" :data-testid="`row-${row.id}`" @click="$emit(\'update:selection\', row)">{{ row.original_filename }}</div></div>',
      props: ['value', 'selection'],
      emits: ['update:selection'],
    },
    Column: { template: '<div><slot /></div>' },
    Button: {
      template:
        '<button :data-testid="$attrs[\'data-testid\']" :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
      props: ['label', 'disabled'],
      emits: ['click'],
    },
    InputText: {
      template:
        '<input :data-testid="$attrs[\'data-testid\']" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      props: ['modelValue'],
      emits: ['update:modelValue'],
    },
    ProgressBar: { template: '<div class="progressbar">{{ value }}%</div>', props: ['value'] },
  }
}

function mountBrowser(props: Record<string, unknown> = {}) {
  return mount(DatasetBrowser, {
    props: {
      visible: true,
      parameterName: 'input_path',
      mode: 'pick',
      serverCap: 2 * 1024 ** 3,
      ...props,
    },
    global: {
      plugins: [createPinia()],
      stubs: stubs(),
    },
  })
}

describe('DatasetBrowser', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedList.mockResolvedValue([])
    mockedUpload.mockResolvedValue({ uploaded: [], errors: [] } as UploadResponse)
    mockedDelete.mockResolvedValue(undefined)
  })

  it('shows pick-mode title with parameter name', async () => {
    const wrapper = mountBrowser({ parameterName: 'my_input' })
    const vm = wrapper.vm as unknown as { dialogTitle: string }
    expect(vm.dialogTitle).toBe('Select dataset for: my_input')
  })

  it('shows upload-and-pick-mode title', async () => {
    const wrapper = mountBrowser({ mode: 'upload-and-pick' })
    const vm = wrapper.vm as unknown as { dialogTitle: string }
    expect(vm.dialogTitle).toBe('Upload datasets')
  })

  it('loads datasets on open', async () => {
    mockedList.mockResolvedValueOnce([makeDataset()])
    const wrapper = mountBrowser()
    await flushPromises()
    const vm = wrapper.vm as unknown as { datasets: Dataset[] }
    expect(vm.datasets).toHaveLength(1)
  })

  it('filters by extension when fileTypeFilter is set', async () => {
    mockedList.mockResolvedValueOnce([
      makeDataset({ id: 'd_1', original_filename: 'cells.tif' }),
      makeDataset({ id: 'd_2', original_filename: 'my_tif_backup.png' }),
    ])
    const wrapper = mountBrowser({ fileTypeFilter: ['*.tif', '*.tiff'] })
    await flushPromises()
    const vm = wrapper.vm as unknown as { filteredDatasets: Dataset[] }
    expect(vm.filteredDatasets.map((d) => d.id)).toEqual(['d_1'])
  })

  it('falls back to substring search when fileTypeFilter is empty', async () => {
    mockedList.mockResolvedValueOnce([
      makeDataset({ id: 'd_1', original_filename: 'cells.tif' }),
      makeDataset({ id: 'd_2', original_filename: 'background.png' }),
    ])
    const wrapper = mountBrowser()
    await flushPromises()
    const vm = wrapper.vm as unknown as { searchQuery: string; filteredDatasets: Dataset[] }
    vm.searchQuery = 'cell'
    await flushPromises()
    expect(vm.filteredDatasets.map((d) => d.id)).toEqual(['d_1'])
  })

  it('Select button is disabled until a row is selected', async () => {
    const wrapper = mountBrowser()
    const selectBtn = wrapper.find('[data-testid="dataset-browser-select"]')
    expect(selectBtn.attributes('disabled')).toBeDefined()
  })

  it('Select emits @select with the dataset path and closes', async () => {
    mockedList.mockResolvedValueOnce([makeDataset()])
    const wrapper = mountBrowser()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      selectedDataset: Dataset | null
      onSelect: () => void
    }
    vm.selectedDataset = makeDataset()
    await flushPromises()
    vm.onSelect()
    expect(wrapper.emitted('select')![0]).toEqual([
      '/srv/datasets/20260421T120000_cells.tif',
    ])
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])
  })

  it('Cancel emits @close', async () => {
    const wrapper = mountBrowser()
    const vm = wrapper.vm as unknown as { onCancel: () => void }
    vm.onCancel()
    expect(wrapper.emitted('close')).toBeTruthy()
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])
  })

  it('Delete button is disabled until a row is selected', async () => {
    const wrapper = mountBrowser()
    const deleteBtn = wrapper.find('[data-testid="dataset-browser-delete"]')
    expect(deleteBtn.attributes('disabled')).toBeDefined()
  })

  it('onDeleteConfirmed calls the API and refreshes', async () => {
    mockedList.mockResolvedValueOnce([makeDataset()])
    const wrapper = mountBrowser()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      selectedDataset: Dataset | null
      onDeleteConfirmed: () => Promise<void>
    }
    vm.selectedDataset = makeDataset()
    await vm.onDeleteConfirmed()
    expect(mockedDelete).toHaveBeenCalledWith('d_abc')
  })

  it('uploads each selected file as its own POST', async () => {
    mockedUpload.mockResolvedValue({
      uploaded: [
        {
          id: 'd_new',
          original_filename: 'a.tif',
          path: '/p',
          size: 1,
          upload_date: '2026-04-21T12:00:00Z',
          content_type: null,
        },
      ],
      errors: [],
    } as UploadResponse)
    const wrapper = mountBrowser()
    const vm = wrapper.vm as unknown as { onUploadFiles: (files: File[]) => Promise<void> }
    await vm.onUploadFiles([
      new File(['a'], 'a.tif', { type: 'image/tiff' }),
      new File(['b'], 'b.tif', { type: 'image/tiff' }),
    ])
    await flushPromises()
    expect(mockedUpload).toHaveBeenCalledTimes(2)
  })

  it('rejects files larger than serverCap * 1.1 without hitting the network', async () => {
    const wrapper = mountBrowser({ serverCap: 100 })
    const vm = wrapper.vm as unknown as { onUploadFiles: (files: File[]) => Promise<void> }
    const huge = new File([new Uint8Array(200)], 'huge.bin')
    await vm.onUploadFiles([huge])
    expect(mockedUpload).not.toHaveBeenCalled()
    expect(wrapper.emitted('toast')).toBeTruthy()
    expect(wrapper.emitted('toast')![0][0]).toMatchObject({ severity: 'error' })
  })

  it('shows pending-upload entries and surfaces errors with retry', async () => {
    let resolveFirst: ((value: UploadResponse) => void) | undefined
    mockedUpload.mockImplementationOnce(
      () => new Promise<UploadResponse>((resolve) => { resolveFirst = resolve }),
    )
    const wrapper = mountBrowser()
    const vm = wrapper.vm as unknown as {
      pendingUploads: Array<{ file: File; loaded: number; error?: string }>
      onUploadFiles: (files: File[]) => Promise<void>
      retryUpload: (entry: unknown) => void
    }

    const file = new File(['x'], 'err.tif')
    void vm.onUploadFiles([file])
    await flushPromises()
    expect(vm.pendingUploads).toHaveLength(1)

    resolveFirst?.({
      uploaded: [],
      errors: [{ filename: 'err.tif', error: 'file_too_large', detail: 'cap' }],
    } as UploadResponse)
    await flushPromises()
    expect(vm.pendingUploads[0].error).toBeTruthy()

    mockedUpload.mockResolvedValueOnce({ uploaded: [], errors: [] } as UploadResponse)
    const entry = vm.pendingUploads[0]
    vm.retryUpload(entry)
    await flushPromises()
    expect(mockedUpload).toHaveBeenCalledTimes(2)
  })

  it('upload-and-pick mode renders the Create Files node action', async () => {
    const wrapper = mountBrowser({ mode: 'upload-and-pick' })
    expect(wrapper.find('[data-testid="dataset-browser-create-node"]').exists()).toBe(true)
  })

  it('pick mode does not render the Create Files node action', async () => {
    const wrapper = mountBrowser({ mode: 'pick' })
    expect(wrapper.find('[data-testid="dataset-browser-create-node"]').exists()).toBe(false)
  })

  it('auto-uploads initialFiles in upload-and-pick mode', async () => {
    mockedUpload.mockResolvedValue({
      uploaded: [
        {
          id: 'd_init',
          original_filename: 'init.tif',
          path: '/p/init.tif',
          size: 1,
          upload_date: '2026-04-21T12:00:00Z',
          content_type: null,
        },
      ],
      errors: [],
    } as UploadResponse)
    mountBrowser({
      mode: 'upload-and-pick',
      initialFiles: [new File(['x'], 'init.tif')],
    })
    await flushPromises()
    expect(mockedUpload).toHaveBeenCalledTimes(1)
  })
})
