import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const toastAdd = vi.fn()
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: toastAdd }),
}))

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import EnvironmentRecoveryDialog from '../EnvironmentRecoveryDialog.vue'
import { api } from '@/api/client'
import { useExecutionStore } from '@/stores/execution'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const EXECUTION_CONTEXT = {
  execution_id: 'exec-recovery',
  workflow_id: 'recovery-workflow',
  draft_revision: 1,
} as const

function mountDialog() {
  return mount(EnvironmentRecoveryDialog, {
    global: {
      stubs: {
        Dialog: {
          props: ['visible'],
          emits: ['update:visible'],
          template: '<div v-if="visible" data-testid="environment-recovery-dialog"><slot /><slot name="footer" /></div>',
        },
        Button: {
          props: ['label'],
          emits: ['click'],
          template: '<button v-bind="$attrs" @click="$emit(\'click\')">{{ label }}</button>',
        },
      },
    },
  })
}

function failWithRecovery() {
  const execution = useExecutionStore()
  execution.applyStatusSnapshot({
    ...EXECUTION_CONTEXT,
    state: 'running',
    last_result: null,
    progress: null,
    node_statuses: {},
  })
  execution.applyExecutionComplete({
    ...EXECUTION_CONTEXT,
    success: false,
    errors: [{
      type: 'EnvironmentReuseError',
      detail: 'Environment recipe mismatch',
      recovery_action: {
        kind: 'delete_environment',
        env_name: 'cellpose-env',
        path: '/wetlands/pixi/workspaces/cellpose-env/pixi.toml',
        existing_hash: 'sha256:old',
        requested_hash: 'sha256:new',
      },
    }],
    node_statuses: {},
  })
}

describe('EnvironmentRecoveryDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedApi.get.mockImplementation((url: string) => {
      if (url === '/api/v1/tools') return Promise.resolve({ data: [] })
      if (url === '/api/v1/tools/packages') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: {} })
    })
  })

  it('opens for environment recipe mismatch recovery actions', () => {
    failWithRecovery()
    const wrapper = mountDialog()

    expect(wrapper.find('[data-testid="environment-recovery-dialog"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('cellpose-env')
    expect(wrapper.text()).toContain('Retry the run')
  })

  it('cancel dismisses the recovery dialog without deleting', async () => {
    failWithRecovery()
    const wrapper = mountDialog()

    await wrapper.find('[data-testid="environment-recovery-cancel"]').trigger('click')

    expect(mockedApi.delete).not.toHaveBeenCalled()
    expect(useExecutionStore().isEnvironmentRecoveryDialogVisible).toBe(false)
  })

  it('deletes the environment after confirmation and tells the user to retry', async () => {
    failWithRecovery()
    mockedApi.delete.mockResolvedValueOnce({
      data: { environment: 'cellpose-env', status: 'deleted' },
    })
    const wrapper = mountDialog()

    await wrapper.find('[data-testid="environment-recovery-delete"]').trigger('click')
    await flushPromises()

    expect(mockedApi.delete).toHaveBeenCalledWith(
      '/api/v1/tools/environments/cellpose-env',
      {
        data: {
          path: '/wetlands/pixi/workspaces/cellpose-env/pixi.toml',
          existing_hash: 'sha256:old',
          requested_hash: 'sha256:new',
        },
      },
    )
    expect(useExecutionStore().isEnvironmentRecoveryDialogVisible).toBe(false)
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
      severity: 'success',
      detail: expect.stringContaining('Retry the run'),
    }))
  })
})
