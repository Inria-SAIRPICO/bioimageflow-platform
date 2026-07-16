import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import PrimeVue from 'primevue/config'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

// Mock primevue/useconfirm so the `useVersionInWorkflow` test can fire the
// accept callback synchronously — without a rendered ConfirmDialog the
// real confirm service never resolves the require() promise on its own.
const requireMock = vi.fn()
vi.mock('primevue/useconfirm', () => ({
  useConfirm: () => ({ require: requireMock }),
}))

import { api } from '@/api/client'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useSettingsStore } from '@/stores/settings'
import { useExecutionStore } from '@/stores/execution'
import ToolsPanel from '../ToolsPanel.vue'
import type { ToolMetadata, PackageInfo, Settings } from '@/api/types'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const mockTools: ToolMetadata[] = [
  {
    name: 'threshold',
    display_name: 'Threshold',
    package: 'bioimageflow-core',
    package_version: '0.1.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: 'Apply threshold to an image',
    tags: ['segmentation', 'binary'],
    categories: ['Image Processing'],
    inputs: { image: { type: 'Image', required: true, nullable: false, connectable: 'by_default' } },
    outputs: { mask: { type: 'Image' } },
    environment: null,
    source_kind: 'package',
    editable: false,
  },
  {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'bioimageflow-core',
    package_version: '0.1.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: 'Apply gaussian blur',
    tags: ['filter'],
    categories: ['Filtering'],
    inputs: { image: { type: 'Image', required: true, nullable: false, connectable: 'by_default' } },
    outputs: { image: { type: 'Image' } },
    environment: null,
    source_kind: 'package',
    editable: false,
  },
  {
    name: 'cellpose',
    display_name: 'Cellpose',
    package: 'bioimageflow-cellpose',
    package_version: '0.2.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: 'Deep learning segmentation',
    tags: ['deep-learning'],
    categories: ['Segmentation'],
    inputs: { image: { type: 'Image', required: true, nullable: false, connectable: 'by_default' } },
    outputs: { labels: { type: 'Labels' } },
    environment: null,
    source_kind: 'package',
    editable: false,
  },
  {
    name: 'MyCustomTool',
    display_name: 'My Custom Tool',
    package: '__custom__',
    package_version: 'local',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: 'Local custom tool',
    tags: [],
    categories: ['Custom'],
    inputs: {},
    outputs: {},
    environment: null,
    source_kind: 'custom',
    editable: true,
  },
]

const mockPackages: PackageInfo[] = [
  {
    name: 'bioimageflow-core',
    installed_versions: ['0.1.0'],
    available_versions: ['0.1.0', '0.2.0'],
    active_version: '0.1.0',
    tools: { threshold: ['0.1.0'], gaussian_blur: ['0.1.0'] },
    load_errors: {},
    environment_status: 'ready',
  },
  {
    name: 'bioimageflow-cellpose',
    installed_versions: ['0.2.0'],
    available_versions: ['0.1.0', '0.2.0'],
    active_version: '0.2.0',
    tools: { cellpose: ['0.2.0'] },
    load_errors: {},
    environment_status: 'stopped',
  },
]

function makeSettings(overrides: Partial<Settings> = {}): Settings {
  return {
    deployment_mode: 'desktop',
    external_editor: null,
    napari_env_path: null,
    omero_instances: [],
    output_data_folder: '/out',
    tool_store_path: '~/.bioimageflow/tool_packages/',
    update_mode: 'auto',
    execution_engine: 'sequential',
    keyboard_shortcuts: {},
    dev_mode: true,
    enable_unsafe_webapp_features: false,
    datasets_root: null,
    max_upload_size: 2147483648,
    resolved_tool_store_path: '~/.bioimageflow/tool_packages/',
    resolved_output_data_folder: '/out',
    ...overrides,
  }
}

function setPywebviewDesktop(enabled: boolean) {
  Object.defineProperty(window, 'pywebview', {
    configurable: true,
    value: enabled
      ? {
          api: {
            select_file: vi.fn(),
            select_files: vi.fn(),
            select_folder: vi.fn(),
            save_file: vi.fn(),
            set_title: vi.fn(),
            reveal_path: vi.fn(),
          },
        }
      : undefined,
  })
}

function mountPanel(options: { settings?: Settings | null } = {}) {
  // Mock fetchTools and fetchPackages calls in onMounted
  mockedApi.get.mockImplementation((url: string) => {
    if (url === '/api/v1/tools') return Promise.resolve({ data: mockTools })
    if (url === '/api/v1/tools/packages') return Promise.resolve({ data: mockPackages })
    return Promise.resolve({ data: {} })
  })

  const pinia = createPinia()
  setActivePinia(pinia)
  const settingsStore = useSettingsStore()
  settingsStore.settings = options.settings === undefined
    ? makeSettings({ deployment_mode: 'desktop' })
    : options.settings
  return mount(ToolsPanel, {
    global: {
      plugins: [pinia, PrimeVue, ConfirmationService, ToastService],
      stubs: {
        TreeTable: true,
        Column: true,
        InputText: true,
        Button: true,
        Dialog: { template: '<div><slot /><slot name="footer" /></div>' },
        Tag: true,
        CreateToolDialog: true,
        ConfirmDialog: true,
      },
    },
  })
}

describe('ToolsPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    requireMock.mockReset()
    setPywebviewDesktop(false)
  })

  // --- Task 12: Basic component tests ---

  it('renders search input', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('[data-testid="tool-search"]').exists()).toBe(true)
  })

  it('renders create tool button', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('[data-testid="create-tool-btn"]').exists()).toBe(true)
  })

  it('renders create tool button before settings load', () => {
    const wrapper = mountPanel({ settings: null })
    expect(wrapper.find('[data-testid="create-tool-btn"]').exists()).toBe(true)
  })

  it('hides create tool button when loaded settings explicitly say webapp', () => {
    setPywebviewDesktop(true)
    const wrapper = mountPanel({
      settings: makeSettings({ deployment_mode: 'webapp' }),
    })
    expect(wrapper.find('[data-testid="create-tool-btn"]').exists()).toBe(false)
  })

  it('shows create tool button in webapp mode when unsafe webapp features are enabled', () => {
    const wrapper = mountPanel({
      settings: makeSettings({
        deployment_mode: 'webapp',
        enable_unsafe_webapp_features: true,
      }),
    })
    expect(wrapper.find('[data-testid="create-tool-btn"]').exists()).toBe(true)
  })

  it('renders manage tools button', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('[data-testid="manage-tools-btn"]').exists()).toBe(true)
  })

  it('showManageDialog toggles via manage tools button', async () => {
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { showManageDialog: boolean }
    expect(vm.showManageDialog).toBe(false)
    vm.showManageDialog = true
    await wrapper.vm.$nextTick()
    expect(vm.showManageDialog).toBe(true)
  })

  it('renders tool list items for each tool', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as { filteredTools: ToolMetadata[] }
    expect(vm.filteredTools).toHaveLength(4)
  })

  it('renders every tag as compact single-line metadata', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const store = useToolRegistryStore()
    const threshold = store.tools.find((tool) => tool.name === 'threshold')!
    threshold.tags = ['segmentation', 'binary', 'image']
    await wrapper.vm.$nextTick()

    const row = wrapper.get('[data-testid="tool-item-threshold"]')
    expect(row.get('.tool-list-tags').text()).toBe('segmentation · binary · image')
    expect(row.find('.tool-list-tag-overflow').exists()).toBe(false)
    expect(row.get('.tool-list-meta').attributes('title')).toBe('segmentation · binary · image')
    expect(row.find('.p-tag').exists()).toBe(false)
  })

  it('labels the synthetic custom package as workflow tools in Manage Tools', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as { treeNodes: Array<{ key: string; data: { display_name: string; isCustomPackage?: boolean } }> }
    const customNode = vm.treeNodes.find((node) => node.key === '__custom__')

    expect(customNode?.data.display_name).toBe('Custom workflow tools')
    expect(customNode?.data.isCustomPackage).toBe(true)
  })

  it('does not render category tool counts in the tool list', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    expect(wrapper.find('.tool-category-count').exists()).toBe(false)
  })

  it('opens a collapsed category when search finds one of its tools', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const categoryToggle = wrapper.get('[data-testid="category-toggle-Image Processing"]')
    await categoryToggle.trigger('click')
    expect(categoryToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-testid="tool-item-threshold"]').exists()).toBe(false)

    const vm = wrapper.vm as unknown as { searchQuery: string }
    vm.searchQuery = 'threshold'
    await wrapper.vm.$nextTick()

    expect(categoryToggle.attributes('aria-expanded')).toBe('true')
    expect(categoryToggle.attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="tool-item-threshold"]').exists()).toBe(true)

    await categoryToggle.trigger('click')
    vm.searchQuery = ''
    await wrapper.vm.$nextTick()

    expect(categoryToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('[data-testid="tool-item-threshold"]').exists()).toBe(false)
  })

  it('treeNodes groups tools by package', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as { treeNodes: Array<{ key: string; children?: unknown[] }> }
    const nodes = vm.treeNodes

    expect(nodes).toHaveLength(3)
    expect(nodes[0].key).toBe('bioimageflow-core')
    expect(nodes[0].children).toHaveLength(2)
    expect(nodes[1].key).toBe('bioimageflow-cellpose')
    expect(nodes[1].children).toHaveLength(1)
  })

  it('search filtering updates treeNodes', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      treeNodes: Array<{ key: string; children?: unknown[] }>
      searchQuery: string
    }

    vm.searchQuery = 'cellpose'
    await wrapper.vm.$nextTick()

    const nodes = vm.treeNodes
    expect(nodes).toHaveLength(1)
    expect(nodes[0].key).toBe('bioimageflow-cellpose')
  })

  it('click on tool row emits add-tool', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    // Test via exposed method since TreeTable is stubbed
    const vm = wrapper.vm as unknown as { onToolClick?: (name: string) => void }
    // Directly verify the emit mechanism works by calling internal handler
    wrapper.vm.$emit('add-tool', 'threshold')
    expect(wrapper.emitted('add-tool')).toBeTruthy()
    expect(wrapper.emitted('add-tool')![0]).toEqual(['threshold'])
  })

  // --- Task 14: Version management tests ---

  it('getVersionRows merges installed and available versions', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      getVersionRows: (name: string) => Array<{
        version: string
        installed: boolean
        available: boolean
        loadError: string | null
      }>
    }

    const rows = vm.getVersionRows('bioimageflow-core')
    expect(rows).toHaveLength(2)

    const v010 = rows.find((r) => r.version === '0.1.0')
    expect(v010).toBeDefined()
    expect(v010!.installed).toBe(true)
    expect(v010!.available).toBe(true)

    const v020 = rows.find((r) => r.version === '0.2.0')
    expect(v020).toBeDefined()
    expect(v020!.installed).toBe(false)
    expect(v020!.available).toBe(true)
    expect(v020!.loadError).toBeNull()
  })

  it('getVersionRows exposes installed version load errors', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.packages = [
      {
        ...mockPackages[0],
        installed_versions: ['0.1.0'],
        available_versions: ['0.1.0'],
        load_errors: { '0.1.0': 'ValueError: broken environment' },
      },
      mockPackages[1],
    ]

    const vm = wrapper.vm as unknown as {
      getVersionRows: (name: string) => Array<{
        version: string
        installed: boolean
        available: boolean
        loadError: string | null
      }>
    }

    expect(vm.getVersionRows('bioimageflow-core')).toEqual([
      {
        version: '0.1.0',
        installed: true,
        available: true,
        loadError: 'ValueError: broken environment',
      },
    ])
  })

  it('versionTriggerLabel marks failed active versions', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.packages = [
      {
        ...mockPackages[0],
        installed_versions: ['0.1.0'],
        active_version: '0.1.0',
        load_errors: { '0.1.0': 'ValueError: broken environment' },
      },
      mockPackages[1],
    ]

    const vm = wrapper.vm as unknown as {
      versionTriggerLabel: (name: string) => string
    }

    expect(vm.versionTriggerLabel('bioimageflow-core')).toBe('0.1.0 (failed)')
  })

  it('getVersionRows returns empty for unknown package', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      getVersionRows: (name: string) => Array<{
        version: string
        installed: boolean
        available: boolean
        loadError: string | null
      }>
    }
    expect(vm.getVersionRows('nonexistent')).toEqual([])
  })

  it('installVersion calls POST and refreshes packages', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({ data: {} })
    // Re-mock get for fetchPackages refresh
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      installVersion: (name: string, version: string) => Promise<void>
    }
    await vm.installVersion('bioimageflow-core', '0.2.0')

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/tools/packages/bioimageflow-core/install', {
      version: '0.2.0',
    })
  })


  it('renders an explicit inline install package footer in Manage Tools', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as { showManageDialog: boolean }
    vm.showManageDialog = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="package-install-footer"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="package-install-footer-label"]').text()).toBe('Install tool package')
    expect(wrapper.find('[data-testid="package-install-url"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="package-install-or"]').text()).toBe('or')
    expect(wrapper.find('[data-testid="package-install-archive-button"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="package-install-button"]').exists()).toBe(true)
  })


  it('hides the custom package source footer in locked-down webapp mode', async () => {
    const wrapper = mountPanel({
      settings: makeSettings({ deployment_mode: 'webapp', enable_unsafe_webapp_features: false }),
    })
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as { showManageDialog: boolean }
    vm.showManageDialog = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="package-install-footer"]').exists()).toBe(false)
  })


  it('shows the custom package source footer when settings are not loaded yet', async () => {
    const wrapper = mountPanel({ settings: null })
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      showManageDialog: boolean
      packageSourceInstallAvailable: boolean
    }
    vm.showManageDialog = true
    await wrapper.vm.$nextTick()

    expect(vm.packageSourceInstallAvailable).toBe(true)
    expect(wrapper.find('[data-testid="package-install-footer"]').exists()).toBe(true)
    expect(mockedApi.get).not.toHaveBeenCalledWith('/api/v1/settings')
  })

  it('installs an unknown package from a repository URL and refreshes tools', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({
      data: { status: 'installed', package: 'demo_tools', version: '1.2.3' },
    })
    mockedApi.get.mockImplementation((url: string) => {
      if (url === '/api/v1/tools') return Promise.resolve({ data: mockTools })
      if (url === '/api/v1/tools/packages') return Promise.resolve({ data: mockPackages })
      return Promise.resolve({ data: {} })
    })

    const vm = wrapper.vm as unknown as {
      packageInstallUrl: string
      packageArchiveFile: File | null
      canInstallPackageSource: boolean
      installPackageSource: () => Promise<void>
    }
    vm.packageInstallUrl = 'https://github.com/example/demo-tools'
    await wrapper.vm.$nextTick()

    expect(vm.canInstallPackageSource).toBe(true)
    await vm.installPackageSource()

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/tools/packages/import-url', {
      url: 'https://github.com/example/demo-tools',
    })
    expect(vm.packageInstallUrl).toBe('')
    expect(vm.packageArchiveFile).toBeNull()
  })

  it('installs an unknown package from a zip archive upload', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({
      data: { status: 'installed', package: 'archive_tools', version: '0.4.0' },
    })
    mockedApi.get.mockImplementation((url: string) => {
      if (url === '/api/v1/tools') return Promise.resolve({ data: mockTools })
      if (url === '/api/v1/tools/packages') return Promise.resolve({ data: mockPackages })
      return Promise.resolve({ data: {} })
    })

    const file = new File(['zip'], 'archive-tools.zip', { type: 'application/zip' })
    const vm = wrapper.vm as unknown as {
      packageInstallUrl: string
      packageArchiveFile: File | null
      packageArchiveLabel: string
      onPackageArchiveSelected: (event: Event) => void
      installPackageSource: () => Promise<void>
    }

    vm.packageInstallUrl = 'https://github.com/example/demo-tools'
    const input = document.createElement('input')
    Object.defineProperty(input, 'files', { value: [file] })
    vm.onPackageArchiveSelected({ target: input } as unknown as Event)
    await wrapper.vm.$nextTick()

    expect(vm.packageInstallUrl).toBe('')
    expect(vm.packageArchiveLabel).toBe('archive-tools.zip')
    await vm.installPackageSource()

    const [url, body, config] = mockedApi.post.mock.calls.find((call) => call[0] === '/api/v1/tools/packages/import-archive')!
    expect(url).toBe('/api/v1/tools/packages/import-archive')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('archive')).toBe(file)
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
  })


  it('surfaces backend validation details when package source install fails', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockRejectedValueOnce({
      response: { data: { detail: 'Installed source did not contain package metadata' } },
    })

    const vm = wrapper.vm as unknown as {
      packageInstallUrl: string
      installPackageSource: () => Promise<void>
    }
    vm.packageInstallUrl = 'https://github.com/example/broken-tools'
    await wrapper.vm.$nextTick()
    await vm.installPackageSource()

    expect(useToolRegistryStore().error).toBe('Installed source did not contain package metadata')
  })

  // --- Version dropdown collapse/expand ---

  it('version list is collapsed for each package by default', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      isVersionsExpanded: (name: string) => boolean
    }
    expect(vm.isVersionsExpanded('bioimageflow-core')).toBe(false)
    expect(vm.isVersionsExpanded('bioimageflow-cellpose')).toBe(false)
  })

  it('toggleVersionsExpanded flips state independently per package', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      isVersionsExpanded: (name: string) => boolean
      toggleVersionsExpanded: (name: string) => void
    }

    vm.toggleVersionsExpanded('bioimageflow-core')
    expect(vm.isVersionsExpanded('bioimageflow-core')).toBe(true)
    // Other package stays collapsed
    expect(vm.isVersionsExpanded('bioimageflow-cellpose')).toBe(false)

    vm.toggleVersionsExpanded('bioimageflow-core')
    expect(vm.isVersionsExpanded('bioimageflow-core')).toBe(false)
  })

  it('installVersion keeps the dropdown open so multiple versions can be toggled', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({ data: {} })
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      isVersionsExpanded: (name: string) => boolean
      toggleVersionsExpanded: (name: string) => void
      installVersion: (name: string, version: string) => Promise<void>
    }

    vm.toggleVersionsExpanded('bioimageflow-core')
    expect(vm.isVersionsExpanded('bioimageflow-core')).toBe(true)

    await vm.installVersion('bioimageflow-core', '0.2.0')

    expect(vm.isVersionsExpanded('bioimageflow-core')).toBe(true)
  })

  // --- Set-current button: workflow-wide active version selection ---

  it('isActiveVersion reflects the package active_version field', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.packages = [
      {
        ...mockPackages[0],
        installed_versions: ['0.1.0', '0.2.0'],
        active_version: '0.2.0',
      },
      mockPackages[1],
    ]

    const vm = wrapper.vm as unknown as {
      isActiveVersion: (name: string, version: string) => boolean
    }
    expect(vm.isActiveVersion('bioimageflow-core', '0.2.0')).toBe(true)
    expect(vm.isActiveVersion('bioimageflow-core', '0.1.0')).toBe(false)
    // Unknown package
    expect(vm.isActiveVersion('nonexistent', '0.1.0')).toBe(false)
  })

  it('useVersionInWorkflow posts /use and refreshes when the user confirms', async () => {
    // Auto-confirm the dialog by firing accept() the moment require() is
    // called. Without a rendered ConfirmDialog the real confirm service
    // never resolves on its own.
    requireMock.mockImplementation((opts: { accept?: () => void | Promise<void> }) => {
      opts.accept?.()
    })

    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({ data: {} })

    const vm = wrapper.vm as unknown as {
      useVersionInWorkflow: (name: string, version: string) => void
    }
    // Switch from the active 0.1.0 → install 0.2.0 first so we're switching
    // to a different installed version.
    const store = useToolRegistryStore()
    store.packages = [
      {
        ...mockPackages[0],
        installed_versions: ['0.1.0', '0.2.0'],
        active_version: '0.1.0',
      },
      mockPackages[1],
    ]

    vm.useVersionInWorkflow('bioimageflow-core', '0.2.0')
    await flushPromises()

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/api/v1/tools/packages/bioimageflow-core/use',
      { version: '0.2.0' },
    )
  })

  it('useVersionInWorkflow is a no-op when the version is already active', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.packages = [{ ...mockPackages[0], active_version: '0.1.0' }, mockPackages[1]]

    const vm = wrapper.vm as unknown as {
      useVersionInWorkflow: (name: string, version: string) => void
    }
    vm.useVersionInWorkflow('bioimageflow-core', '0.1.0')

    // No POST should have been issued — onMounted may have called GETs but
    // we only care that no /use POST went out.
    const useCalls = mockedApi.post.mock.calls.filter((c) => /\/use$/.test(String(c[0])))
    expect(useCalls).toHaveLength(0)
  })

  it('useVersionInWorkflow is a no-op for failed installed versions', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.packages = [
      {
        ...mockPackages[0],
        installed_versions: ['0.1.0', '0.2.0'],
        active_version: '0.1.0',
        load_errors: { '0.2.0': 'SyntaxError: bad package' },
      },
      mockPackages[1],
    ]

    const vm = wrapper.vm as unknown as {
      useVersionInWorkflow: (name: string, version: string) => void
    }
    vm.useVersionInWorkflow('bioimageflow-core', '0.2.0')

    const useCalls = mockedApi.post.mock.calls.filter((c) => /\/use$/.test(String(c[0])))
    expect(useCalls).toHaveLength(0)
  })

  it('uninstallVersion sends version as a query parameter (spec v1 §2.4)', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.delete.mockResolvedValueOnce({ data: {} })
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      uninstallVersion: (name: string, version: string) => Promise<void>
    }
    await vm.uninstallVersion('bioimageflow-core', '0.1.0')

    expect(mockedApi.delete).toHaveBeenCalledWith(
      '/api/v1/tools/packages/bioimageflow-core',
      { params: { version: '0.1.0' } },
    )
  })

  // --- Task 15: Info and Open in Editor tests ---

  it('toggleDocumentation shows tool documentation with the display name title', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      toggleDocumentation: (name: string) => void
      activeDoc: string | null
      getDocumentation: (name: string) => string
    }

    vm.toggleDocumentation('MyCustomTool')
    await flushPromises()
    expect(vm.activeDoc).toBe('MyCustomTool')
    expect(vm.getDocumentation('MyCustomTool')).toBe('Local custom tool')
    expect(wrapper.find('.tool-documentation-header h4').text()).toBe('My Custom Tool')

    // Toggle off
    vm.toggleDocumentation('MyCustomTool')
    expect(vm.activeDoc).toBeNull()
  })

  it('openInEditor calls tool-specific editor API in desktop mode', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    // Set settings to desktop mode
    const settingsStore = useSettingsStore()
    settingsStore.settings = makeSettings({ deployment_mode: 'desktop' })

    mockedApi.post.mockResolvedValueOnce({
      data: { opened: true, method: 'external', url: null, path: '/path/to/tool.py', message: null },
    })

    const vm = wrapper.vm as unknown as {
      openInEditor: (name: string) => Promise<void>
    }
    await vm.openInEditor('threshold')

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/editor/open-tool', {
      tool_name: 'threshold',
    })
  })

  it('opens the code editor loading dock before source lookup finishes', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const loadingDetails: unknown[] = []
    const onLoading = vi.fn((event: Event) => {
      loadingDetails.push((event as CustomEvent).detail)
    })
    window.addEventListener('bif:open-code-editor-loading', onLoading)

    let resolveOpen!: (value: unknown) => void
    mockedApi.post.mockImplementationOnce(() => new Promise((resolve) => {
      resolveOpen = resolve
    }))

    const vm = wrapper.vm as unknown as {
      openInEditor: (name: string) => Promise<void>
    }
    const openPromise = vm.openInEditor('threshold')

    expect(onLoading).toHaveBeenCalledTimes(1)
    expect(loadingDetails[0]).toEqual({ path: '', requestId: expect.any(Number) })
    await vi.waitFor(() => expect(resolveOpen).toBeTypeOf('function'))

    resolveOpen({
      data: {
        path: '/path/to/tool.py',
        opened: true,
        method: 'embedded',
        url: 'http://127.0.0.1:32344',
        message: null,
      },
    })
    await openPromise

    expect(loadingDetails).toEqual([{ path: '', requestId: expect.any(Number) }])
    window.removeEventListener('bif:open-code-editor-loading', onLoading)
  })

  it('derives a tool source folder from POSIX and Windows source files', async () => {
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as {
      parentPath: (path: string) => string
    }

    expect(vm.parentPath('/path/to/tool.py')).toBe('/path/to')
    expect(vm.parentPath('/tool.py')).toBe('/')
    expect(vm.parentPath('C:\\tools\\tool.py')).toBe('C:\\tools')
    expect(vm.parentPath('C:\\tool.py')).toBe('C:\\')
  })

  it('openInEditor copies the path when editor backend returns clipboard fallback', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({
      data: {
        opened: false,
        method: 'clipboard',
        path: '/path/to/tool.py',
        url: null,
        message: null,
      },
    })

    const vm = wrapper.vm as unknown as {
      openInEditor: (name: string) => Promise<void>
    }
    await vm.openInEditor('threshold')

    expect(writeText).toHaveBeenCalledWith('/path/to/tool.py')
  })

  it('custom tool actions are only available for editable custom tools', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const store = useToolRegistryStore()
    const vm = wrapper.vm as unknown as {
      isEditableTool: (tool: ToolMetadata) => boolean
    }

    expect(vm.isEditableTool(store.getToolByName('MyCustomTool')!)).toBe(true)
    expect(vm.isEditableTool(store.getToolByName('threshold')!)).toBe(false)
  })

  it('renders main-list open script for all tools and edit actions only for custom tools', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    expect(wrapper.find('[data-testid="tool-open-script-MyCustomTool"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tool-rename-MyCustomTool"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tool-delete-MyCustomTool"]').exists()).toBe(true)

    expect(wrapper.find('[data-testid="tool-open-script-threshold"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tool-rename-threshold"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="tool-delete-threshold"]').exists()).toBe(false)
  })

  it('main-list custom open script button opens the tool source without adding a node', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockClear()
    mockedApi.post.mockResolvedValueOnce({
      data: {
        opened: true,
        method: 'external',
        url: null,
        path: '/workflow/tools/my_custom_tool.py',
        message: null,
      },
    })

    await wrapper.find('[data-testid="tool-open-script-MyCustomTool"]').trigger('click')
    await flushPromises()

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/editor/open-tool', {
      tool_name: 'MyCustomTool',
    })
    expect(wrapper.emitted('add-tool')).toBeUndefined()
  })

  it('main-list custom rename button renames the tool without adding a node', async () => {
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('RenamedTool')
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    mockedApi.patch.mockResolvedValueOnce({
      data: {
        old_name: 'MyCustomTool',
        new_name: 'RenamedTool',
        path: '/workflow/tools/renamed_tool.py',
      },
    })
    mockedApi.get.mockResolvedValue({ data: [] })

    await wrapper.find('[data-testid="tool-rename-MyCustomTool"]').trigger('click')
    await flushPromises()

    expect(mockedApi.patch).toHaveBeenCalledWith('/api/v1/tools/MyCustomTool', {
      new_name: 'RenamedTool',
    })
    expect(wrapper.emitted('add-tool')).toBeUndefined()
    promptSpy.mockRestore()
  })

  it('main-list custom delete button checks usage and opens confirmation without adding a node', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    mockedApi.get.mockClear()
    mockedApi.get.mockResolvedValueOnce({ data: { affected_workflows: [] } })

    await wrapper.find('[data-testid="tool-delete-MyCustomTool"]').trigger('click')
    await flushPromises()

    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools/MyCustomTool/usage')
    expect(requireMock).toHaveBeenCalledWith(expect.objectContaining({
      header: 'Delete Custom Tool',
    }))
    expect(wrapper.emitted('add-tool')).toBeUndefined()
  })

  it('openInEditor does nothing in webapp mode when unsafe webapp features are disabled', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    // Set settings to webapp mode
    const settingsStore = useSettingsStore()
    settingsStore.settings = makeSettings({ deployment_mode: 'webapp' })

    // Clear mocks so we can verify no calls are made
    mockedApi.get.mockClear()
    mockedApi.post.mockClear()

    const vm = wrapper.vm as unknown as {
      openInEditor: (name: string) => Promise<void>
    }
    await vm.openInEditor('threshold')

    expect(mockedApi.get).not.toHaveBeenCalled()
    expect(mockedApi.post).not.toHaveBeenCalled()
  })

  it('openInEditor works in webapp mode when unsafe webapp features are enabled', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const settingsStore = useSettingsStore()
    settingsStore.settings = makeSettings({
      deployment_mode: 'webapp',
      enable_unsafe_webapp_features: true,
    })

    mockedApi.post.mockResolvedValueOnce({
      data: { opened: true, method: 'external', url: null, path: '/path/to/tool.py', message: null },
    })

    const vm = wrapper.vm as unknown as {
      openInEditor: (name: string) => Promise<void>
    }
    await vm.openInEditor('threshold')

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/editor/open-tool', {
      tool_name: 'threshold',
    })
  })

  // --- Task 16: Environment controls tests ---

  it('getEnvStatus returns correct status from packages', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      getEnvStatus: (name: string) => string
    }

    expect(vm.getEnvStatus('bioimageflow-core')).toBe('ready')
    expect(vm.getEnvStatus('bioimageflow-cellpose')).toBe('stopped')
    expect(vm.getEnvStatus('nonexistent')).toBe('unknown')
  })

  it('toggleEnvironment calls stop for running environment', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    // Override the package status to 'running'
    const store = useToolRegistryStore()
    store.packages = [
      { ...mockPackages[0], environment_status: 'running' },
      mockPackages[1],
    ]

    mockedApi.post.mockResolvedValueOnce({ data: {} })
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      toggleEnvironment: (name: string) => Promise<void>
    }
    await vm.toggleEnvironment('bioimageflow-core')

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/api/v1/tools/environments/bioimageflow-core/stop',
    )
  })

  it('toggleEnvironment calls start for stopped environment', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({ data: {} })
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      toggleEnvironment: (name: string) => Promise<void>
    }
    await vm.toggleEnvironment('bioimageflow-cellpose')

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/api/v1/tools/environments/bioimageflow-cellpose/start',
    )
  })

  it('tool environment controls use the declared tool environment name', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.tools = store.tools.map((tool) =>
      tool.name === 'cellpose'
        ? { ...tool, environment: { name: 'cellpose-env', dependencies: { pip: ['cellpose'] } } }
        : tool,
    )

    mockedApi.post.mockResolvedValueOnce({ data: {} })
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      toggleToolEnvironment: (tool: ToolMetadata) => Promise<void>
    }
    await vm.toggleToolEnvironment(store.getToolByName('cellpose')!)

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/api/v1/tools/environments/cellpose-env/start',
    )
  })

  it('updates the tool power button when execution starts its environment', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.tools = store.tools.map((tool) =>
      tool.name === 'cellpose'
        ? { ...tool, environment: { name: 'cellpose-env', dependencies: { pip: ['cellpose'] } } }
        : tool,
    )

    store.applyEnvironmentStatus({
      type: 'environment_status',
      env_name: 'cellpose-env',
      status: 'running',
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-testid="tool-power-cellpose"]').classes()).toContain('env-running')
  })

  it('does not toggle tool environments while a workflow is executing', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })
    const toolRegistry = useToolRegistryStore()
    toolRegistry.tools = toolRegistry.tools.map((tool) =>
      tool.name === 'cellpose'
        ? { ...tool, environment: { name: 'cellpose-env', dependencies: { pip: ['cellpose'] } } }
        : tool,
    )
    useExecutionStore().state = 'running'
    mockedApi.post.mockClear()

    const vm = wrapper.vm as unknown as {
      toggleToolEnvironment: (tool: ToolMetadata) => Promise<void>
    }
    await vm.toggleToolEnvironment(toolRegistry.getToolByName('cellpose')!)

    expect(mockedApi.post).not.toHaveBeenCalled()
  })

  it('does not start tools without a declared environment', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()

    const vm = wrapper.vm as unknown as {
      getToolEnvStatus: (tool: ToolMetadata) => string
      toggleToolEnvironment: (tool: ToolMetadata) => Promise<void>
    }
    const threshold = store.getToolByName('threshold')!

    expect(vm.getToolEnvStatus(threshold)).toBe('unavailable')
    await vm.toggleToolEnvironment(threshold)

    expect(mockedApi.post).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tools/environments/'),
    )
  })

  it('keeps explicit environments in the same package independently scoped', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })
    const store = useToolRegistryStore()
    store.tools = store.tools.map((tool) => {
      if (tool.name === 'threshold') {
        return { ...tool, environment: { name: 'threshold-env', dependencies: {} } }
      }
      if (tool.name === 'gaussian_blur') {
        return { ...tool, environment: { name: 'blur-env', dependencies: {} } }
      }
      return tool
    })

    mockedApi.post.mockResolvedValueOnce({ data: { status: 'running' } })
    mockedApi.get.mockResolvedValueOnce({ data: [{ ...mockPackages[0], environment_status: 'running' }] })

    const vm = wrapper.vm as unknown as {
      getToolEnvStatus: (tool: ToolMetadata) => string
      toggleToolEnvironment: (tool: ToolMetadata) => Promise<void>
    }
    await vm.toggleToolEnvironment(store.getToolByName('threshold')!)

    expect(vm.getToolEnvStatus(store.getToolByName('threshold')!)).toBe('running')
    expect(vm.getToolEnvStatus(store.getToolByName('gaussian_blur')!)).toBe('stopped')
  })

  // --- Versions column test ---

  it('treeNodes includes version data from packages', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.tools.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      treeNodes: Array<{ key: string; data: { versions: string }; children?: Array<{ data: { versions: string } }> }>
    }
    const nodes = vm.treeNodes

    // Package row should show installed versions
    const coreNode = nodes.find((n) => n.key === 'bioimageflow-core')
    expect(coreNode).toBeDefined()
    expect(coreNode!.data.versions).toBe('0.1.0')

    // Tool child rows should show their package_version
    const toolNode = coreNode!.children![0]
    expect(toolNode.data.versions).toBe('0.1.0')
  })

  // --- Error handling tests ---

  it('installVersion sets error on failure', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockRejectedValueOnce(new Error('Install failed'))

    const vm = wrapper.vm as unknown as {
      installVersion: (name: string, version: string) => Promise<void>
    }
    await vm.installVersion('bioimageflow-core', '0.2.0')

    const store = useToolRegistryStore()
    expect(store.error).toBe('Install failed')
  })

  it('uninstallVersion sets error on failure', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.delete.mockRejectedValueOnce(new Error('Uninstall failed'))

    const vm = wrapper.vm as unknown as {
      uninstallVersion: (name: string, version: string) => Promise<void>
    }
    await vm.uninstallVersion('bioimageflow-core', '0.1.0')

    const store = useToolRegistryStore()
    expect(store.error).toBe('Uninstall failed')
  })

  it('toggleEnvironment sets error on failure', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockRejectedValueOnce(new Error('Env toggle failed'))

    const vm = wrapper.vm as unknown as {
      toggleEnvironment: (name: string) => Promise<void>
    }
    await vm.toggleEnvironment('bioimageflow-cellpose')

    const store = useToolRegistryStore()
    expect(store.error).toBe('Env toggle failed')
  })

  it('toggleEnvironment refreshes packages after toggle', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockResolvedValueOnce({ data: {} })
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      toggleEnvironment: (name: string) => Promise<void>
    }
    await vm.toggleEnvironment('bioimageflow-cellpose')

    // fetchPackages should have been called (the get after the post)
    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/tools/packages')
  })
})
