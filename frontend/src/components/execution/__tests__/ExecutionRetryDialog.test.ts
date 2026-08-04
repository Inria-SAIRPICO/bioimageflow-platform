import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'
import ExecutionRetryDialog from '../ExecutionRetryDialog.vue'

const jobs = [
  { id: 'prepare', scoped_node_path: 'prepare', state: 'succeeded' as const },
  { id: 'segment', scoped_node_path: 'analysis/segment', state: 'failed' as const },
]
const available = { available: true, reason: null }

describe('ExecutionRetryDialog', () => {
  it('previews scoped recomputation with downstream cascade enabled by default', async () => {
    const wrapper = mount(ExecutionRetryDialog, {
      props: {
        visible: true,
        jobs,
        initialMode: 'recompute',
        initialNodePath: 'analysis/segment',
        retryAction: available,
        recomputeAction: available,
        plan: null,
      },
      global: primeVueTestGlobal({ dialog: true }),
    })

    await wrapper.get('[data-testid="preview-execution-retry"]').trigger('click')

    expect(wrapper.emitted('preview')).toEqual([[
      { node_paths: ['analysis/segment'], cascade: true },
    ]])
  })

  it('shows invalidations and prevents confirmation while conflicts exist', async () => {
    const wrapper = mount(ExecutionRetryDialog, {
      props: {
        visible: true,
        jobs,
        initialMode: 'retry',
        retryAction: available,
        recomputeAction: available,
        plan: {
          plan_digest: 'sha256:plan',
          parent_execution_id: 'run-parent',
          child_execution_id: 'run-child',
          mode: 'recompute',
          target: { id: 'cluster', label: 'GPU cluster', mode: 'submitted_remote' },
          recompute: { node_paths: ['analysis/segment'], cascade: true },
          invalidations: [{
            node_path: 'analysis/segment', result_key: 'result-key',
            record_id: 'record-id', selection_status: 'selected',
          }],
          conflicting_run_ids: ['run-active'],
          confirmable: false,
          disabled_reason: 'An execution is active',
        },
      },
      global: primeVueTestGlobal({ dialog: true }),
    })

    expect(wrapper.get('[data-testid="retry-invalidations"]').text()).toContain('analysis/segment')
    expect(wrapper.get('[data-testid="retry-conflicts"]').text()).toContain('run-active')
    expect(wrapper.get('[data-testid="confirm-execution-retry"]').attributes('disabled')).toBeDefined()
  })

  it('disables an unavailable mode using the exact server reason', async () => {
    const wrapper = mount(ExecutionRetryDialog, {
      props: {
        visible: true,
        jobs,
        initialMode: 'recompute',
        retryAction: available,
        recomputeAction: { available: false, reason: 'Retained cache was pruned' },
        plan: null,
      },
      global: primeVueTestGlobal({ dialog: true }),
    })

    expect(wrapper.get('[data-testid="retry-mode-unavailable"]').text()).toContain(
      'Recompute nodes: Retained cache was pruned',
    )
    expect((wrapper.vm as unknown as { mode: string }).mode).toBe('retry')
    await wrapper.get('[data-testid="preview-execution-retry"]').trigger('click')
    expect(wrapper.emitted('preview')).toEqual([[null]])
  })

  it('prevents confirmation when the planned action becomes unavailable', async () => {
    const wrapper = mount(ExecutionRetryDialog, {
      props: {
        visible: true,
        jobs,
        initialMode: 'retry',
        retryAction: available,
        recomputeAction: available,
        plan: {
          plan_digest: 'sha256:plan',
          parent_execution_id: 'run-parent',
          child_execution_id: 'run-child',
          mode: 'retry',
          target: { id: 'cluster', label: 'GPU cluster', mode: 'submitted_remote' },
          recompute: null,
          invalidations: [],
          conflicting_run_ids: [],
          confirmable: true,
        },
      },
      global: primeVueTestGlobal({ dialog: true }),
    })

    await wrapper.setProps({
      retryAction: { available: false, reason: 'Parent retention was removed' },
    })

    expect(wrapper.get('[data-testid="retry-action-unavailable"]').text()).toContain(
      'Parent retention was removed',
    )
    expect(wrapper.get('[data-testid="confirm-execution-retry"]').attributes('disabled')).toBeDefined()
  })
})
