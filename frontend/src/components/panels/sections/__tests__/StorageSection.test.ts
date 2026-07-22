import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'

import StorageSection from '../StorageSection.vue'
import { getDemoWorkflowsStatus } from '@/api/demoWorkflows'

vi.mock('@/api/demoWorkflows', () => ({
  getDemoWorkflowsStatus: vi.fn(),
  installDemoWorkflows: vi.fn(),
}))

vi.mock('@/api/workspace', () => ({
  getWorkspaceInfo: vi.fn().mockResolvedValue({
    workspace_path: '/tmp/workspace',
    workflows_root: '/tmp/workspace/workflows',
    tools_root: '/tmp/workspace/tools',
    outputs_root: '/tmp/workspace/outputs',
    deployment_mode: 'desktop',
    user_editable: true,
  }),
  revealFilesystemPath: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/utils/nativeDialogs', () => ({
  isDesktop: () => false,
  selectFolder: vi.fn(),
}))

const settings = {
  deployment_mode: 'desktop' as const,
  external_editor: null,
  napari_env_path: null,
  omero_instances: [],
  output_data_folder: '~/bioimageflow_data/',
  latest_output_mode: 'auto' as const,
  tool_store_path: '~/.bioimageflow/tool_packages/',
  update_mode: 'auto' as const,
  execution_engine: 'sequential' as const,
  node_data_page_size: 250 as const,
  keyboard_shortcuts: {},
  dev_mode: false,
  enable_unsafe_webapp_features: false,
  datasets_root: null,
  max_upload_size: 2147483648,
  resolved_tool_store_path: '/tmp/tools',
  resolved_output_data_folder: '/tmp/outputs',
  latest_output_effective_mode: 'symlink',
  latest_output_warning: null,
  latest_output_capabilities: {},
  workspace_path: '/tmp/workspace',
}

describe('StorageSection demo workflows', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows derived demo status and explicit install/remove actions', async () => {
    vi.mocked(getDemoWorkflowsStatus).mockResolvedValue({
      bundle_version: 1,
      status: 'partial',
      workflows: [
        {
          id: 'fish-analysis',
          version: 1,
          workflow_id: 'Demo/Fish Analysis',
          display_name: 'Fish Analysis',
          status: 'installed',
          installed_version: 1,
          identity_generation: 1,
        },
        {
          id: 'parameters-space-exploration',
          version: 1,
          workflow_id: 'Demo/Parameters Space Exploration',
          display_name: 'Parameters Space Exploration',
          status: 'missing',
          installed_version: null,
          identity_generation: null,
        },
      ],
      can_install: true,
      can_remove: true,
    })
    const wrapper = mount(StorageSection, {
      props: { modelValue: settings },
      global: {
        plugins: [createPinia(), PrimeVue, ConfirmationService, ToastService],
      },
    })

    await flushPromises()

    expect(wrapper.get('[data-testid="demo-workflows-status"]').text()).toContain(
      'Partially installed',
    )
    expect(wrapper.get('[data-testid="demo-workflows-install"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="demo-workflows-remove"]').attributes('disabled')).toBeUndefined()
  })
})
