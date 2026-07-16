import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'

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
import type { GraphState, ValidationResult } from '@/api/types'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'

function mountButton(opts: {
  validationResult?: ValidationResult | null
  syncPending?: boolean
} = {}) {
  const graph: GraphState = { nodes: [], edges: [] }
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
  })

  it('Run button is enabled when idle and validation is not pending', () => {
    const { wrapper } = mountButton()
    const btn = wrapper.find('[data-testid="run-workflow-button"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeUndefined()
  })

  it('Run button is disabled when no workflow identity is active', () => {
    useWorkflowStore().current = null
    const { wrapper } = mountButton()
    const btn = wrapper.find('[data-testid="run-workflow-button"]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('title')).toMatch(/workflow/i)
  })

  it('does not fall back to the global workflow when no registered canvas is active', () => {
    const canvasId = canvasIdFromPanelId('workflow:registered')
    canvasSessionRegistry.register({
      kind: 'root',
      canvasId,
      workflowId: 'registered',
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
    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['n1', 'n2'], 'wf_a')
  })

  it('runs the active canvas selection and workflow identity', async () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'wf_a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'wf_b' })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'wf_a', 'Workflow A')
    ui.setCanvasSelectedNodes(canvasA, ['node-a'])
    ui.setCanvasWorkflow(canvasB, 'wf_b', 'Workflow B')
    ui.setCanvasSelectedNodes(canvasB, ['node-b'])
    canvasSessionRegistry.activate(canvasA)
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

    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['node-a'], 'wf_a')
  })

  it('captures the active root canvas and accepted draft revision', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'wf_a' })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')
    canvasSessionRegistry.activate(canvasId)
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
    const canvasId = canvasIdFromPanelId('workflow:a')
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'wf_a' })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')
    canvasSessionRegistry.activate(canvasId)
    persistenceMocks.canvasId = canvasId
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
    const staleGraph: GraphState = {
      nodes: [{
        id: 'stale',
        name: 'Stale',
        tool_name: 'old_tool',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    }
    const freshGraph: GraphState = {
      nodes: [{
        id: 'fresh',
        name: 'Fresh',
        tool_name: 'new_tool',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    }
    const { wrapper, currentGraph } = mountButton()
    await wrapper.setProps({ graph: staleGraph })
    currentGraph.value = freshGraph
    const exec = useExecutionStore()
    const runSpy = vi.spyOn(exec, 'run').mockResolvedValue()

    await wrapper.find('[data-testid="run-workflow-button"]').trigger('click')
    await nextTick()
    await nextTick()

    expect(runSpy).toHaveBeenCalledWith(freshGraph, undefined, 'wf_a')
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
    expect(runSpy).toHaveBeenCalledWith(expect.anything(), ['selected'], 'wf_a')
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
    const canvasId = canvasIdFromPanelId('workflow:a')
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'wf_a' })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')
    canvasSessionRegistry.activate(canvasId)
    persistenceMocks.canvasId = canvasId
    persistenceMocks.acceptedDraftRevision.value = 7
    const graphA: GraphState = {
      nodes: [{
        id: 'node-a',
        name: 'Node A',
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
    const graphB: GraphState = {
      nodes: [{
        id: 'node-b',
        name: 'Node B',
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
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'wf_a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'wf_b' })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'wf_a', 'Workflow A')
    ui.setCanvasWorkflow(canvasB, 'wf_b', 'Workflow B')
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
