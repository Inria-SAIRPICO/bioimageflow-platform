import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import type { ToolMetadata, PackageInfo } from '@/api/types'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const mockTools: ToolMetadata[] = [
  {
    name: 'threshold',
    display_name: 'Threshold',
    package: 'bioimageflow-core',
    package_version: '0.1.0',
    tool_type: 'ProcessingTool',
    documentation: 'Apply threshold',
    tags: ['segmentation', 'binary'],
    categories: ['Image Processing'],
    inputs: { image: { type: 'Image', required: true, connectable: 'by_default' } },
    outputs: { mask: { type: 'Image' } },
    environment: null,
  },
  {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'bioimageflow-core',
    package_version: '0.1.0',
    tool_type: 'ProcessingTool',
    documentation: 'Apply gaussian blur',
    tags: ['filter', 'smoothing'],
    categories: ['Filtering'],
    inputs: { image: { type: 'Image', required: true, connectable: 'by_default' } },
    outputs: { image: { type: 'Image' } },
    environment: null,
  },
  {
    name: 'cellpose',
    display_name: 'Cellpose Segmentation',
    package: 'bioimageflow-cellpose',
    package_version: '0.2.0',
    tool_type: 'ProcessingTool',
    documentation: 'Cellpose deep learning segmentation',
    tags: ['deep-learning', 'segmentation'],
    categories: ['Segmentation'],
    inputs: { image: { type: 'Image', required: true, connectable: 'by_default' } },
    outputs: { labels: { type: 'Labels' } },
    environment: null,
  },
]

const mockPackages: PackageInfo[] = [
  {
    name: 'bioimageflow-core',
    installed_versions: ['0.1.0'],
    available_versions: ['0.1.0', '0.2.0'],
    tools: { threshold: ['0.1.0'], gaussian_blur: ['0.1.0'] },
    environment_status: 'ready',
  },
  {
    name: 'bioimageflow-cellpose',
    installed_versions: ['0.2.0'],
    available_versions: ['0.1.0', '0.2.0'],
    tools: { cellpose: ['0.2.0'] },
    environment_status: 'ready',
  },
]

describe('toolRegistry store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts with empty tools and packages', () => {
    const store = useToolRegistryStore()
    expect(store.tools).toEqual([])
    expect(store.packages).toEqual([])
  })

  it('fetchTools populates tools from API', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools')
    expect(store.tools).toEqual(mockTools)
    expect(store.tools).toHaveLength(3)
  })

  it('fetchPackages populates packages from API', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const store = useToolRegistryStore()
    await store.fetchPackages()

    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools/packages')
    expect(store.packages).toEqual(mockPackages)
    expect(store.packages).toHaveLength(2)
  })

  it('getToolByName returns the correct tool', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    const tool = store.getToolByName('threshold')
    expect(tool).toBeDefined()
    expect(tool!.display_name).toBe('Threshold')
  })

  it('getToolByName returns undefined for unknown tool', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    expect(store.getToolByName('nonexistent')).toBeUndefined()
  })

  it('searchTools filters by name', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    const results = store.searchTools('threshold')
    expect(results).toHaveLength(1)
    expect(results[0].name).toBe('threshold')
  })

  it('searchTools filters by tag', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    const results = store.searchTools('segmentation')
    expect(results).toHaveLength(2)
    expect(results.map((t) => t.name)).toContain('threshold')
    expect(results.map((t) => t.name)).toContain('cellpose')
  })

  it('searchTools filters by category', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    const results = store.searchTools('Filtering')
    expect(results).toHaveLength(1)
    expect(results[0].name).toBe('gaussian_blur')
  })

  it('searchTools returns all tools for empty query', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    const results = store.searchTools('')
    expect(results).toHaveLength(3)
  })

  it('searchTools is case-insensitive', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockTools })

    const store = useToolRegistryStore()
    await store.fetchTools()

    const results = store.searchTools('THRESHOLD')
    expect(results).toHaveLength(1)
    expect(results[0].name).toBe('threshold')
  })

  it('fetchTools handles API errors gracefully', async () => {
    mockedApi.get.mockRejectedValueOnce(new Error('Network error'))

    const store = useToolRegistryStore()
    await store.fetchTools()

    expect(store.error).toBe('Network error')
    expect(store.tools).toEqual([])
  })

  it('fetchPackages handles API errors gracefully', async () => {
    mockedApi.get.mockRejectedValueOnce(new Error('Server error'))

    const store = useToolRegistryStore()
    await store.fetchPackages()

    expect(store.error).toBe('Server error')
    expect(store.packages).toEqual([])
  })

  describe('applyToolReload', () => {
    it('replaces an existing tool entry', async () => {
      mockedApi.get.mockResolvedValueOnce({ data: mockTools })
      const store = useToolRegistryStore()
      await store.fetchTools()

      const updated: ToolMetadata = {
        ...mockTools[0],
        documentation: 'Updated docs',
        inputs: { ...mockTools[0].inputs, sigma: { type: 'float', required: false, connectable: 'never' } },
      }
      store.applyToolReload({
        type: 'tool_reload',
        tool_name: 'threshold',
        tool_metadata: updated,
      })

      const after = store.getToolByName('threshold')
      expect(after).toBeDefined()
      expect(after!.documentation).toBe('Updated docs')
      expect(after!.inputs).toHaveProperty('sigma')
      // No duplicate entry.
      expect(store.tools.filter((t) => t.name === 'threshold')).toHaveLength(1)
    })

    it('adds a tool that was not previously in the registry', () => {
      const store = useToolRegistryStore()
      const newTool: ToolMetadata = {
        ...mockTools[0],
        name: 'brand_new',
        display_name: 'Brand New',
      }
      store.applyToolReload({
        type: 'tool_reload',
        tool_name: 'brand_new',
        tool_metadata: newTool,
      })
      expect(store.getToolByName('brand_new')).toBeDefined()
      expect(store.tools).toHaveLength(1)
    })

    it('does not duplicate when called multiple times for the same tool', async () => {
      mockedApi.get.mockResolvedValueOnce({ data: mockTools })
      const store = useToolRegistryStore()
      await store.fetchTools()

      for (let i = 0; i < 3; i++) {
        store.applyToolReload({
          type: 'tool_reload',
          tool_name: 'threshold',
          tool_metadata: mockTools[0],
        })
      }
      expect(store.tools.filter((t) => t.name === 'threshold')).toHaveLength(1)
    })

    it('updates the tool entry in PackageInfo.tools[version]', async () => {
      mockedApi.get.mockResolvedValueOnce({ data: mockPackages })
      const store = useToolRegistryStore()
      await store.fetchPackages()

      // Add a new tool that the package doesn't yet know about.
      const newTool: ToolMetadata = {
        ...mockTools[0],
        name: 'newly_added',
        package: 'bioimageflow-core',
        package_version: '0.1.0',
      }
      store.applyToolReload({
        type: 'tool_reload',
        tool_name: 'newly_added',
        tool_metadata: newTool,
      })

      const pkg = store.packages.find((p) => p.name === 'bioimageflow-core')
      expect(pkg).toBeDefined()
      expect(pkg!.tools['0.1.0']).toContain('newly_added')
    })
  })

  describe('applyToolRemoved', () => {
    it('removes the tool from the registry', async () => {
      mockedApi.get.mockResolvedValueOnce({ data: mockTools })
      const store = useToolRegistryStore()
      await store.fetchTools()

      store.applyToolRemoved({ type: 'tool_removed', tool_name: 'threshold' })
      expect(store.getToolByName('threshold')).toBeUndefined()
      expect(store.tools).toHaveLength(2)
    })

    it('is a no-op when the tool is not present', () => {
      const store = useToolRegistryStore()
      store.applyToolRemoved({ type: 'tool_removed', tool_name: 'ghost' })
      expect(store.tools).toEqual([])
    })

    it('drops the tool from PackageInfo.tools[version]', async () => {
      mockedApi.get.mockResolvedValueOnce({ data: mockPackages })
      const store = useToolRegistryStore()
      await store.fetchPackages()

      // First add the tool to the registry so we have something to remove.
      const t: ToolMetadata = {
        ...mockTools[0],
        name: 'temp_tool',
        package: 'bioimageflow-core',
        package_version: '0.1.0',
      }
      store.applyToolReload({
        type: 'tool_reload',
        tool_name: 'temp_tool',
        tool_metadata: t,
      })
      let pkg = store.packages.find((p) => p.name === 'bioimageflow-core')
      expect(pkg!.tools['0.1.0']).toContain('temp_tool')

      store.applyToolRemoved({ type: 'tool_removed', tool_name: 'temp_tool' })

      pkg = store.packages.find((p) => p.name === 'bioimageflow-core')
      expect(pkg!.tools['0.1.0']).not.toContain('temp_tool')
    })
  })

  describe('reactivity', () => {
    it('applyToolReload triggers a watcher on tools', async () => {
      const { watch, nextTick } = await import('vue')
      const store = useToolRegistryStore()
      const fired: number[] = []
      watch(
        () => store.tools.length,
        (n) => fired.push(n),
      )

      store.applyToolReload({
        type: 'tool_reload',
        tool_name: 'gauss',
        tool_metadata: { ...mockTools[0], name: 'gauss' },
      })
      await nextTick()
      expect(fired).toEqual([1])
    })

    it('applyToolRemoved triggers a watcher on tools', async () => {
      const { watch, nextTick } = await import('vue')
      const store = useToolRegistryStore()
      store.applyToolReload({
        type: 'tool_reload',
        tool_name: 'gauss',
        tool_metadata: { ...mockTools[0], name: 'gauss' },
      })
      await nextTick()

      const fired: number[] = []
      watch(
        () => store.tools.length,
        (n) => fired.push(n),
      )
      store.applyToolRemoved({ type: 'tool_removed', tool_name: 'gauss' })
      await nextTick()
      expect(fired).toEqual([0])
    })
  })
})
