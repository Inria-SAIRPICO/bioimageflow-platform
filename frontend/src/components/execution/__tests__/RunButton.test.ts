import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() },
}))

import RunButton from '../RunButton.vue'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'
import type { ValidationResult } from '@/api/types'

function mountButton(opts: {
  validationResult?: ValidationResult | null
  syncPending?: boolean
} = {}) {
  const graph = { nodes: [], edges: [] }
  const flushNow = vi.fn(async () => {})
  const validationResult = ref<ValidationResult | null>(
    opts.validationResult ?? {
      valid: true,
      node_statuses: {},
      errors: [],
    },
  )
  const graphSync = { flushNow, validationResult }
  const wrapper = mount(RunButton, {
    global: {
      plugins: [[PrimeVue, { theme: { preset: Aura } }]],
      stubs: {
        // PrimeVue Dialog teleports to document.body; stub it so the
        // assertions can use wrapper.find() without poking at the DOM.
        Dialog: {
          template: '<div v-if="visible" :data-testid="$attrs[\'data-testid\']"><slot /><slot name="footer" /></div>',
          props: ['visible'],
        },
      },
    },
    props: {
      graph,
      graphSync,
      syncPending: opts.syncPending ?? false,
    },
  })
  return { wrapper, graphSync, flushNow, validationResult }
}

describe('RunButton', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('Run button is enabled when idle and validation is not pending', () => {
    const { wrapper } = mountButton()
    const btn = wrapper.find('[data-testid="run-workflow-button"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('Run button disabled during execution with matching tooltip', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    // While running the Run button is hidden; Stop button is shown
    expect(wrapper.find('[data-testid="run-workflow-button"]').exists()).toBe(
      false,
    )
    expect(wrapper.find('[data-testid="stop-execution-button"]').exists()).toBe(
      true,
    )
  })

  it('Run button is disabled while validation is pending', async () => {
    const { wrapper } = mountButton({ syncPending: true })
    const btn = wrapper.find('[data-testid="run-workflow-button"]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('title')).toMatch(/validation/i)
  })

  it('Run Selected is disabled when no nodes selected', () => {
    const { wrapper } = mountButton()
    const btn = wrapper.find('[data-testid="run-selected-button"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('Run Selected passes selected node IDs to run', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    const ui = useUIStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    ui.setSelectedNodes(['n1', 'n2'])
    await nextTick()
    await wrapper.find('[data-testid="run-selected-button"]').trigger('click')
    await nextTick()
    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['n1', 'n2'], null)
  })

  it('passes the active workflow name to run', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    const workflows = useWorkflowStore()
    workflows.current = {
      name: 'wf_a',
      display_name: 'Workflow A',
      description: null,
      storage_path: '/tmp/workflows/wf_a',
      path: '/tmp/workflows/wf_a.json',
      last_modified: '2026-01-01T00:00:00Z',
    }
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()

    expect(runSpy).toHaveBeenCalledWith(expect.anything(), undefined, 'wf_a')
  })

  it('Stop button is only visible while running', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    expect(wrapper.find('[data-testid="stop-execution-button"]').exists()).toBe(
      false,
    )
    exec.state = 'running'
    await nextTick()
    expect(wrapper.find('[data-testid="stop-execution-button"]').exists()).toBe(
      true,
    )
  })

  it('Stop button calls executionStore.stop()', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    const stopSpy = vi.spyOn(exec, 'stop').mockResolvedValue()
    exec.state = 'running'
    await nextTick()
    await wrapper.find('[data-testid="stop-execution-button"]').trigger('click')
    expect(stopSpy).toHaveBeenCalled()
  })

  it('out-of-date confirm dialog appears when out_of_date nodes exist', async () => {
    const { wrapper } = mountButton({
      validationResult: {
        valid: true,
        node_statuses: {
          n1: { node_id: 'n1', status: 'out_of_date', cached: false },
        },
        errors: [],
      },
    })
    const exec = useExecutionStore()
    vi.spyOn(exec, 'run').mockResolvedValue()
    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="out-of-date-confirm"]').exists()).toBe(
      true,
    )
  })

  it('Run Selected does not prompt for out-of-date nodes outside the selected execution set', async () => {
    const { wrapper } = mountButton({
      validationResult: {
        valid: true,
        node_statuses: {
          downstream: { node_id: 'downstream', status: 'out_of_date', cached: false },
        },
        errors: [],
      },
    })
    const exec = useExecutionStore()
    const ui = useUIStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    ui.setSelectedNodes(['selected'])
    await nextTick()

    await wrapper.find('[data-testid="run-selected-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(wrapper.find('[data-testid="out-of-date-confirm"]').exists()).toBe(false)
    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['selected'], null)
  })

  it('run proceeds after confirm', async () => {
    const { wrapper } = mountButton({
      validationResult: {
        valid: true,
        node_statuses: {
          n1: { node_id: 'n1', status: 'out_of_date', cached: false },
        },
        errors: [],
      },
    })
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await wrapper.find('[data-testid="out-of-date-continue"]').trigger('click')
    await nextTick()
    await nextTick()
    expect(runSpy).toHaveBeenCalled()
  })

  it('run aborts on cancel', async () => {
    const { wrapper } = mountButton({
      validationResult: {
        valid: true,
        node_statuses: {
          n1: { node_id: 'n1', status: 'out_of_date', cached: false },
        },
        errors: [],
      },
    })
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await wrapper.find('[data-testid="out-of-date-cancel"]').trigger('click')
    await nextTick()
    await nextTick()
    expect(runSpy).not.toHaveBeenCalled()
  })

  it('emits toast on 409 conflict', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    vi.spyOn(exec, 'run').mockRejectedValue({ response: { status: 409 } })
    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()
    const toasts = wrapper.emitted('toast')
    expect(toasts).toBeTruthy()
    expect(toasts![0][0]).toMatchObject({ severity: 'warn' })
  })

  it('emits toast on 422 validation failure', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    vi.spyOn(exec, 'run').mockRejectedValue({ response: { status: 422 } })
    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()
    const toasts = wrapper.emitted('toast')
    expect(toasts).toBeTruthy()
    expect(toasts![0][0]).toMatchObject({ severity: 'error' })
  })

  it('enriches the validation toast with node/field details and auto-selects the first offender', async () => {
    // lockForExecution throws 'Validation errors found…' when validationResult.valid === false.
    // We arrange that state via the validationResult ref supplied to the button.
    const { wrapper } = mountButton({
      validationResult: {
        valid: false,
        node_statuses: {},
        errors: [
          {
            type: 'parameter_invalid',
            detail: "Input is not a valid path",
            node: 'files_1',
            edge_id: null,
            field: 'path',
          },
          {
            type: 'missing_connection',
            detail: 'Required input',
            node: 'atlas_1',
            edge_id: null,
            field: 'input_image',
          },
        ],
      },
    })
    const exec = useExecutionStore()
    // Spy shouldn't even be called — lockForExecution aborts first.
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    const ui = useUIStore()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(runSpy).not.toHaveBeenCalled()
    const toasts = wrapper.emitted('toast')
    expect(toasts).toBeTruthy()
    const payload = toasts![0][0] as {
      severity: string
      summary: string
      detail?: string
    }
    expect(payload.severity).toBe('error')
    expect(payload.summary).toContain('(2)')
    expect(payload.detail).toContain('files_1.path')
    expect(payload.detail).toContain('Input is not a valid path')
    expect(payload.detail).toContain('atlas_1.input_image')

    // First offending node auto-selected.
    expect(ui.selectedNodeIds).toEqual(['files_1'])
  })
})
