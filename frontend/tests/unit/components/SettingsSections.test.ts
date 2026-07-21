import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'

import ExternalEditorSection from '@/components/panels/sections/ExternalEditorSection.vue'
import NapariSection from '@/components/panels/sections/NapariSection.vue'
import ExecutionSection from '@/components/panels/sections/ExecutionSection.vue'
import StorageSection from '@/components/panels/sections/StorageSection.vue'
import * as nativeDialogs from '@/utils/nativeDialogs'
import * as workspaceApi from '@/api/workspace'

vi.mock('@/api/demoWorkflows', () => ({
  getDemoWorkflowsStatus: vi.fn().mockResolvedValue({
    bundle_version: 1,
    status: 'missing',
    workflows: [],
    can_install: true,
    can_remove: false,
  }),
  installDemoWorkflows: vi.fn(),
}))

vi.mock('@/api/workspace', () => ({
  getWorkspaceInfo: vi.fn().mockResolvedValue({
    workspace_path: '/Users/me/bif-workspace',
    workflows_root: '/Users/me/bif-workspace/workflows',
    tools_root: '/Users/me/bif-workspace/tools',
    outputs_root: '/Users/me/bif-workspace/outputs',
    deployment_mode: 'desktop',
    user_editable: true,
  }),
  revealFilesystemPath: vi.fn().mockResolvedValue(undefined),
}))

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
  keyboard_shortcuts: {},
  dev_mode: true,
  enable_unsafe_webapp_features: false,
  datasets_root: null,
  max_upload_size: 2147483648,
  workspace_path: '/Users/me/bif-workspace',
  workspaces_root: null,
  resolved_tool_store_path: '/Users/me/.bioimageflow/tool_packages',
  resolved_output_data_folder: '/Users/me/bioimageflow_data',
}

const pinia = createPinia()
setActivePinia(pinia)
const globalOpts = {
  global: {
    plugins: [pinia, PrimeVue, ConfirmationService, ToastService],
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
  it('summarizes direct/sequential execution without stale cache pruning controls', () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: {
        modelValue: {
          ...baseSettings,
          engine: 'direct',
          execution: 'sequential',
        },
      },
    })

    expect(wrapper.find('[data-testid="execution-backend-value"]').text()).toBe('Direct')
    expect(wrapper.find('[data-testid="execution-scheduling-value"]').text()).toBe('Sequential')
    expect(
      wrapper.find('[data-testid="cache-max-executions-input"]').exists(),
    ).toBe(false)
    expect(
      wrapper.find('[data-testid="cache-max-age-input"]').exists(),
    ).toBe(false)
    expect(wrapper.text()).not.toContain('Parsl')
    expect(wrapper.emitted('update:field')).toBeUndefined()
  })

  it('maps legacy parsl settings to parallel wording without advertising Parsl', () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, execution_engine: 'parsl' as 'parallel' } },
    })

    expect(wrapper.find('[data-testid="execution-scheduling-value"]').text()).toBe('Parallel')
    expect(wrapper.text()).not.toContain('Parsl')
  })

  it('maps current parallel scheduling setting to parallel wording', () => {
    const wrapper = mount(ExecutionSection, {
      ...globalOpts,
      props: { modelValue: { ...baseSettings, execution_engine: 'parallel' } },
    })

    expect(wrapper.find('[data-testid="execution-scheduling-value"]').text()).toBe('Parallel')
  })
})

describe('StorageSection', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.clearAllMocks()
  })

  it('renders the effective default workspace when no override is stored', async () => {
    vi.mocked(workspaceApi.getWorkspaceInfo).mockResolvedValueOnce({
      workspace_path: '/Users/me/BioImageFlow/workspace',
      workflows_root: '/Users/me/BioImageFlow/workspace/workflows',
      tools_root: '/Users/me/BioImageFlow/workspace/tools',
      outputs_root: '/Users/me/BioImageFlow/workspace/outputs',
      deployment_mode: 'desktop',
      user_editable: true,
    })
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: {
        modelValue: {
          ...baseSettings,
          workspace_path: null,
          workspaces_root: null,
        },
      },
    })

    await flushPromises()

    expect((wrapper.get('[data-testid="workspace-path-input"]').element as HTMLInputElement).value)
      .toBe('/Users/me/BioImageFlow/workspace')
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

  it('reveals the output folder through the backend', async () => {
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })
    await wrapper.find('[data-testid="output-reveal-button"]').trigger('click')
    await flushPromises()

    expect(workspaceApi.revealFilesystemPath).toHaveBeenCalledWith(
      '/Users/me/bioimageflow_data',
    )
  })

  it('reveals the effective workspace through the backend', async () => {
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })
    await flushPromises()
    await wrapper.get('[data-testid="workspace-path-reveal-button"]').trigger('click')
    await flushPromises()

    expect(workspaceApi.revealFilesystemPath).toHaveBeenCalledWith(
      '/Users/me/bif-workspace',
    )
  })

  it('lets desktop users pick a workspace path', async () => {
    vi.spyOn(nativeDialogs, 'isDesktop').mockReturnValue(true)
    vi.spyOn(nativeDialogs, 'selectFolder').mockResolvedValue('/chosen/workspace')
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: { modelValue: baseSettings },
    })

    await wrapper.find('[data-testid="workspace-path-change-button"]').trigger('click')

    expect(nativeDialogs.selectFolder).toHaveBeenCalledWith('Select workspace folder')
    expect(wrapper.emitted('update:field')?.[0]).toEqual([
      { field: 'workspace_path', value: '/chosen/workspace' },
    ])
  })

  it('shows webapp workspace path as read-only', () => {
    vi.spyOn(nativeDialogs, 'isDesktop').mockReturnValue(true)
    const wrapper = mount(StorageSection, {
      ...globalOpts,
      props: {
        modelValue: {
          ...baseSettings,
          deployment_mode: 'webapp',
          workspace_path: '/srv/workspaces/current',
        },
      },
    })

    expect((wrapper.find('[data-testid="workspace-path-input"]').element as HTMLInputElement).value)
      .toBe('/srv/workspaces/current')
    expect(wrapper.find('[data-testid="workspace-path-change-button"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="workspace-path-help"]').text()).toContain(
      'managed by the web application',
    )
  })
})
