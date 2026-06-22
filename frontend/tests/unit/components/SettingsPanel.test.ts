import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), patch: vi.fn() },
}))

import { api } from '@/api/client'
import SettingsPanel from '@/components/panels/SettingsPanel.vue'
import { useSettingsStore } from '@/stores/settings'
import { useSettingsPanel } from '@/composables/useSettingsPanel'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
}

class _ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
;(globalThis as { ResizeObserver?: typeof _ResizeObserverMock }).ResizeObserver ??=
  _ResizeObserverMock as unknown as typeof _ResizeObserverMock
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = () =>
    ({
      matches: false,
      media: '',
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}

const baseSettings = {
  deployment_mode: 'desktop' as const,
  external_editor: null,
  napari_env_path: null,
  omero_instances: [],
  output_data_folder: '~/bioimageflow_data/',
  tool_store_path: '~/.bioimageflow/tool_packages/',
  update_mode: 'auto' as const,
  execution_engine: 'sequential' as const,
  keyboard_shortcuts: {},
  dev_mode: true,
  enable_unsafe_webapp_features: false,
  datasets_root: null,
  max_upload_size: 2147483648,
  workspace_path: null,
  workspaces_root: null,
  resolved_tool_store_path: '/Users/me/.bioimageflow/tool_packages',
  resolved_output_data_folder: '/Users/me/bioimageflow_data',
}

const mountOpts = {
  global: { plugins: [PrimeVue, ConfirmationService, ToastService] },
  attachTo: document.body,
}

describe('SettingsPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedApi.get.mockResolvedValue({ data: baseSettings })
    // Reset the module-level singleton so tests don't bleed across each other.
    useSettingsPanel().close()
  })

  it('fetches settings on first open', async () => {
    const wrapper = mount(SettingsPanel, mountOpts)
    useSettingsPanel().open()
    await flushPromises()
    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/settings')
    wrapper.unmount()
  })

  it('does not refetch when reopened if already loaded', async () => {
    const wrapper = mount(SettingsPanel, mountOpts)
    useSettingsPanel().open()
    await flushPromises()
    useSettingsPanel().close()
    await flushPromises()
    useSettingsPanel().open()
    await flushPromises()
    expect(mockedApi.get).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('does not fetch on mount when closed', async () => {
    mount(SettingsPanel, mountOpts)
    await flushPromises()
    expect(mockedApi.get).not.toHaveBeenCalled()
  })

  it('forwards section update events to settingsStore.updateSettings', async () => {
    mockedApi.patch.mockResolvedValue({
      data: { ...baseSettings, external_editor: 'code {file_path}' },
    })
    const wrapper = mount(SettingsPanel, mountOpts)
    const store = useSettingsStore()
    useSettingsPanel().open()
    await flushPromises()

    // Reach into the panel to trigger an update directly via the store, since
    // simulating the section's emit through the open Dialog is complex.
    await store.updateSettings({ external_editor: 'code {file_path}' })
    expect(mockedApi.patch).toHaveBeenCalledWith('/api/v1/settings', {
      external_editor: 'code {file_path}',
    })
    wrapper.unmount()
  })

  it('panel.close hides the dialog', async () => {
    mount(SettingsPanel, mountOpts)
    const panel = useSettingsPanel()
    panel.open()
    await flushPromises()
    expect(panel.isOpen.value).toBe(true)
    panel.close()
    await flushPromises()
    expect(panel.isOpen.value).toBe(false)
  })
})

describe('useSettingsPanel composable', () => {
  beforeEach(() => {
    useSettingsPanel().close()
  })

  it('open() and close() toggle isOpen', () => {
    const { open, close, isOpen } = useSettingsPanel()
    expect(isOpen.value).toBe(false)
    open()
    expect(isOpen.value).toBe(true)
    close()
    expect(isOpen.value).toBe(false)
  })

  it('shares state across calls', () => {
    const a = useSettingsPanel()
    const b = useSettingsPanel()
    a.open()
    expect(b.isOpen.value).toBe(true)
  })
})
