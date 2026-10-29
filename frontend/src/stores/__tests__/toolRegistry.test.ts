import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import type { ToolMetadata } from '@/api/types'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

function catalogTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'CustomTool',
    display_name: 'Custom Tool',
    package: '__custom__',
    package_version: 'local',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    dataframe_output: false,
    row_consumption: 'mapped',
    documentation: '',
    inputs: {},
    outputs: {},
    tags: [],
    categories: [],
    source_kind: 'custom',
    editable: true,
    ...overrides,
  }
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

  it('finds an existing catalog tool when its query omits one letter', () => {
    const store = useToolRegistryStore()
    store.tools = [catalogTool()]

    expect(store.searchTools('custm')).toEqual(store.tools)
  })

  it.each([
    ['identifier with acronym boundaries', { name: 'OMEImageReader', display_name: 'Unrelated' }, 'imgae'],
    ['display name', { display_name: 'Gaussian Blur' }, 'gausian'],
    ['tag', { tags: ['segmentation'] }, 'segmentationx'],
    ['category', { categories: ['Morphology'] }, 'morpholpgy'],
    ['documentation keyword', { documentation: 'Measures fluorescence.' }, 'fluorescense'],
  ] satisfies Array<[string, Partial<ToolMetadata>, string]>)(
    'matches a minor typo in a %s', (_field, metadata, query) => {
      const store = useToolRegistryStore()
      store.tools = [catalogTool(metadata)]

      expect(store.searchTools(query)).toEqual(store.tools)
    },
  )

  it('preserves partial matching, all query tokens, original references and catalog order', () => {
    const store = useToolRegistryStore()
    store.tools = [
      catalogTool({ name: 'Second', display_name: 'Gaussian Measure', tags: ['image'], categories: ['Denoising'] }),
      catalogTool({ name: 'First', display_name: 'Gaussian Blur', tags: ['image'], categories: ['Denoising'] }),
      catalogTool({ name: 'Third', display_name: 'Gaussian Blur', tags: ['table'], categories: ['Statistics'] }),
    ]

    expect(store.searchTools(' GAUSS  IMAGE denois ')).toEqual(store.tools.slice(0, 2))
    expect(store.searchTools('gausian imgae')).toEqual(store.tools.slice(0, 2))
    expect(store.searchTools('gauss image')[0]).toBe(store.tools[0])
    expect(store.searchTools('gauss image')[1]).toBe(store.tools[1])
    expect(store.searchTools('gauss missing')).toEqual([])
    expect(store.searchTools('')).toBe(store.tools)
    expect(store.searchTools('   ')).toEqual(store.tools)
  })

  it('keeps short queries exact and refuses unrelated or multiple-edit terms', () => {
    const store = useToolRegistryStore()
    store.tools = [catalogTool({ name: 'Cat', display_name: 'Cat' }), catalogTool()]

    expect(store.searchTools('cat')).toEqual([store.tools[0]])
    expect(store.searchTools('cot')).toEqual([])
    expect(store.searchTools('custxx')).toEqual([])
    expect(store.searchTools('unrelated')).toEqual([])
  })

  it('bounds typo matching to 64 characters without limiting exact partial matches', () => {
    const store = useToolRegistryStore()
    const stem = 'x'.repeat(63)
    store.tools = [catalogTool({ name: 'LongIdentifier', display_name: `${stem}z ${stem}xz` })]

    expect(store.searchTools(`${stem}y`)).toEqual(store.tools)
    expect(store.searchTools(`${stem}xy`)).toEqual([])
    expect(store.searchTools(`${stem}xz`)).toEqual(store.tools)
  })

  it('derives search terms from reactive metadata changes, replacements, reloads and removal', () => {
    const store = useToolRegistryStore()
    store.tools = [catalogTool()]
    expect(store.searchTools('custm')).toEqual(store.tools)

    store.tools[0]!.name = 'RenamedMolecules'
    store.tools[0]!.display_name = 'Renamed Molecules'
    expect(store.searchTools('custm')).toEqual([])
    expect(store.searchTools('moleculs')).toEqual(store.tools)

    store.applyToolReload({
      type: 'tool_reload', tool_name: 'RenamedMolecules',
      tool_metadata: catalogTool({ name: 'RenamedMolecules', display_name: 'Fluorescence Detector' }),
    })
    expect(store.searchTools('fluorescense')).toEqual(store.tools)
    store.applyToolRemoved({ type: 'tool_removed', tool_name: 'RenamedMolecules' })
    expect(store.searchTools('fluorescense')).toEqual([])

    store.tools = [catalogTool({ name: 'Replacement', display_name: 'Gaussian' })]
    expect(store.searchTools('gausian')).toEqual(store.tools)
    expect(store.searchTools('custm')).toEqual([])
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

  it('tracks a package install until refreshed read models are available', async () => {
    let resolveInstall: (value: unknown) => void = () => {}
    mockedApi.post.mockImplementationOnce(
      () => new Promise((resolve) => {
        resolveInstall = resolve
      }),
    )
    const store = useToolRegistryStore()

    const pending = store.installPackageVersion('common', '1.2.3')

    expect(store.isPackageVersionInstalling('common', '1.2.3')).toBe(true)
    expect(store.isPackageInstalling('common')).toBe(true)
    resolveInstall({ data: { status: 'installed' } })
    await pending

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/api/v1/tools/packages/common/install',
      { version: '1.2.3' },
    )
    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools')
    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools/packages')
    expect(store.isPackageVersionInstalling('common', '1.2.3')).toBe(false)
  })

  it('clears package install state and propagates failures', async () => {
    mockedApi.post.mockRejectedValueOnce(new Error('install failed'))
    const store = useToolRegistryStore()

    await expect(store.installPackageVersion('common', '1.2.3')).rejects.toThrow(
      'install failed',
    )

    expect(store.error).toBe('install failed')
    expect(store.isPackageInstalling('common')).toBe(false)
  })

  it('applyToolReload upserts tools and package membership', () => {
    const store = useToolRegistryStore()
    store.packages = [{
      name: '__custom__',
      installed_versions: ['local'],
      available_versions: ['local'],
      active_version: 'local',
      tools: { local: [] },
      load_errors: {},
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
        accepts_upstream: true,
        dynamic_outputs: false,
        dataframe_output: false,
        row_consumption: 'mapped',
        documentation: '',
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
      accepts_upstream: true,
      dynamic_outputs: false,
      dataframe_output: false,
      row_consumption: 'mapped',
      documentation: '',
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
      load_errors: {},
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
