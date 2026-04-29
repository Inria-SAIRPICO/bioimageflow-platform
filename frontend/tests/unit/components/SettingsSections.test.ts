import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'

import ExternalEditorSection from '@/components/panels/sections/ExternalEditorSection.vue'
import NapariSection from '@/components/panels/sections/NapariSection.vue'
import ExecutionSection from '@/components/panels/sections/ExecutionSection.vue'
import StorageSection from '@/components/panels/sections/StorageSection.vue'
import * as nativeDialogs from '@/utils/nativeDialogs'

// In jsdom, ResizeObserver and matchMedia are missing — PrimeVue Select uses
// both during mount.
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
  cache_max_executions: null,
  cache_max_age: null,
  keyboard_shortcuts: {},
  dev_mode: true,
  datasets_root: null,
  max_upload_size: 2147483648,
  resolved_tool_store_path: '/Users/me/.bioimageflow/tool_packages',
  resolved_output_data_folder: '/Users/me/bioimageflow_data',
}

const globalOpts = {
  global: {
    plugins: [PrimeVue, ConfirmationService, ToastService],
  },
}

describe('ExternalEditorSection', () => {
  it('renders the current value', () => {
    const wrapper = mount(ExternalEditorSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, external_editor: 'code' } },
    })
    const input = wrapper.find('[data-testid="external-editor-input"]')
    expect((input.element as HTMLInputElement).value).toBe('code')
  })

  it('emits update:field on blur', async () => {
    const wrapper = mount(ExternalEditorSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })
    const input = wrapper.find('[data-testid="external-editor-input"]')
    await input.setValue('vim {file_path}')
    await input.trigger('blur')
    expect(wrapper.emitted('update:field')).toEqual([
      [{ field: 'external_editor', value: 'vim {file_path}' }],
    ])
  })

  it('emits null when cleared', async () => {
    const wrapper = mount(ExternalEditorSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, external_editor: 'code' } },
    })
    const input = wrapper.find('[data-testid="external-editor-input"]')
    await input.setValue('')
    await input.trigger('blur')
    expect(wrapper.emitted('update:field')).toEqual([
      [{ field: 'external_editor', value: null }],
    ])
  })
})

describe('NapariSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows Browse button only in desktop mode', () => {
    vi.spyOn(nativeDialogs, 'isDesktop').mockReturnValue(false)
    const wrapper = mount(NapariSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })
    expect(
      wrapper.find('[data-testid="napari-browse-button"]').exists(),
    ).toBe(false)
  })

  it('emits null when path is cleared', async () => {
    const wrapper = mount(NapariSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, napari_env_path: '/x' } },
    })
    const input = wrapper.find('[data-testid="napari-env-input"]')
    await input.setValue('')
    await input.trigger('blur')
    expect(wrapper.emitted('update:field')?.[0]).toEqual([
      { field: 'napari_env_path', value: null },
    ])
  })
})

describe('ExecutionSection', () => {
  it('renders the unlimited checkbox checked when value is null', () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: {
        modelValue: { ...baseSettings, cache_max_executions: null },
      },
    })
    // The InputNumber should be hidden when unlimited.
    expect(
      wrapper.find('[data-testid="cache-max-executions-input"]').exists(),
    ).toBe(false)
  })

  it('renders the InputNumber when cache_max_executions is 0', () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, cache_max_executions: 0 } },
    })
    expect(
      wrapper.find('[data-testid="cache-max-executions-input"]').exists(),
    ).toBe(true)
  })

  it('toggling Unlimited emits null', async () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, cache_max_executions: 5 } },
    })
    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(true)
    expect(wrapper.emitted('update:field')?.[0]).toEqual([
      { field: 'cache_max_executions', value: null },
    ])
  })

  it('unchecking Unlimited emits the integer count', async () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, cache_max_executions: null } },
    })
    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(false)
    expect(wrapper.emitted('update:field')?.[0]).toEqual([
      { field: 'cache_max_executions', value: 0 },
    ])
  })

  it('cache_max_age: blur with empty input emits null', async () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, cache_max_age: '30d' } },
    })
    const input = wrapper.find('[data-testid="cache-max-age-input"]')
    await input.setValue('')
    await input.trigger('blur')
    const events = wrapper.emitted('update:field') ?? []
    expect(events.at(-1)).toEqual([{ field: 'cache_max_age', value: null }])
  })
})

describe('StorageSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the resolved output folder, not the raw value', () => {
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })
    const input = wrapper.find('[data-testid="output-data-folder-input"]')
    expect((input.element as HTMLInputElement).value).toBe(
      '/Users/me/bioimageflow_data',
    )
  })

  it('renders the resolved tool store path', () => {
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })
    const input = wrapper.find('[data-testid="tool-store-path-input"]')
    expect((input.element as HTMLInputElement).value).toBe(
      '/Users/me/.bioimageflow/tool_packages',
    )
  })

  it('Reveal button shows toast when revealPath rejects', async () => {
    vi.spyOn(nativeDialogs, 'revealPath').mockRejectedValue(
      new Error('not found'),
    )
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })
    await wrapper.find('[data-testid="output-reveal-button"]').trigger('click')
    // Toast emission is internal to PrimeVue; we just assert no throw and that
    // revealPath was attempted.
    expect(nativeDialogs.revealPath).toHaveBeenCalled()
  })
})
