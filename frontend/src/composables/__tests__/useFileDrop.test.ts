import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { useFileDrop } from '../useFileDrop'
import { useDatasetsStore } from '@/stores/datasets'

function mountHost() {
  const Host = defineComponent({
    setup() {
      useFileDrop()
      return () => h('div')
    },
  })
  return mount(Host, { global: { plugins: [createPinia()] } })
}

function makeDragEvent(opts: { files?: File[]; types?: string[]; type?: string }): DragEvent {
  const files = opts.files ?? []
  const event = new Event(opts.type ?? 'drop', { bubbles: true, cancelable: true }) as DragEvent
  Object.defineProperty(event, 'dataTransfer', {
    value: { files, types: opts.types ?? (files.length ? ['Files'] : []) },
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
