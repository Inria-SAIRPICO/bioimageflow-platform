import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { getEditorStatus, openPathWithEditor, openToolWithEditor } from '@/api/editor'

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

  it('can request editor startup while fetching status', async () => {
    mockedGet.mockResolvedValueOnce({
      data: { available: true, url: 'http://127.0.0.1:32344', version: '4.106.2', control_available: true },
    })

    await getEditorStatus({ launch: true })

    expect(mockedGet).toHaveBeenCalledWith('/api/v1/editor/status', {
      params: { launch: true },
    })
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

  it('can request a focused file while opening a project path', async () => {
    mockedPost.mockResolvedValueOnce({
      data: { opened: true, method: 'external', url: null, path: '/workspace/tools/tool.py', message: null },
    })

    await openPathWithEditor('/workspace', null, { focusPath: '/workspace/tools/tool.py' })

    expect(mockedPost).toHaveBeenCalledWith('/api/v1/editor/open', {
      path: '/workspace',
      focus_path: '/workspace/tools/tool.py',
    })
  })

  it('opens a tool script through the tool-specific editor endpoint', async () => {
    mockedPost.mockResolvedValueOnce({
      data: { opened: true, method: 'external', url: null, path: '/workspace/tools/tool.py', message: null },
    })

    await openToolWithEditor('MyTool', 'wf')

    expect(mockedPost).toHaveBeenCalledWith('/api/v1/editor/open-tool', {
      tool_name: 'MyTool',
      workflow_id: 'wf',
    })
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

  it('dispatches loading events around slow embedded open requests', async () => {
    const events: string[] = []
    let loadingDetail: unknown
    const onLoading = vi.fn((event: Event) => {
      loadingDetail = (event as CustomEvent).detail
      events.push('loading')
    })
    const onOpen = vi.fn(() => events.push('open'))
    const onFinished = vi.fn(() => events.push('finished'))
    window.addEventListener('bif:open-code-editor-loading', onLoading)
    window.addEventListener('bif:open-code-editor', onOpen)
    window.addEventListener('bif:open-code-editor-loading-finished', onFinished)
    mockedPost.mockImplementationOnce(async () => {
      events.push('post')
      return {
        data: {
          opened: true,
          method: 'embedded',
          url: 'http://127.0.0.1:32344',
          path: '/tmp/tool.py',
          message: null,
        },
      }
    })

    await openPathWithEditor('/tmp/tool.py', null, { showEmbeddedLoading: true })

    expect(events).toEqual(['loading', 'post', 'open', 'finished'])
    expect(loadingDetail).toEqual({ path: '/tmp/tool.py' })
    window.removeEventListener('bif:open-code-editor-loading', onLoading)
    window.removeEventListener('bif:open-code-editor', onOpen)
    window.removeEventListener('bif:open-code-editor-loading-finished', onFinished)
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
