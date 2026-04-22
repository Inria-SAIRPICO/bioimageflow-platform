import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import PrimeVue from 'primevue/config'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import ToolsPanel from '../ToolsPanel.vue'
import type { PackageInfo } from '@/api/types'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const emptyStorePackages: PackageInfo[] = [
  {
    name: 'bioimageflow_common_tools',
    installed_versions: [],
    available_versions: ['0.1.1', '0.1.2'],
    tools: {},
    environment_status: 'stopped',
  },
]

function mountPanel() {
  mockedApi.get.mockImplementation((url: string) => {
    if (url === '/api/v1/tools') return Promise.resolve({ data: [] })
    if (url === '/api/v1/tools/packages') {
      return Promise.resolve({ data: emptyStorePackages })
    }
    return Promise.resolve({ data: {} })
  })

  const pinia = createPinia()
  return mount(ToolsPanel, {
    global: {
      plugins: [pinia, PrimeVue, ConfirmationService, ToastService],
      stubs: {
        TreeTable: true,
        Column: true,
        InputText: true,
        Button: true,
        Dialog: true,
        Tag: true,
        CreateToolDialog: true,
        ConfirmDialog: true,
      },
    },
  })
}

describe('ToolsPanel — empty tool store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows a known-but-not-installed package as a tree node with no tool children', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      treeNodes: Array<{ key: string; data: { versions: string }; children?: unknown[] }>
    }
    const nodes = vm.treeNodes
    expect(nodes).toHaveLength(1)
    expect(nodes[0].key).toBe('bioimageflow_common_tools')
    expect(nodes[0].children ?? []).toHaveLength(0)
  })

  it('getVersionRows exposes both available versions as not-installed', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    const vm = wrapper.vm as unknown as {
      getVersionRows: (name: string) => Array<{ version: string; installed: boolean; available: boolean }>
    }
    const rows = vm.getVersionRows('bioimageflow_common_tools')
    expect(rows).toHaveLength(2)
    for (const row of rows) {
      expect(row.installed).toBe(false)
      expect(row.available).toBe(true)
    }
  })
})
