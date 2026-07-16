import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodeOutputErrorBlock from '../NodeOutputErrorBlock.vue'
import { useExecutionStore } from '@/stores/execution'
import {
  _resetCanvasStatusProjectionForTest,
  useCanvasStatusProjection,
} from '@/composables/useCanvasStatusProjection'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'

const EXECUTION_CONTEXT = {
  execution_id: 'exec-node-output',
  workflow_id: 'node-output-workflow',
  draft_revision: 1,
} as const

function mountBlock(nodeId: string) {
  return mount(NodeOutputErrorBlock, {
    props: { nodeId },
    global: { plugins: [PrimeVue] },
  })
}

function setFailed(
  nodeId: string,
  error: string | null,
  traceback: string | null = 'Traceback (most recent call last):\n  ...',
) {
  const store = useExecutionStore()
  store.applyNodeState({
    ...EXECUTION_CONTEXT,
    node_id: nodeId,
    status: 'failed',
    cached: false,
    error,
    traceback,
  })
}

describe('NodeOutputErrorBlock', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    _resetCanvasStatusProjectionForTest()
    setActivePinia(createPinia())
    const canvasId = canvasIdFromPanelId('workflow:node-output-workflow')
    useCanvasStatusProjection({
      descriptor: {
        kind: 'root',
        canvasId,
        workflowId: EXECUTION_CONTEXT.workflow_id,
      },
      nodes: ref([
        { id: 'n1', enabled: true },
        { id: 'other', enabled: true },
      ]),
      validationResult: ref(null),
      acceptedDraftRevision: ref(EXECUTION_CONTEXT.draft_revision),
    })
    useUIStore().setCanvasWorkflow(
      canvasId,
      EXECUTION_CONTEXT.workflow_id,
      'Node Output Workflow',
    )
    canvasSessionRegistry.activate(canvasId)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders nothing when the node has no status entry', () => {
    const w = mountBlock('n1')
    expect(w.find('.error-block').exists()).toBe(false)
  })

  it('renders nothing when the node status is not failed', () => {
    const store = useExecutionStore()
    store.applyNodeState({
      ...EXECUTION_CONTEXT,
      node_id: 'n1',
      status: 'executed',
      cached: false,
      error: null,
      traceback: null,
    })
    const w = mountBlock('n1')
    expect(w.find('.error-block').exists()).toBe(false)
  })

  it('renders the error banner when status is "failed"', () => {
    setFailed('n1', 'Something broke', 'Traceback...')
    const w = mountBlock('n1')
    expect(w.find('.error-block').exists()).toBe(true)
    expect(w.text()).toContain('Something broke')
  })

  it('hides a stale failure after the canvas projects an unexecuted edit', () => {
    const projection = useCanvasStatusProjection()
    setFailed('n1', 'Stale failure')
    projection.markProvisional('n1', {
      node_id: 'n1',
      status: 'unexecuted',
      cached: false,
    })

    const w = mountBlock('n1')

    expect(w.find('.error-block').exists()).toBe(false)
  })

  it('traceback is collapsed by default', () => {
    setFailed('n1', 'Boom', 'Traceback (most recent call last):\nFoo\nBar')
    const w = mountBlock('n1')
    expect(w.find('[data-testid="traceback-pre"]').exists()).toBe(false)
    const showBtn = w.find('[data-testid="traceback-toggle"]')
    expect(showBtn.exists()).toBe(true)
    expect(showBtn.text().toLowerCase()).toContain('show')
  })

  it('clicking "Show traceback" expands the full traceback', async () => {
    const tb = 'Traceback (most recent call last):\n  File "x.py", line 1\nValueError: bad'
    setFailed('n1', 'Boom', tb)
    const w = mountBlock('n1')
    await w.find('[data-testid="traceback-toggle"]').trigger('click')
    const pre = w.find('[data-testid="traceback-pre"]')
    expect(pre.exists()).toBe(true)
    expect(pre.text()).toContain('ValueError: bad')
  })

  it('"Copy traceback" button writes the traceback to the clipboard', async () => {
    vi.useFakeTimers()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    const tb = 'Traceback ABC'
    setFailed('n1', 'Boom', tb)
    const w = mountBlock('n1')
    await w.find('[data-testid="copy-traceback"]').trigger('click')
    expect(writeText).toHaveBeenCalledWith(tb)
    expect(w.find('[data-testid="copy-confirm"]').exists()).toBe(true)
    vi.advanceTimersByTime(2000)
    await w.vm.$nextTick()
    expect(w.find('[data-testid="copy-confirm"]').exists()).toBe(false)
  })

  it('renders the "Node failed on row N of M" line when progress matches', () => {
    setFailed('n1', 'Boom')
    const store = useExecutionStore()
    store.applyProgress({
      ...EXECUTION_CONTEXT,
      node_id: 'n1',
      row: 3,
      total_rows: 10,
    })
    const w = mountBlock('n1')
    const text = w.text()
    expect(text).toMatch(/row\s*3.*10/i)
  })

  it('does NOT render the row line when progress is for a different node', () => {
    setFailed('n1', 'Boom')
    const store = useExecutionStore()
    store.applyProgress({
      ...EXECUTION_CONTEXT,
      node_id: 'other',
      row: 3,
      total_rows: 10,
    })
    const w = mountBlock('n1')
    expect(w.find('[data-testid="failed-row-line"]').exists()).toBe(false)
  })

  it('always shows "All results discarded" guidance when block is rendered', () => {
    setFailed('n1', 'Boom')
    const w = mountBlock('n1')
    expect(w.text().toLowerCase()).toContain('discarded')
  })

  it('clears when the node transitions back to non-failed', async () => {
    setFailed('n1', 'Boom')
    const w = mountBlock('n1')
    expect(w.find('.error-block').exists()).toBe(true)
    const store = useExecutionStore()
    store.applyNodeState({
      ...EXECUTION_CONTEXT,
      node_id: 'n1',
      status: 'unexecuted',
      cached: false,
      error: null,
      traceback: null,
    })
    await w.vm.$nextTick()
    expect(w.find('.error-block').exists()).toBe(false)
  })

  it('renders a placeholder when error is null but status is failed', () => {
    setFailed('n1', null, null)
    const w = mountBlock('n1')
    expect(w.find('.error-block').exists()).toBe(true)
    expect(w.text().toLowerCase()).toContain('no error message')
  })
})
