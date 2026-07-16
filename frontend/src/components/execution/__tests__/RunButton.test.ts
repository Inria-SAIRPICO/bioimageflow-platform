import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() },
}))

const workflowDraftMocks = vi.hoisted(() => ({
  ensureFreshForCriticalOperation: vi.fn().mockResolvedValue(true),
}))

const persistenceMocks = vi.hoisted(() => ({
  ensureFreshForCriticalOperation: vi.fn().mockResolvedValue(true),
  acceptedDraftRevision: { value: null as number | null },
  canvasId: null as ReturnType<typeof canvasIdFromPanelId> | null,
}))

vi.mock('@/stores/workflowDraft', () => ({
  useWorkflowDraftStore: () => workflowDraftMocks,
}))

vi.mock('@/composables/useCanvasPersistence', () => ({
  useCanvasPersistence: () => persistenceMocks,
}))

import RunButton from '../RunButton.vue'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'
import { useCanvasLifecycleStore } from '@/stores/canvasLifecycle'
import type { ValidationResult } from '@/api/types'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import { makeGraph, makeGraphNode } from '@/test-utils/graphFixtures'
import {
  registerNestedCanvas,
  registerRootCanvas,
} from '@/test-utils/canvasFixtures'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'

function mountButton(opts: {
  validationResult?: ValidationResult | null
  syncPending?: boolean
} = {}) {
  const graph = makeGraph()
  const flushNow = vi.fn(async () => {})
  const validationResult = ref<ValidationResult | null>(
    opts.validationResult ?? {
      valid: true,
      node_statuses: {},
      errors: [],
    },
  )
  const currentGraph = ref(graph)
  const graphSync = { flushNow, validationResult, currentGraph }
  const wrapper = mount(RunButton, {
    // PrimeVue Dialog teleports to document.body; the shared visible stub
    // keeps assertions within this wrapper.
    global: primeVueTestGlobal({ dialog: true }),
    props: {
      graph,
      graphSync,
      syncPending: opts.syncPending ?? false,
    },
  })
  return { wrapper, graphSync, flushNow, validationResult, currentGraph }
}

describe('RunButton', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    useWorkflowStore().current = {
      name: 'wf_a',
      display_name: 'Workflow A',
      description: null,
      storage_path: '/tmp/workflows/wf_a',
      path: '/tmp/workflows/wf_a.json',
      last_modified: '2026-01-01T00:00:00Z',
    }
    workflowDraftMocks.ensureFreshForCriticalOperation.mockClear()
    workflowDraftMocks.ensureFreshForCriticalOperation.mockResolvedValue(true)
    persistenceMocks.ensureFreshForCriticalOperation.mockClear()
    persistenceMocks.ensureFreshForCriticalOperation.mockResolvedValue(true)
    persistenceMocks.acceptedDraftRevision.value = null
    persistenceMocks.canvasId = null
    const { canvasId } = registerRootCanvas('wf_a', {
      displayName: 'Workflow A',
    })
    persistenceMocks.canvasId = canvasId
    persistenceMocks.acceptedDraftRevision.value = 1
  })

  it('Run button is enabled when idle and validation is not pending', () => {
    const { wrapper } = mountButton()
    const btn = wrapper.find('[data-testid="run-workflow-button"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('does not block the active workflow for another canvas lifecycle action', async () => {
    const inactive = registerRootCanvas('wf_b', { activate: false })
    const lifecycle = useCanvasLifecycleStore()
    lifecycle.begin(inactive.canvasId, 'deleting')
    const { wrapper } = mountButton()

    expect(
      wrapper.find('[data-testid="run-workflow-button"]').attributes('disabled'),
    ).toBeUndefined()

    lifecycle.begin(persistenceMocks.canvasId!, 'saving')
    await nextTick()
    expect(
      wrapper.find('[data-testid="run-workflow-button"]').attributes('disabled'),
    ).toBeDefined()
  })

  it('Run button is disabled when no workflow identity is active', () => {
    canvasSessionRegistry.dispose()
    useWorkflowStore().current = null
    const { wrapper } = mountButton()
    const btn = wrapper.find('[data-testid="run-workflow-button"]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('title')).toMatch(/workflow/i)
  })

  it('does not fall back to the global workflow when no registered canvas is active', () => {
    canvasSessionRegistry.dispose()
    registerRootCanvas('registered', {
      activate: false,
      present: false,
    })

    const { wrapper } = mountButton()
    const btn = wrapper.find('[data-testid="run-workflow-button"]')

    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('title')).toMatch(/workflow/i)
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

  it('shows a disabled starting state without exposing Stop', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    exec.state = 'starting'
    await nextTick()

    const run = wrapper.find('[data-testid="run-workflow-button"]')
    expect(run.exists()).toBe(true)
    expect(run.attributes('disabled')).toBeDefined()
    expect(run.text()).toContain('Starting')
    expect(wrapper.find('[data-testid="stop-execution-button"]').exists()).toBe(false)
  })

  it('shows a disabled stopping state so Stop cannot be repeated', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    exec.state = 'stopping'
    await nextTick()

    const stop = wrapper.find('[data-testid="stop-execution-button"]')
    expect(stop.exists()).toBe(true)
    expect(stop.attributes('disabled')).toBeDefined()
    expect(stop.text()).toContain('Stopping')
    expect(wrapper.find('[data-testid="run-workflow-button"]').exists()).toBe(false)
  })

  it('Run remains clickable while validation is pending and flushes before execution', async () => {
    const { wrapper, flushNow } = mountButton({ syncPending: true })
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()
    const btn = wrapper.find('[data-testid="run-workflow-button"]')
    expect(btn.attributes('disabled')).toBeUndefined()

    await btn.trigger('click')
    await nextTick()
    await nextTick()

    expect(flushNow).toHaveBeenCalledOnce()
    expect(runSpy).toHaveBeenCalledOnce()
    expect(flushNow.mock.invocationCallOrder[0]).toBeLessThan(
      runSpy.mock.invocationCallOrder[0]!,
    )
  })

  it('flushes pending validation before deciding which nodes need confirmation', async () => {
    const { wrapper, flushNow, validationResult, currentGraph } = mountButton({
      syncPending: true,
    })
    currentGraph.value = {
      nodes: [{
        id: 'changed',
        name: 'Changed',
        tool_name: 'tool',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    }
    flushNow.mockImplementation(async () => {
      validationResult.value = {
        valid: true,
        node_statuses: {
          changed: { node_id: 'changed', status: 'out_of_date', cached: false },
        },
        errors: [],
      }
    })
    const runSpy = vi.spyOn(useExecutionStore(), 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(flushNow).toHaveBeenCalledOnce()
    expect(wrapper.emitted('confirm-required')).toEqual([[['changed']]])
    expect(runSpy).not.toHaveBeenCalled()
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
    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['n1', 'n2'], 'wf_a', {
      canvasId: persistenceMocks.canvasId,
      draftRevision: 1,
    })
  })

  it('runs the active canvas selection and workflow identity', async () => {
    const { canvasId: canvasA } = registerRootCanvas('wf_a', {
      panelId: 'workflow:a',
      displayName: 'Workflow A',
      activate: false,
    })
    const { canvasId: canvasB } = registerRootCanvas('wf_b', {
      panelId: 'workflow:b',
      displayName: 'Workflow B',
      activate: false,
    })
    const ui = useUIStore()
    ui.setCanvasSelectedNodes(canvasA, ['node-a'])
    ui.setCanvasSelectedNodes(canvasB, ['node-b'])
    canvasSessionRegistry.activate(canvasA)
    persistenceMocks.canvasId = canvasA
    persistenceMocks.acceptedDraftRevision.value = 3
    useWorkflowStore().current = {
      name: 'wf_b',
      display_name: 'Workflow B',
    } as any
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-selected-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['node-a'], 'wf_a', {
      canvasId: canvasA,
      draftRevision: 3,
    })
  })

  it('captures the active root canvas and accepted draft revision', async () => {
    const { canvasId } = registerRootCanvas('wf_a', {
      panelId: 'workflow:a',
      displayName: 'Workflow A',
    })
    persistenceMocks.canvasId = canvasId
    persistenceMocks.acceptedDraftRevision.value = 7
    const { wrapper } = mountButton()
    const runSpy = vi.spyOn(useExecutionStore(), 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(runSpy).toHaveBeenCalledWith(expect.anything(), undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })
  })

  it('does not start a root execution without an accepted draft revision', async () => {
    const { canvasId } = registerRootCanvas('wf_a', {
      panelId: 'workflow:a',
      displayName: 'Workflow A',
    })
    persistenceMocks.canvasId = canvasId
    persistenceMocks.acceptedDraftRevision.value = null
    const { wrapper } = mountButton()
    const runSpy = vi.spyOn(useExecutionStore(), 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(runSpy).not.toHaveBeenCalled()
    expect(wrapper.emitted('toast')?.[0]?.[0]).toMatchObject({
      severity: 'error',
      summary: 'Run failed',
    })
  })

  it('disables nested-canvas Run commands and never enters preparation', async () => {
    const { canvasId: parentCanvasId } = registerRootCanvas('wf_a', {
      panelId: 'workflow:a',
      displayName: 'Workflow A',
      activate: false,
    })
    const { canvasId: nestedCanvasId } = registerNestedCanvas({
      sessionId: 'nested-a',
      parentCanvasId,
      workflowId: 'wf_a',
      panelId: 'sub-workflow:nested-a',
      displayName: 'Nested A',
    })
    const ui = useUIStore()
    ui.setCanvasSelectedNodes(nestedCanvasId, ['nested-node'])
    persistenceMocks.canvasId = nestedCanvasId
    const { wrapper, flushNow } = mountButton()
    const runSpy = vi.spyOn(useExecutionStore(), 'run').mockResolvedValue()

    const run = wrapper.find('[data-testid="run-workflow-button"]')
    const runSelected = wrapper.find('[data-testid="run-selected-button"]')
    expect(run.attributes('disabled')).toBeDefined()
    expect(runSelected.attributes('disabled')).toBeDefined()
    expect(run.attributes('title')).toMatch(/owning root workflow/i)
    expect(runSelected.attributes('title')).toMatch(/owning root workflow/i)

    const exposed = wrapper.vm as unknown as {
      onRun(): Promise<void>
      onRunSelected(): Promise<void>
    }
    await exposed.onRun()
    await exposed.onRunSelected()

    expect(persistenceMocks.ensureFreshForCriticalOperation).not.toHaveBeenCalled()
    expect(flushNow).not.toHaveBeenCalled()
    expect(runSpy).not.toHaveBeenCalled()
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

    expect(runSpy).toHaveBeenCalledWith(expect.anything(), undefined, 'wf_a', {
      canvasId: persistenceMocks.canvasId,
      draftRevision: 1,
    })
    expect(persistenceMocks.ensureFreshForCriticalOperation).toHaveBeenCalledOnce()
    expect(workflowDraftMocks.ensureFreshForCriticalOperation).not.toHaveBeenCalled()
  })

  it('blocks run when the active workflow has unresolved remote draft changes', async () => {
    persistenceMocks.ensureFreshForCriticalOperation.mockResolvedValueOnce(false)
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(runSpy).not.toHaveBeenCalled()
    expect(wrapper.emitted('toast')![0][0]).toMatchObject({
      severity: 'warn',
      summary: 'Resolve workflow changes first',
    })
  })

  it('uses the latest graph-sync graph after the freshness check', async () => {
    const staleGraph = makeGraph({
      nodes: [makeGraphNode({
        id: 'stale',
        name: 'Stale',
        tool_name: 'old_tool',
      })],
    })
    const freshGraph = makeGraph({
      nodes: [makeGraphNode({
        id: 'fresh',
        name: 'Fresh',
        tool_name: 'new_tool',
      })],
    })
    const { wrapper, currentGraph } = mountButton()
    await wrapper.setProps({ graph: staleGraph })
    currentGraph.value = freshGraph
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(runSpy).toHaveBeenCalledWith(freshGraph, undefined, 'wf_a', {
      canvasId: persistenceMocks.canvasId,
      draftRevision: 1,
    })
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
    const stopSpy = vi.spyOn(exec, 'stop').mockResolvedValue(true)
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
    const dialogText = wrapper.find('[data-testid="out-of-date-confirm"]').text()
    expect(dialogText).toContain('need rebuild')
    expect(dialogText).not.toMatch(/corrupt|invalid cache/i)
  })

  it('flushes fresh validation before deciding whether confirmation is required', async () => {
    const { wrapper, flushNow, validationResult } = mountButton()
    flushNow.mockImplementation(async () => {
      validationResult.value = {
        valid: true,
        node_statuses: {
          n1: { node_id: 'n1', status: 'out_of_date', cached: false },
        },
        errors: [],
      }
    })
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(flushNow).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="out-of-date-confirm"]').exists()).toBe(true)
    expect(runSpy).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="out-of-date-continue"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(flushNow).toHaveBeenCalledTimes(1)
    expect(runSpy).toHaveBeenCalled()
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
    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['selected'], 'wf_a', {
      canvasId: persistenceMocks.canvasId,
      draftRevision: 1,
    })
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

  it('requires fresh confirmation when the graph changes while confirmation is open', async () => {
    const { canvasId } = registerRootCanvas('wf_a', {
      panelId: 'workflow:a',
      displayName: 'Workflow A',
    })
    persistenceMocks.canvasId = canvasId
    persistenceMocks.acceptedDraftRevision.value = 7
    const graphA = makeGraph({
      nodes: [makeGraphNode({
        id: 'node-a',
        name: 'Node A',
      })],
    })
    const graphB = makeGraph({
      nodes: [makeGraphNode({
        id: 'node-b',
        name: 'Node B',
      })],
    })
    const { wrapper, currentGraph, validationResult, flushNow } = mountButton({
      validationResult: {
        valid: true,
        node_statuses: {
          'node-a': { node_id: 'node-a', status: 'out_of_date', cached: false },
        },
        errors: [],
      },
    })
    currentGraph.value = graphA
    const runSpy = vi.spyOn(useExecutionStore(), 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    expect(wrapper.emitted('confirm-required')).toEqual([[['node-a']]])

    currentGraph.value = graphB
    validationResult.value = {
      valid: true,
      node_statuses: {
        'node-b': { node_id: 'node-b', status: 'out_of_date', cached: false },
      },
      errors: [],
    }
    persistenceMocks.acceptedDraftRevision.value = 8
    await wrapper.find('[data-testid="out-of-date-continue"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(flushNow).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('confirm-required')).toEqual([
      [['node-a']],
      [['node-b']],
    ])
    expect(runSpy).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="out-of-date-continue"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(flushNow).toHaveBeenCalledTimes(2)
    expect(runSpy).toHaveBeenCalledWith(graphB, undefined, 'wf_a', {
      canvasId,
      draftRevision: 8,
    })
  })

  it('does not redirect a confirmed run when another canvas becomes active', async () => {
    const { canvasId: canvasA } = registerRootCanvas('wf_a', {
      panelId: 'workflow:a',
      displayName: 'Workflow A',
      activate: false,
    })
    const { canvasId: canvasB } = registerRootCanvas('wf_b', {
      panelId: 'workflow:b',
      displayName: 'Workflow B',
      activate: false,
    })
    canvasSessionRegistry.activate(canvasA)
    persistenceMocks.canvasId = canvasA
    persistenceMocks.acceptedDraftRevision.value = 7
    const { wrapper, flushNow } = mountButton({
      validationResult: {
        valid: true,
        node_statuses: {
          n1: { node_id: 'n1', status: 'out_of_date', cached: false },
        },
        errors: [],
      },
    })
    const runSpy = vi.spyOn(useExecutionStore(), 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="out-of-date-confirm"]').exists()).toBe(true)

    canvasSessionRegistry.activate(canvasB)
    persistenceMocks.canvasId = canvasB
    await wrapper.find('[data-testid="out-of-date-continue"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(flushNow).toHaveBeenCalledOnce()
    expect(runSpy).not.toHaveBeenCalled()
    expect(wrapper.emitted('run-started')).toBeUndefined()
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

  it('emits an already-running warning for an untyped 409 conflict', async () => {
    const { wrapper } = mountButton()
    const exec = useExecutionStore()
    vi.spyOn(exec, 'run').mockRejectedValue({ response: { status: 409 } })
    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()
    const toasts = wrapper.emitted('toast')
    expect(toasts).toBeTruthy()
    expect(toasts![0][0]).toMatchObject({
      severity: 'warn',
      summary: 'An execution is already running',
    })
  })

  it.each(['draft_revision_conflict', 'draft_graph_mismatch'])(
    'emits a workflow-changed warning for %s',
    async (errorCode) => {
      const { wrapper } = mountButton()
      const exec = useExecutionStore()
      vi.spyOn(exec, 'run').mockRejectedValue({
        response: {
          status: 409,
          data: { error: errorCode, detail: 'Execution input is stale' },
        },
      })

      await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
      await nextTick()
      await nextTick()

      expect(wrapper.emitted('toast')?.[0]?.[0]).toMatchObject({
        severity: 'warn',
        summary: 'Workflow changed before execution',
        detail: expect.stringMatching(/refresh.*retry/i),
      })
    },
  )

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
