import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import { useToolRegistryStore } from '@/stores/toolRegistry'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

describe('toolRegistry custom tool actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedApi.get.mockImplementation((url: string) => {
      if (url === '/api/v1/tools') return Promise.resolve({ data: [] })
      if (url === '/api/v1/tools/packages') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: {} })
    })
  })

  it('createTool posts the documented body and refreshes read models', async () => {
    mockedApi.post.mockResolvedValueOnce({
      data: {
        name: 'MyTool',
        tool_type: 'ProcessingTool',
        path: '/tmp/my_tool.py',
        source_kind: 'custom',
        editable: true,
      },
    })
    const store = useToolRegistryStore()

    const result = await store.createTool({ name: 'MyTool', tool_type: 'ProcessingTool' })

    expect(result.path).toBe('/tmp/my_tool.py')
    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/tools', {
      name: 'MyTool',
      tool_type: 'ProcessingTool',
    })
    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools')
    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools/packages')
  })

  it('renameTool records validation errors and clears busy state', async () => {
    mockedApi.patch.mockRejectedValueOnce(new Error('validation failed'))
    const store = useToolRegistryStore()

    await expect(store.renameTool('OldName', 'bad name')).rejects.toThrow('validation failed')

    expect(store.error).toBe('validation failed')
    expect(store.customToolBusy).toBe(false)
  })

  it('deleteTool records conflict errors and clears busy state', async () => {
    mockedApi.delete.mockRejectedValueOnce(new Error('conflict'))
    const store = useToolRegistryStore()

    await expect(store.deleteTool('MyTool')).rejects.toThrow('conflict')

    expect(store.error).toBe('conflict')
    expect(store.customToolBusy).toBe(false)
  })

  it('custom tool busy state is isolated from package install calls', async () => {
    let resolvePost: (value: unknown) => void = () => {}
    mockedApi.post.mockImplementationOnce(
      () => new Promise((resolve) => {
        resolvePost = resolve
      }),
    )
    const store = useToolRegistryStore()

    const pending = store.createTool({ name: 'MyTool', tool_type: 'ProcessingTool' })
    expect(store.customToolBusy).toBe(true)

    resolvePost({
      data: {
        name: 'MyTool',
        tool_type: 'ProcessingTool',
        path: '/tmp/my_tool.py',
        source_kind: 'custom',
        editable: true,
      },
    })
    await pending

    expect(store.customToolBusy).toBe(false)
  })
})
