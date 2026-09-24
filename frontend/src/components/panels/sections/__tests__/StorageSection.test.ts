import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmDialog from 'primevue/confirmdialog'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'

import StorageSection from '../StorageSection.vue'
import { getDemoWorkflowsStatus } from '@/api/demoWorkflows'
import { useWorkflowStore } from '@/stores/workflow'

vi.mock('@/api/demoWorkflows', () => ({
  getDemoWorkflowsStatus: vi.fn(),
  installDemoWorkflows: vi.fn(),
}))

vi.mock('@/api/workspace', () => ({
  getWorkspaceInfo: vi.fn().mockResolvedValue({
    workspace_path: '/tmp/workspace',
    workflows_root: '/tmp/workspace/workflows',
    tools_root: '/tmp/workspace/tools',
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
  napari_registry_revision: 0,
  omero_instances: [],
  tool_store_path: '~/.bioimageflow/tool_packages/',
  update_mode: 'auto' as const,
  new_workflow_execution: 'sequential' as const,
  default_execution_target_id: 'local',
  node_data_page_size: 250 as const,
  keyboard_shortcuts: {},
  dev_mode: false,
  enable_unsafe_webapp_features: false,
  datasets_root: null,
  max_upload_size: 2147483648,
  resolved_tool_store_path: '/tmp/tools',
  latest_output_effective_mode: 'symlink' as const,
  latest_output_warning: null,
  workspace_path: '/tmp/workspace',
}

describe('StorageSection demo workflows', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows derived demo status and explicit install/remove actions', async () => {
    vi.mocked(getDemoWorkflowsStatus).mockResolvedValue({
      bundle_version: 2,
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

    expect(wrapper.find('[data-testid="latest-output-mode"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="latest-output-effective-mode"]').text())
      .toContain('Symbolic links')
    expect(wrapper.text()).toContain('Use Export when you need independent file copies')
    expect(wrapper.get('[data-testid="demo-workflows-status"]').text()).toContain(
      'Partially installed',
    )
    expect(wrapper.get('[data-testid="demo-workflows-install"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="demo-workflows-remove"]').attributes('disabled')).toBeUndefined()
  })

  it('shows one confirmation and sends one deletion per installed demo', async () => {
    vi.mocked(getDemoWorkflowsStatus).mockResolvedValue({
      bundle_version: 2,
      status: 'installed',
      workflows: ['Demo/Fish Analysis', 'Demo/Parameters Space Exploration'].map((workflow_id) => ({
        id: workflow_id,
        version: 1,
        workflow_id,
        display_name: workflow_id,
        status: 'installed' as const,
        installed_version: 1,
        identity_generation: 1,
      })),
      can_install: false,
      can_remove: true,
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.spyOn(useWorkflowStore(), 'fetchWorkflowTree').mockResolvedValue([])
    const deleted: string[] = []
    const onDelete = (event: Event) => {
      const detail = (event as CustomEvent<{ workflowName: string; resolve: () => void }>).detail
      deleted.push(detail.workflowName)
      detail.resolve()
    }
    window.addEventListener('bioimageflow:request-delete-workflow', onDelete)
    const host = document.createElement('div')
    document.body.appendChild(host)
    const wrapper = mount(defineComponent({
      render: () => h('div', [
        h(ConfirmDialog, { group: 'app' }),
        h(ConfirmDialog),
        h(StorageSection, { modelValue: settings }),
      ]),
    }), {
      attachTo: host,
      global: { plugins: [pinia, PrimeVue, ConfirmationService, ToastService] },
    })

    try {
      await flushPromises()
      await wrapper.get('[data-testid="demo-workflows-remove"]').trigger('click')
      await flushPromises()
      expect(document.querySelectorAll('[role="alertdialog"]')).toHaveLength(1)
      const accept = [...document.querySelectorAll('button')]
        .find(button => button.textContent?.trim() === 'Yes')
      expect(accept).toBeDefined()
      accept?.click()
      await flushPromises()
      expect(deleted).toEqual(['Demo/Fish Analysis', 'Demo/Parameters Space Exploration'])
    } finally {
      wrapper.unmount()
      host.remove()
      window.removeEventListener('bioimageflow:request-delete-workflow', onDelete)
    }
  })
})
