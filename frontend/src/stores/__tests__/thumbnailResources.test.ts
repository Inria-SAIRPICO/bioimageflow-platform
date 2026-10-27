import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createThumbnailResources, type ThumbnailState } from '../thumbnails'

function response(status: 'pending' | 'ready' | 'failed' = 'ready', contents = 'image', environment = 'ready'): Response {
  return new Response(contents, { headers: {
    'X-Thumbnail-Status': status, 'X-Thumbnail-Environment': environment,
  } })
}

describe('thumbnail resources', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('owns one poll chain for repeated cells and reuses completed bytes in one inspection', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response('pending'))
      .mockResolvedValueOnce(response())
    const resources = createThumbnailResources({ fetcher })
    const first = vi.fn()
    const sibling = vi.fn()
    const leave = resources.subscribe('inspection-1:source-0', '/thumbnail?row=0', first)
    const leaveSibling = resources.subscribe('inspection-1:source-0', '/thumbnail?row=0&wait=20', sibling)
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(1)
    leave()
    await vi.advanceTimersByTimeAsync(250)
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(String(fetcher.mock.calls[1][0])).toContain('wait=20')
    expect(sibling).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'ready' }))
    expect(first).not.toHaveBeenCalledWith(expect.objectContaining({ status: 'ready' }))
    leaveSibling()
    const repeated = vi.fn()
    const leaveRepeated = resources.subscribe('inspection-1:source-0', '/thumbnail?row=0', repeated)
    expect(repeated).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'ready' }))
    await vi.advanceTimersByTimeAsync(20_000)
    expect(fetcher).toHaveBeenCalledTimes(2)
    leaveRepeated()
  })

  it('pauses after the last subscriber leaves without canceling its issued request', async () => {
    let finish!: (value: Response) => void
    const fetcher = vi.fn().mockReturnValueOnce(new Promise<Response>(resolve => { finish = resolve }))
    const installing = vi.fn()
    const resources = createThumbnailResources({ fetcher, onInstallingChange: installing })
    const listener = vi.fn()
    const leave = resources.subscribe('epoch:source', '/thumbnail', listener)
    leave()
    finish(response('pending', 'placeholder', 'installing'))
    await flushPromises()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetcher).toHaveBeenCalledOnce()
    expect(listener).toHaveBeenCalledOnce() // only the initial pending state
    expect(installing).not.toHaveBeenCalledWith('epoch:source', true)
  })

  it('revalidates a new inspection even for the same source and ignores old callbacks', async () => {
    let finishOld!: (value: Response) => void
    const fetcher = vi.fn()
      .mockReturnValueOnce(new Promise<Response>(resolve => { finishOld = resolve }))
      .mockResolvedValueOnce(response('ready', 'new bytes'))
    const resources = createThumbnailResources({ fetcher })
    const oldListener = vi.fn()
    const leaveOld = resources.subscribe('old:source', '/thumbnail', oldListener)
    leaveOld()
    const currentStates: ThumbnailState[] = []
    const leaveCurrent = resources.subscribe('new:source', '/thumbnail', state => currentStates.push(state))
    await flushPromises()
    const currentBlob = currentStates[currentStates.length - 1]!.blob
    finishOld(response('ready', 'old bytes'))
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(currentStates[currentStates.length - 1]!.blob).toBe(currentBlob)
    expect(oldListener).toHaveBeenCalledOnce()
    leaveCurrent()
  })

  it.each([
    { maxEntries: 2, maxBytes: 100 },
    { maxEntries: 10, maxBytes: 5 },
  ])('evicts completed entries within the configured budget %j', async limits => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response('ready', 'abc')))
    const resources = createThumbnailResources({ fetcher, ...limits })
    for (const key of ['a', 'b', 'c']) {
      const leave = resources.subscribe(key, `/thumbnail?source=${key}`, vi.fn())
      await flushPromises()
      leave()
    }
    expect(fetcher).toHaveBeenCalledTimes(3)
    const leave = resources.subscribe('a', '/thumbnail?source=a', vi.fn())
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(4)
    leave()
  })

  it('does not retain a failed response as a completed image', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response('failed')).mockResolvedValueOnce(response())
    const resources = createThumbnailResources({ fetcher })
    const leave = resources.subscribe('source', '/thumbnail', vi.fn())
    await flushPromises()
    leave()
    const current = vi.fn()
    const leaveCurrent = resources.subscribe('source', '/thumbnail', current)
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(current).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'ready' }))
    leaveCurrent()
  })
})
