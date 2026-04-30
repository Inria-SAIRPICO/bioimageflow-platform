import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { getEditorStatus, openPathWithEditor } from '@/api/editor'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockedGet = vi.mocked(api.get as any)
const mockedPost = vi.mocked(api.post as any)

describe('editor api helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it('fetches editor status', async () => {
    mockedGet.mockResolvedValueOnce({
      data: { available: true, url: 'http://127.0.0.1:32344', version: '4.106.2', control_available: true },
    })

    await expect(getEditorStatus()).resolves.toMatchObject({ available: true })
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/editor/status')
  })

  it('shows success for external editor responses', async () => {
    const toast = { add: vi.fn() }
    mockedPost.mockResolvedValueOnce({
      data: { opened: true, method: 'external', url: null, path: '/tmp/tool.py', message: null },
    })

    await openPathWithEditor('/tmp/tool.py', toast)

    expect(mockedPost).toHaveBeenCalledWith('/api/v1/editor/open', { path: '/tmp/tool.py' })
    expect(toast.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success' }))
  })

  it('dispatches an activation event for embedded editor responses', async () => {
    const listener = vi.fn()
    window.addEventListener('bif:open-code-editor', listener)
    mockedPost.mockResolvedValueOnce({
      data: {
        opened: true,
        method: 'embedded',
        url: 'http://127.0.0.1:32344',
        path: '/tmp/tool.py',
        message: null,
      },
    })

    await openPathWithEditor('/tmp/tool.py')

    expect(listener).toHaveBeenCalledTimes(1)
    expect(listener.mock.calls[0][0].detail).toEqual({
      url: 'http://127.0.0.1:32344',
      path: '/tmp/tool.py',
    })
    window.removeEventListener('bif:open-code-editor', listener)
  })

  it('copies the path for clipboard fallback responses', async () => {
    const toast = { add: vi.fn() }
    mockedPost.mockResolvedValueOnce({
      data: {
        opened: false,
        method: 'clipboard',
        url: null,
        path: '/tmp/tool.py',
        message: 'Path copied - open in your local editor.',
      },
    })

    await openPathWithEditor('/tmp/tool.py', toast)

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/tmp/tool.py')
    expect(toast.add).toHaveBeenCalledWith(expect.objectContaining({
      summary: 'Path copied - open in your local editor.',
    }))
  })
})
