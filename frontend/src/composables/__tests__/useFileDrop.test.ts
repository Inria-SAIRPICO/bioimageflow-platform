import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

vi.mock('@/utils/nativeDialogs', () => ({
  isDesktop: vi.fn(),
}))

import { isDesktop } from '@/utils/nativeDialogs'
import { useFileDrop } from '../useFileDrop'
import { useDatasetBrowserStore } from '@/stores/datasetBrowser'

const mockedIsDesktop = vi.mocked(isDesktop)

function mountHost(onPaths: (paths: string[]) => void) {
  const Host = defineComponent({
    setup() {
      useFileDrop({ onPaths })
      return () => h('div')
    },
  })
  return mount(Host, { global: { plugins: [createPinia()] } })
}

function makeDragEvent(opts: {
  files?: File[]
  types?: string[]
}): DragEvent {
  const files = opts.files ?? []
  const types = opts.types ?? (files.length > 0 ? ['Files'] : [])
  const event = new Event('drop', { bubbles: true, cancelable: true }) as DragEvent
  Object.defineProperty(event, 'dataTransfer', {
    value: {
      files: Object.assign(files, { item: (i: number) => files[i] }),
      types,
    },
  })
  return event
}

describe('useFileDrop', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedIsDesktop.mockReturnValue(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('ignores palette-tool drops (application/bioimageflow-tool)', () => {
    const onPaths = vi.fn()
    const wrapper = mountHost(onPaths)
    const store = useDatasetBrowserStore()

    const event = makeDragEvent({
      files: [],
      types: ['application/bioimageflow-tool'],
    })
    window.dispatchEvent(event)

    expect(store.isOpen).toBe(false)
    expect(onPaths).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('opens the dataset browser in browser mode with initialFiles', async () => {
    const onPaths = vi.fn()
    const wrapper = mountHost(onPaths)
    const store = useDatasetBrowserStore()

    const files = [new File(['x'], 'a.tif'), new File(['y'], 'b.tif')]
    const event = makeDragEvent({ files })
    window.dispatchEvent(event)

    expect(store.isOpen).toBe(true)
    expect(store.options?.mode).toBe('upload-and-pick')
    expect(store.options?.initialFiles?.map((f) => f.name)).toEqual(['a.tif', 'b.tif'])

    // When the modal emits createFilesNode, onPaths is called with the paths
    store.onCreateFilesNode(['/server/a.tif', '/server/b.tif'])
    expect(onPaths).toHaveBeenCalledWith(['/server/a.tif', '/server/b.tif'])
    wrapper.unmount()
  })

  it('uses File.path in desktop mode without opening the modal', () => {
    mockedIsDesktop.mockReturnValue(true)
    const onPaths = vi.fn()
    const wrapper = mountHost(onPaths)
    const store = useDatasetBrowserStore()

    const file = new File(['x'], 'cells.tif')
    ;(file as File & { path?: string }).path = '/desktop/cells.tif'
    const event = makeDragEvent({ files: [file] })
    window.dispatchEvent(event)

    expect(onPaths).toHaveBeenCalledWith(['/desktop/cells.tif'])
    expect(store.isOpen).toBe(false)
    wrapper.unmount()
  })

  it('falls back to browser-mode flow in desktop when File.path is missing', () => {
    mockedIsDesktop.mockReturnValue(true)
    const onPaths = vi.fn()
    const wrapper = mountHost(onPaths)
    const store = useDatasetBrowserStore()

    const file = new File(['x'], 'cells.tif')
    // No .path injected
    const event = makeDragEvent({ files: [file] })
    window.dispatchEvent(event)

    expect(store.isOpen).toBe(true)
    expect(store.options).toMatchObject({ mode: 'upload-and-pick' })
    wrapper.unmount()
  })

  it('prevents the browser from navigating on dragover+drop of files', () => {
    const onPaths = vi.fn()
    const wrapper = mountHost(onPaths)

    const file = new File(['x'], 'a.tif')
    const dragover = makeDragEvent({ files: [file] })
    Object.defineProperty(dragover, 'type', { value: 'dragover' })
    window.dispatchEvent(dragover)
    expect(dragover.defaultPrevented).toBe(true)

    const drop = makeDragEvent({ files: [file] })
    window.dispatchEvent(drop)
    expect(drop.defaultPrevented).toBe(true)
    wrapper.unmount()
  })
})
