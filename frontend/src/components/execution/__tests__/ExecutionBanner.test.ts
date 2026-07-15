import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

import ExecutionBanner from '../ExecutionBanner.vue'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'

function mountBanner() {
  return mount(ExecutionBanner, {
    global: {
      plugins: [[PrimeVue, { theme: { preset: Aura } }]],
    },
  })
}

describe('ExecutionBanner', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('is hidden when idle with no lastResult', () => {
    const wrapper = mountBanner()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(false)
  })

  it('shows running message when state is running', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    const headline = wrapper.find('[data-testid="execution-banner-headline"]')
    expect(headline.exists()).toBe(true)
    expect(headline.text()).toContain('Executing')
  })

  it('shows a non-terminal starting message', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'starting'
    await nextTick()

    expect((wrapper.vm as any).mode).toBe('starting')
    expect(wrapper.find('[data-testid="execution-banner-headline"]').text())
      .toContain('Starting')
    await wrapper.find('[data-testid="execution-banner"]').trigger('click')
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(true)
  })

  it('shows a non-terminal stopping message until idle is accepted', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    exec.state = 'stopping'
    await nextTick()

    expect((wrapper.vm as any).mode).toBe('stopping')
    expect(wrapper.find('[data-testid="execution-banner-headline"]').text())
      .toContain('Stopping')
    expect(wrapper.find('[data-testid="execution-banner-overall-progress"]').exists())
      .toBe(false)

    exec.applyStatusSnapshot({ state: 'idle', last_result: null, progress: null })
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner-headline"]').text())
      .toContain('stopped')
  })

  it('displays current node name when running with progress', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    exec.progress = { node_id: 'my_node', row: 3, total_rows: 10 }
    await nextTick()
    const el = wrapper.find('[data-testid="execution-banner-current-node"]')
    expect(el.exists()).toBe(true)
    expect(el.text()).toContain('my_node')
  })

  it('shows overall progress bar when running', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    const ui = useUIStore()
    ui.setGraphNodes([{ id: 'a' }, { id: 'b' }])
    exec.state = 'running'
    exec.nodeStatuses = {
      a: { node_id: 'a', status: 'executed', cached: false },
    }
    await nextTick()
    expect(
      wrapper.find('[data-testid="execution-banner-overall-progress"]').exists(),
    ).toBe(true)
  })

  it('shows row progress bar when row progress is present', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    exec.progress = { node_id: 'n1', row: 5, total_rows: 10 }
    await nextTick()
    expect(
      wrapper.find('[data-testid="execution-banner-row-progress"]').exists(),
    ).toBe(true)
  })

  it('does not render a duplicate Stop button in the running banner', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner-stop"]').exists()).toBe(false)
  })

  it('shows "Execution complete" on success result', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    exec.applyExecutionComplete({
      success: true,
      errors: [],
      node_statuses: {},
    })
    await nextTick()
    expect(
      wrapper.find('[data-testid="execution-banner-headline"]').text(),
    ).toContain('complete')
  })

  it('shows "Execution failed" and auto-selects failed node on failure', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    const ui = useUIStore()
    exec.state = 'running'
    await nextTick()
    exec.applyExecutionComplete({
      success: false,
      errors: [{ type: 'X', detail: 'kaboom' }],
      node_statuses: {
        bad: { node_id: 'bad', status: 'failed', cached: false, error: 'x' },
      },
    })
    await nextTick()
    expect(
      wrapper.find('[data-testid="execution-banner-headline"]').text(),
    ).toContain('failed')
    expect(ui.selectedNodeIds).toEqual(['bad'])
  })

  it('auto-dismisses after 5s on completion', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    exec.applyExecutionComplete({
      success: true,
      errors: [],
      node_statuses: {},
    })
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(true)
    vi.advanceTimersByTime(5000)
    await flushPromises()
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(false)
  })

  it('auto-dismisses when completion arrives before the start request resolves', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'starting'
    await nextTick()
    exec.applyExecutionComplete({
      success: true,
      errors: [],
      node_statuses: {},
    })
    await nextTick()

    expect((wrapper.vm as any).mode).toBe('success')
    vi.advanceTimersByTime(5000)
    await flushPromises()
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(false)
  })

  it('auto-dismisses after 3s on stop (no lastResult)', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    // Transition to idle with no lastResult (stop scenario)
    exec.state = 'idle'
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(true)
    vi.advanceTimersByTime(3000)
    await flushPromises()
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(false)
  })

  it('click on terminal banner dismisses immediately', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    exec.applyExecutionComplete({
      success: true,
      errors: [],
      node_statuses: {},
    })
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(true)
    await wrapper.find('[data-testid="execution-banner"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(false)
  })

  it('new execution clears pending dismiss timer', async () => {
    const wrapper = mountBanner()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    exec.applyExecutionComplete({
      success: true,
      errors: [],
      node_statuses: {},
    })
    await nextTick()
    // New execution starts before the 5s timer fires
    vi.advanceTimersByTime(1000)
    exec.state = 'running'
    exec.lastResult = null
    await nextTick()
    // Banner must still be visible (running), timer must not fire
    vi.advanceTimersByTime(5000)
    await nextTick()
    expect(wrapper.find('[data-testid="execution-banner"]').exists()).toBe(true)
  })
})
