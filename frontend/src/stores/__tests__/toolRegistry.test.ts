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

  it('applyToolReload upserts tools and package membership', () => {
    const store = useToolRegistryStore()
    store.packages = [{
      name: '__custom__',
      installed_versions: ['local'],
      available_versions: ['local'],
      active_version: 'local',
      tools: { local: [] },
      environment_status: 'stopped',
    }]

    store.applyToolReload({
      type: 'tool_reload',
      tool_name: 'CustomTool',
      tool_metadata: {
        name: 'CustomTool',
        display_name: 'Custom Tool',
        package: '__custom__',
        package_version: 'local',
        tool_type: 'ProcessingTool',
        inputs: {},
        outputs: {},
        tags: [],
        categories: [],
        source_kind: 'custom',
        editable: true,
      },
    })

    expect(store.getToolByName('CustomTool')?.editable).toBe(true)
    expect(store.packages[0]!.tools.local).toContain('CustomTool')
  })

  it('applyToolRemoved removes tools and package membership', () => {
    const store = useToolRegistryStore()
    store.tools = [{
      name: 'CustomTool',
      display_name: 'Custom Tool',
      package: '__custom__',
      package_version: 'local',
      tool_type: 'ProcessingTool',
      inputs: {},
      outputs: {},
      tags: [],
      categories: [],
      source_kind: 'custom',
      editable: true,
    }]
    store.packages = [{
      name: '__custom__',
      installed_versions: ['local'],
      available_versions: ['local'],
      active_version: 'local',
      tools: { local: ['CustomTool'] },
      environment_status: 'stopped',
    }]

    store.applyToolRemoved({
      type: 'tool_removed',
      tool_name: 'CustomTool',
    })

    expect(store.getToolByName('CustomTool')).toBeUndefined()
    expect(store.packages[0]!.tools.local).not.toContain('CustomTool')
  })
})
