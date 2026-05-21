import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ImageCell from '../ImageCell.vue'

vi.mock('@/api/client', () => ({
  api: { post: vi.fn() },
}))

import { api } from '@/api/client'

const READY_BYTES = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3])
const PENDING_BYTES = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 9, 9, 9])
const mockedPost = vi.mocked(api.post)

function makeFetchResponse(status: 'ready' | 'pending', bytes: Uint8Array): Response {
  const blob = new Blob([bytes], { type: 'image/png' })
  return new Response(blob, {
    status: 200,
    headers: { 'Content-Type': 'image/png', 'X-Thumbnail-Status': status },
  })
}

function mountCell(props = {}) {
  return mount(ImageCell, {
    props: { nodeId: 'n1', row: 0, col: 'mask', value: '/tmp/m.tif', ...props },
    global: { plugins: [PrimeVue] },
  })
}

describe('ImageCell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockedPost.mockReset()
    // jsdom doesn't ship URL.createObjectURL/revokeObjectURL
    if (typeof URL.createObjectURL !== 'function') {
      ;(URL as any).createObjectURL = vi.fn(() => 'blob:mock-url')
      ;(URL as any).revokeObjectURL = vi.fn()
    } else {
      vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    }
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('renders the thumbnail when the server replies "ready" on the first call', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(makeFetchResponse('ready', READY_BYTES))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountCell()
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/nodes/n1/thumbnail')
    const img = wrapper.find('img.image-cell__thumb')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('blob:mock-url')
  })

  it('requests and renders doubled thumbnails', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(makeFetchResponse('ready', READY_BYTES))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountCell()
    await flushPromises()

    const url = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost')
    expect(url.searchParams.get('size')).toBe('256')
    const thumb = wrapper.find('[data-testid="image-thumbnail"]')
    expect(thumb.attributes('style')).toContain('width: 96px')
    expect(thumb.attributes('style')).toContain('height: 96px')
  })

  it('retries when the server replies "pending" until it gets "ready"', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeFetchResponse('pending', PENDING_BYTES))
      .mockResolvedValueOnce(makeFetchResponse('pending', PENDING_BYTES))
      .mockResolvedValueOnce(makeFetchResponse('ready', READY_BYTES))
    vi.stubGlobal('fetch', fetchMock)

    mountCell()
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    // Advance past the first retry delay; expect a second fetch.
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(4_000)
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(3)

    // Once we've seen "ready", further timer ticks must NOT trigger more fetches.
    await vi.advanceTimersByTimeAsync(60_000)
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('shows a pending thumbnail indicator while generation is still running', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(makeFetchResponse('pending', PENDING_BYTES))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountCell()
    await flushPromises()

    expect(wrapper.find('img.image-cell__thumb').exists()).toBe(false)
    expect(wrapper.find('.image-cell__pending').exists()).toBe(true)
    expect(wrapper.find('.image-cell__unavailable').exists()).toBe(false)
    expect(wrapper.find('.image-cell__pending').attributes('aria-label')).toBe(
      'thumbnail generating',
    )
  })

  it('shows a pending thumbnail indicator while the first request is in flight', async () => {
    let resolveFetch!: (response: Response) => void
    const fetchMock = vi.fn().mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountCell()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(wrapper.find('img.image-cell__thumb').exists()).toBe(false)
    expect(wrapper.find('.image-cell__pending').exists()).toBe(true)
    expect(wrapper.find('.image-cell__unavailable').exists()).toBe(false)

    resolveFetch(makeFetchResponse('ready', READY_BYTES))
    await flushPromises()

    expect(wrapper.find('img.image-cell__thumb').exists()).toBe(true)
    expect(wrapper.find('.image-cell__pending').exists()).toBe(false)
  })

  it('cache-busts retries with a versioned query param', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeFetchResponse('pending', PENDING_BYTES))
      .mockResolvedValueOnce(makeFetchResponse('ready', READY_BYTES))
    vi.stubGlobal('fetch', fetchMock)

    mountCell()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const firstUrl = String(fetchMock.mock.calls[0][0])
    const secondUrl = String(fetchMock.mock.calls[1][0])
    expect(secondUrl).not.toBe(firstUrl)
    // Both URLs should target the same endpoint
    expect(firstUrl).toMatch(/\/api\/v1\/nodes\/n1\/thumbnail/)
    expect(secondUrl).toMatch(/\/api\/v1\/nodes\/n1\/thumbnail/)
  })

  it('stops retrying after the max attempts and shows thumbnail unavailable', async () => {
    // Always pending — exhaust retries.
    const fetchMock = vi.fn().mockResolvedValue(makeFetchResponse('pending', PENDING_BYTES))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountCell()
    await flushPromises()
    // Advance plenty so any reasonable retry schedule completes.
    for (let i = 0; i < 10; i++) {
      await vi.advanceTimersByTimeAsync(20_000)
      await flushPromises()
    }
    const calls = fetchMock.mock.calls.length
    // Allow some headroom but enforce a finite ceiling so a bug-induced
    // tight retry loop fails this test loudly.
    expect(calls).toBeGreaterThan(1)
    expect(calls).toBeLessThanOrEqual(8)
    expect(wrapper.find('.image-cell__unavailable').exists()).toBe(true)
    expect(wrapper.find('.image-cell__pending').exists()).toBe(false)
  })

  it('shows the unavailable fallback when the fetch errors out', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('network down'))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mountCell()
    await flushPromises()

    expect(wrapper.find('img.image-cell__thumb').exists()).toBe(false)
    expect(wrapper.find('.image-cell__unavailable').exists()).toBe(true)
    expect(wrapper.find('.image-cell__unavailable').attributes('aria-label')).toBe(
      'thumbnail unavailable',
    )
  })

  it('keeps Open in Napari enabled after a launch failure so the action can be retried', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeFetchResponse('ready', READY_BYTES))
    vi.stubGlobal('fetch', fetchMock)
    mockedPost.mockRejectedValueOnce({
      response: {
        status: 503,
        data: { error: 'napari_launch_failed', detail: 'solver crashed' },
      },
    })

    const wrapper = mountCell()
    await flushPromises()

    const button = wrapper.find('[data-testid="open-napari-0-mask"]')
    await button.trigger('click')
    await flushPromises()

    expect(button.attributes('disabled')).toBeUndefined()
  })

  it('requests an Avivator dock panel with a filename-suffixed image_url', async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeFetchResponse('ready', READY_BYTES))
    vi.stubGlobal('fetch', fetchMock)
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

    const wrapper = mountCell({ workflowName: 'wf a', value: '/tmp/mask.ome.tif' })
    await flushPromises()

    await wrapper.find('[data-testid="open-avivator-0-mask"]').trigger('click')

    const event = dispatchSpy.mock.calls
      .map(([arg]) => arg)
      .find((arg): arg is CustomEvent => arg instanceof CustomEvent
        && arg.type === 'bioimageflow:open-avivator')
    expect(event).toBeDefined()
    const { url, imageUrl, title } = event!.detail
    expect(title).toBe('mask.ome.tif')
    const avivatorUrl = new URL(String(url))
    expect(avivatorUrl.origin).toBe('http://avivator.gehlenborglab.org')
    expect(avivatorUrl.searchParams.get('image_url')).toBe(imageUrl)
    expect(new URL(imageUrl).href).toBe(
      `${window.location.origin}/api/v1/nodes/n1/image/mask.ome.tif?row=0&col=mask&workflow_name=wf+a`,
    )
  })
})
