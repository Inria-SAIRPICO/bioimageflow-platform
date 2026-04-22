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

const mockPackages: PackageInfo[] = [
  {
    name: 'bioimageflow_common_tools',
    installed_versions: ['0.1.1'],
    available_versions: ['0.1.1', '0.1.2'],
    tools: { threshold: ['0.1.1'] },
    environment_status: 'ready',
  },
]

function mountPanel() {
  mockedApi.get.mockImplementation((url: string) => {
    if (url === '/api/v1/tools') return Promise.resolve({ data: [] })
    if (url === '/api/v1/tools/packages') return Promise.resolve({ data: mockPackages })
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

describe('ToolsPanel — busy state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('isBusy flips on during install and back off after resolve', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    let resolveInstall: (value: unknown) => void = () => {}
    mockedApi.post.mockImplementationOnce(
      () => new Promise((resolve) => {
        resolveInstall = resolve
      }),
    )
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      isBusy: (name: string, version: string) => boolean
      installVersion: (name: string, version: string) => Promise<void>
    }

    expect(vm.isBusy('bioimageflow_common_tools', '0.1.2')).toBe(false)
    const pending = vm.installVersion('bioimageflow_common_tools', '0.1.2')
    await wrapper.vm.$nextTick()
    expect(vm.isBusy('bioimageflow_common_tools', '0.1.2')).toBe(true)

    resolveInstall({ data: {} })
    await pending
    expect(vm.isBusy('bioimageflow_common_tools', '0.1.2')).toBe(false)
  })

  it('isBusy flips on during uninstall and back off after resolve', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    let resolveUninstall: (value: unknown) => void = () => {}
    mockedApi.delete.mockImplementationOnce(
      () => new Promise((resolve) => {
        resolveUninstall = resolve
      }),
    )
    mockedApi.get.mockResolvedValueOnce({ data: mockPackages })

    const vm = wrapper.vm as unknown as {
      isBusy: (name: string, version: string) => boolean
      uninstallVersion: (name: string, version: string) => Promise<void>
    }

    const pending = vm.uninstallVersion('bioimageflow_common_tools', '0.1.1')
    await wrapper.vm.$nextTick()
    expect(vm.isBusy('bioimageflow_common_tools', '0.1.1')).toBe(true)

    resolveUninstall({ data: {} })
    await pending
    expect(vm.isBusy('bioimageflow_common_tools', '0.1.1')).toBe(false)
  })

  it('isBusy resets after install failure and error is recorded', async () => {
    const wrapper = mountPanel()
    await vi.waitFor(() => {
      const store = useToolRegistryStore()
      expect(store.packages.length).toBeGreaterThan(0)
    })

    mockedApi.post.mockRejectedValueOnce(new Error('boom'))

    const vm = wrapper.vm as unknown as {
      isBusy: (name: string, version: string) => boolean
      installVersion: (name: string, version: string) => Promise<void>
    }
    await vm.installVersion('bioimageflow_common_tools', '0.1.2')

    expect(vm.isBusy('bioimageflow_common_tools', '0.1.2')).toBe(false)
    const store = useToolRegistryStore()
    expect(store.error).toBe('boom')
  })
})
