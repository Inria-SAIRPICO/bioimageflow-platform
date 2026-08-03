import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { items: [] } }),
    post: vi.fn(),
  },
}))

import ExecutionPanel from '../ExecutionPanel.vue'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'

describe('ExecutionPanel', () => {
  it('renders hierarchical jobs and structured diagnostics from a normalized snapshot', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const registry = useExecutionRegistryStore()
    registry.applySnapshot({
      id: 'run-1', revision: 1, workflow_id: 'workflow', workflow_name: 'Workflow',
      target_id: 'cluster', target_label: 'GPU cluster', target_mode: 'submitted_remote',
      state: 'failed', created_at: '2026-08-03T10:00:00Z',
      jobs: [{
        id: 'job-1', scoped_node_path: 'preprocessing/segment', display_name: 'Segment',
        parent_path: 'preprocessing', state: 'failed', executor_label: 'gpu',
        resources: { cpu: 4, gpu: 1, memory_gb: 16 }, duration_seconds: 2.5,
        diagnostic: { exception_type: 'RuntimeError', message: 'CUDA failed', traceback: 'trace' },
      }],
    })

    const wrapper = mount(ExecutionPanel, {
      global: { plugins: [pinia, PrimeVue] },
    })
    await flushPromises()
    // The mount refresh can replace history; restore a live snapshot exactly as a websocket does.
    registry.applySnapshot({
      id: 'run-1', revision: 2, workflow_id: 'workflow', workflow_name: 'Workflow',
      target_id: 'cluster', target_label: 'GPU cluster', target_mode: 'submitted_remote',
      state: 'failed', created_at: '2026-08-03T10:00:00Z',
      jobs: [{
        id: 'job-1', scoped_node_path: 'preprocessing/segment', display_name: 'Segment',
        state: 'failed', executor_label: 'gpu', resources: { cpu: 4, gpu: 1 },
        diagnostic: { exception_type: 'RuntimeError', message: 'CUDA failed', traceback: 'trace' },
      }],
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('GPU cluster')
    expect(wrapper.text()).toContain('Segment')
    await wrapper.get('button.job-row').trigger('click')
    expect(wrapper.get('[data-testid="execution-job-details"]').text()).toContain('CUDA failed')
  })
})
