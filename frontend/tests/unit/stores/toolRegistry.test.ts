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
    inputs: { image: { type: 'Image', connectable: true } },
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
    inputs: { image: { type: 'Image', connectable: true } },
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
    inputs: { image: { type: 'Image', connectable: true } },
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
})
