import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { useFileDrop } from '../useFileDrop'
import { useDatasetsStore } from '@/stores/datasets'
import { useErrorStore } from '@/stores/errors'

function mountHost() {
  const Host = defineComponent({
    setup() {
      useFileDrop()
      return () => h('div')
    },
  })
  return mount(Host, { global: { plugins: [createPinia()] } })
}

function makeDragEvent(opts: {
  files?: File[]
  items?: Array<Partial<DataTransferItem>>
  types?: string[]
  type?: string
}): DragEvent {
  const files = opts.files ?? []
  const event = new Event(opts.type ?? 'drop', { bubbles: true, cancelable: true }) as DragEvent
  Object.defineProperty(event, 'dataTransfer', {
    value: {
      files,
      items: opts.items ?? [],
      types: opts.types ?? (files.length ? ['Files'] : []),
    },
  })
  return event
}

describe('useFileDrop', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => vi.restoreAllMocks())

  it('ignores palette tool drops', () => {
    const wrapper = mountHost()
    const store = useDatasetsStore()
    const queue = vi.spyOn(store, 'queueUploads')

    window.dispatchEvent(makeDragEvent({ types: ['application/bioimageflow-tool'] }))

    expect(queue).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('queues dropped files as managed datasets and activates the panel', () => {
    const wrapper = mountHost()
    const store = useDatasetsStore()
    const queue = vi.spyOn(store, 'queueUploads').mockImplementation(() => store.activate())
    const files = [new File(['x'], 'a.tif'), new File(['y'], 'b.tif')]

    window.dispatchEvent(makeDragEvent({ files }))

    expect(queue).toHaveBeenCalledWith(files)
    expect(store.activationRequest).toBe(1)
    wrapper.unmount()
  })

  it('uses the managed upload flow even when desktop File.path is present', () => {
    const wrapper = mountHost()
    const store = useDatasetsStore()
    const queue = vi.spyOn(store, 'queueUploads').mockImplementation(() => undefined)
    const file = new File(['x'], 'cells.tif')
    ;(file as File & { path?: string }).path = '/desktop/cells.tif'

    window.dispatchEvent(makeDragEvent({ files: [file] }))

    expect(queue).toHaveBeenCalledWith([file])
    wrapper.unmount()
  })

  it('rejects directory drops and reports a user-visible upload error', () => {
    const wrapper = mountHost()
    const datasets = useDatasetsStore()
    const errors = useErrorStore()
    const queue = vi.spyOn(datasets, 'queueUploads')
    const folder = new File([], 'images')
    const drop = makeDragEvent({
      files: [folder],
      items: [{
        kind: 'file',
        webkitGetAsEntry: () => ({ isDirectory: true, name: 'images' }),
      } as Partial<DataTransferItem>],
    })

    window.dispatchEvent(drop)

    expect(drop.defaultPrevented).toBe(true)
    expect(queue).not.toHaveBeenCalled()
    expect(errors.errors).toHaveLength(1)
    expect(errors.errors[0]).toMatchObject({
      kind: 'dataset_upload_rejected',
      detail: 'Folder "images" cannot be uploaded. Drop files instead.',
      acknowledged: false,
    })
    wrapper.unmount()
  })

  it('prevents browser navigation for file dragover and drop', () => {
    const wrapper = mountHost()
    const store = useDatasetsStore()
    vi.spyOn(store, 'queueUploads').mockImplementation(() => undefined)
    const file = new File(['x'], 'a.tif')
    const dragover = makeDragEvent({ files: [file], type: 'dragover' })
    const drop = makeDragEvent({ files: [file] })

    window.dispatchEvent(dragover)
    window.dispatchEvent(drop)

    expect(dragover.defaultPrevented).toBe(true)
    expect(drop.defaultPrevented).toBe(true)
    wrapper.unmount()
  })
})
