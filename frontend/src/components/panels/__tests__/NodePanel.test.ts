import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodePanel from '../NodePanel.vue'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useLoggerStore } from '@/stores/logger'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'
import {
  _resetCanvasCommandsForTest,
  useCanvasCommands,
} from '@/composables/useCanvasCommands'
import type { ToolMetadata, InputFieldSchema } from '@/api/types'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import {
  __resetForTests as resetFieldFocusForTests,
  useFieldFocusTracker,
} from '@/composables/useFieldFocusTracker'

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'bioimageflow-core',
    package_version: '0.3.2',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: 'Apply gaussian blur to smooth images.',
    tags: [],
    categories: ['Filtering'],
    inputs: {
      image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default', description: 'Input image path' },
      sigma: { type: 'float', required: true, nullable: false, connectable: 'never', default: 1.0, min: 0.1, max: 50.0, step: 0.1, description: 'Blur strength' },
      threshold: { type: 'float', required: false, nullable: true, connectable: 'never', default: 0.5, description: 'Optional threshold' },
    },
    outputs: {
      result: { type: 'ImageFile' },
      mask: { type: 'MaskPath' },
    },
    environment: null,
    ...overrides,
  }
}

function makeNodeData(overrides: Record<string, unknown> = {}) {
  return {
    name: 'Blur 1',
    toolName: 'gaussian_blur',
    tool: makeTool(),
    status: 'unexecuted',
    parameters: { sigma: 1.0, threshold: 0.5 } as Record<string, unknown>,
    collapsed: false,
    enabled: true,
    connectedInputs: {} as Record<string, string>,
    pinnedInputs: { image: true } as Record<string, boolean>,
    output_templates: { result: '', mask: '' } as Record<string, string>,
    ...overrides,
  }
}

let mountedCanvasIndex = 0

const nodeEditCommandCalls = {
  renameNode: vi.fn(),
  setNodeEnabled: vi.fn(),
  setInputPinned: vi.fn(),
  setOutputTemplate: vi.fn(),
  togglePublishedInput: vi.fn(),
  togglePublishedOutput: vi.fn(),
  renamePublishedInput: vi.fn(),
  renamePublishedOutput: vi.fn(),
}

function mountPanel(
  nodeData: ReturnType<typeof makeNodeData> | null = null,
  executionPhase: 'idle' | 'starting' | 'running' | 'stopping' = 'idle',
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const uiStore = useUIStore()
  const canvasId = canvasIdFromPanelId(`node-panel:test-${mountedCanvasIndex++}`)
  const descriptor = {
    kind: 'root' as const,
    canvasId,
    workflowId: null,
  }
  useGraphSync({ descriptor, getWorkflowId: () => null })
  useCanvasCommands({
    descriptor,
    renameNode: (nodeId, name) => {
      nodeEditCommandCalls.renameNode(nodeId, name)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      if (!node?.data) return false
      const trimmed = name.trim()
      if (!trimmed || trimmed === node.data.name) return false
      if (uiStore.graphNodes.some((candidate: any) => (
        candidate.id !== nodeId && candidate.data?.name === trimmed
      ))) return false
      node.data.name = trimmed
      return true
    },
    setNodeEnabled: (nodeId, enabled) => {
      nodeEditCommandCalls.setNodeEnabled(nodeId, enabled)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      if (!node?.data || node.data.enabled === enabled) return false
      node.data.enabled = enabled
      return true
    },
    setInputPinned: (nodeId, key, pinned) => {
      nodeEditCommandCalls.setInputPinned(nodeId, key, pinned)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      if (!node?.data) return false
      const nextPinned = key in (node.data.connectedInputs ?? {}) ? true : pinned
      if (node.data.pinnedInputs?.[key] === nextPinned) return false
      node.data.pinnedInputs = { ...(node.data.pinnedInputs ?? {}), [key]: nextPinned }
      return true
    },
    setOutputTemplate: (nodeId, key, value) => {
      nodeEditCommandCalls.setOutputTemplate(nodeId, key, value)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      if (!node?.data || node.data.output_templates?.[key] === value) return false
      node.data.output_templates = { ...(node.data.output_templates ?? {}), [key]: value }
      return true
    },
    togglePublishedInput: (nodeId, key) => {
      nodeEditCommandCalls.togglePublishedInput(nodeId, key)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      const context = node?.data?.publicationContext ?? node?.data?.subWorkflowContext
      const field = node?.data?.tool?.inputs?.[key]
      if (!node?.data || !context || !field) {
        return { status: 'rejected' as const, reason: 'not_found' as const }
      }
      const index = (context.published_inputs ?? []).findIndex((item: any) => (
        item.internal_node_id === nodeId && item.internal_field === key
      ))
      if (index >= 0) {
        context.published_inputs = context.published_inputs.filter(
          (_item: any, candidateIndex: number) => candidateIndex !== index,
        )
        return { status: 'changed' as const }
      }
      const name = `${nodeId}.${key}`
      const names = [...(context.published_inputs ?? []), ...(context.published_outputs ?? [])]
        .map((item: any) => item.name)
      if (names.includes(name)) {
        return { status: 'rejected' as const, reason: 'duplicate_name' as const, name }
      }
      context.published_inputs = [...(context.published_inputs ?? []), {
        name,
        internal_node_id: nodeId,
        internal_field: key,
        kind: 'input',
        schema: field,
        default: node.data.parameters?.[key] ?? field.default ?? null,
      }]
      return { status: 'changed' as const }
    },
    togglePublishedOutput: (nodeId, key) => {
      nodeEditCommandCalls.togglePublishedOutput(nodeId, key)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      const context = node?.data?.publicationContext ?? node?.data?.subWorkflowContext
      const field = node?.data?.tool?.outputs?.[key]
      if (!node?.data || !context || !field) {
        return { status: 'rejected' as const, reason: 'not_found' as const }
      }
      const index = (context.published_outputs ?? []).findIndex((item: any) => (
        item.internal_node_id === nodeId && item.internal_output === key
      ))
      if (index >= 0) {
        context.published_outputs = context.published_outputs.filter(
          (_item: any, candidateIndex: number) => candidateIndex !== index,
        )
        return { status: 'changed' as const }
      }
      const name = `${nodeId}.${key}`
      const names = [...(context.published_inputs ?? []), ...(context.published_outputs ?? [])]
        .map((item: any) => item.name)
      if (names.includes(name)) {
        return { status: 'rejected' as const, reason: 'duplicate_name' as const, name }
      }
      context.published_outputs = [...(context.published_outputs ?? []), {
        name,
        internal_node_id: nodeId,
        internal_output: key,
        schema: field,
      }]
      return { status: 'changed' as const }
    },
    renamePublishedInput: (nodeId, key, value) => {
      nodeEditCommandCalls.renamePublishedInput(nodeId, key, value)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      const context = node?.data?.publicationContext ?? node?.data?.subWorkflowContext
      const index = (context?.published_inputs ?? []).findIndex((item: any) => (
        item.internal_node_id === nodeId && item.internal_field === key
      )) ?? -1
      if (!context || index < 0) {
        return { status: 'rejected' as const, reason: 'not_found' as const }
      }
      const next = value.trim()
      if (!next) return { status: 'rejected' as const, reason: 'empty_name' as const }
      const current = context.published_inputs[index]
      if (current.name === next) return { status: 'unchanged' as const }
      const duplicate = [...context.published_inputs, ...(context.published_outputs ?? [])]
        .some((item: any) => item !== current && item.name === next)
      if (duplicate) {
        return { status: 'rejected' as const, reason: 'duplicate_name' as const, name: next }
      }
      context.published_inputs = context.published_inputs.map((item: any, itemIndex: number) => (
        itemIndex === index ? { ...item, name: next } : item
      ))
      return { status: 'changed' as const }
    },
    renamePublishedOutput: (nodeId, key, value) => {
      nodeEditCommandCalls.renamePublishedOutput(nodeId, key, value)
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      const context = node?.data?.publicationContext ?? node?.data?.subWorkflowContext
      const index = (context?.published_outputs ?? []).findIndex((item: any) => (
        item.internal_node_id === nodeId && item.internal_output === key
      )) ?? -1
      if (!context || index < 0) {
        return { status: 'rejected' as const, reason: 'not_found' as const }
      }
      const next = value.trim()
      if (!next) return { status: 'rejected' as const, reason: 'empty_name' as const }
      const current = context.published_outputs[index]
      if (current.name === next) return { status: 'unchanged' as const }
      const duplicate = [...(context.published_inputs ?? []), ...context.published_outputs]
        .some((item: any) => item !== current && item.name === next)
      if (duplicate) {
        return { status: 'rejected' as const, reason: 'duplicate_name' as const, name: next }
      }
      context.published_outputs = context.published_outputs.map((item: any, itemIndex: number) => (
        itemIndex === index ? { ...item, name: next } : item
      ))
      return { status: 'changed' as const }
    },
    updateParameter: (nodeId, key, value) => {
      const node = uiStore.graphNodes.find((candidate: any) => candidate.id === nodeId)
      if (!node?.data) return false
      node.data.parameters = {
        ...node.data.parameters,
        [key]: value,
      }
      node.data.status = 'unexecuted'
      node.data.provisional = true
      return true
    },
  })
  canvasSessionRegistry.activate(canvasId)

  if (nodeData) {
    const nodeId = 'node-1'
    uiStore.setCanvasSelectedNodes(canvasId, [nodeId])
    uiStore.setCanvasGraphNodes(canvasId, [{ id: nodeId, data: nodeData }])
  }
  useExecutionStore(pinia).state = executionPhase as any

  const wrapper = mount(NodePanel, {
    global: {
      plugins: [pinia, PrimeVue],
    },
  })
  setActivePinia(pinia)
  return wrapper
}

describe('NodePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    _resetCanvasCommandsForTest()
    resetFieldFocusForTests()
    mountedCanvasIndex = 0
    for (const command of Object.values(nodeEditCommandCalls)) command.mockClear()
  })

  it('reports parameter focus with the active canvas identity', async () => {
    const w = mountPanel(makeNodeData())
    const tracker = useFieldFocusTracker()
    const canvasId = canvasIdFromPanelId('node-panel:test-0')
    const sigmaRow = w.findAll('.param-row').find(row => row.text().includes('sigma'))

    expect(sigmaRow).toBeDefined()
    await sigmaRow!.trigger('focusin')
    expect(tracker.focusedFields(canvasId, 'node-1')).toEqual([{
      canvasId,
      nodeId: 'node-1',
      fieldName: 'sigma',
    }])

    await sigmaRow!.trigger('focusout', { relatedTarget: null })
    expect(tracker.focusedFields(canvasId, 'node-1')).toEqual([])
    w.unmount()
  })

  it('clears tracked parameter focus when the selection changes without focusout', async () => {
    const w = mountPanel(makeNodeData())
    const tracker = useFieldFocusTracker()
    const canvasId = canvasIdFromPanelId('node-panel:test-0')
    const sigmaRow = w.findAll('.param-row').find(row => row.text().includes('sigma'))

    await sigmaRow!.trigger('focusin')
    expect(tracker.isAnyFocused(canvasId, 'node-1')).toBe(true)
    useUIStore().setCanvasSelectedNodes(canvasId, [])
    await w.vm.$nextTick()

    expect(tracker.isAnyFocused(canvasId, 'node-1')).toBe(false)
    w.unmount()
  })

  it('does not let a stale focusout blur the newly selected node', async () => {
    const w = mountPanel(makeNodeData())
    const tracker = useFieldFocusTracker()
    const ui = useUIStore()
    const canvasId = canvasIdFromPanelId('node-panel:test-0')
    const staleSigmaRow = w.findAll('.param-row').find(row => row.text().includes('sigma'))!

    await staleSigmaRow.trigger('focusin')
    ui.setCanvasGraphNodes(canvasId, [
      { id: 'node-1', data: makeNodeData() },
      { id: 'node-2', data: makeNodeData({ name: 'Blur 2' }) },
    ])
    ui.setCanvasSelectedNodes(canvasId, ['node-2'])
    await w.vm.$nextTick()
    const nextTarget = { canvasId, nodeId: 'node-2', fieldName: 'sigma' }
    tracker.trackFocus(nextTarget)

    await staleSigmaRow.trigger('focusout', { relatedTarget: null })

    expect(tracker.focusedFields(canvasId, 'node-2')).toEqual([nextTarget])
    w.unmount()
  })

  it('clears tracked parameter focus when the panel unmounts', async () => {
    const w = mountPanel(makeNodeData())
    const tracker = useFieldFocusTracker()
    const canvasId = canvasIdFromPanelId('node-panel:test-0')
    const sigmaRow = w.findAll('.param-row').find(row => row.text().includes('sigma'))!

    await sigmaRow.trigger('focusin')
    w.unmount()

    expect(tracker.focusedFields(canvasId, 'node-1')).toEqual([])
  })

  // --- Empty state ---

  it('shows empty state when no node selected', () => {
    const w = mountPanel()
    expect(w.find('.empty-state').exists()).toBe(true)
    expect(w.find('.empty-state').text()).toContain('Select a node')
  })

  it('renders the selected node from the explicitly active canvas', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
    const ui = useUIStore()
    ui.setCanvasSelectedNodes(canvasA, ['shared'])
    ui.setCanvasGraphNodes(canvasA, [{
      id: 'shared',
      data: makeNodeData({ name: 'Node A' }),
    }])
    ui.setCanvasSelectedNodes(canvasB, ['shared'])
    ui.setCanvasGraphNodes(canvasB, [{
      id: 'shared',
      data: makeNodeData({ name: 'Node B' }),
    }])
    canvasSessionRegistry.activate(canvasA)
    const w = mount(NodePanel, {
      global: { plugins: [pinia, PrimeVue] },
    })

    expect(w.find('.node-name').text()).toBe('Node A')
    canvasSessionRegistry.activate(canvasB)
    await w.vm.$nextTick()
    expect(w.find('.node-name').text()).toBe('Node B')
    w.unmount()
  })

  // --- Fix 12: Enable/Disable toggle ---

  describe('enable/disable toggle', () => {
    it('renders the enabled toggle switch', () => {
      const w = mountPanel(makeNodeData())
      expect(w.find('[data-testid="node-enabled-toggle"]').exists()).toBe(true)
    })

    it('reflects the enabled state', () => {
      const data = makeNodeData({ enabled: true })
      const w = mountPanel(data)
      const toggle = w.find('[data-testid="node-enabled-toggle"]')
      expect(toggle.exists()).toBe(true)
    })

    it('routes enabled changes through the active canvas command', async () => {
      const data = makeNodeData({ enabled: true })
      const w = mountPanel(data)

      w.findComponent({ name: 'ToggleSwitch' }).vm.$emit('update:modelValue', false)
      await w.vm.$nextTick()

      expect(nodeEditCommandCalls.setNodeEnabled).toHaveBeenCalledWith('node-1', false)
      expect(data.enabled).toBe(false)
    })
  })

  describe('node rename', () => {
    it('routes the requested display name through the active canvas command', async () => {
      const data = makeNodeData()
      const w = mountPanel(data)

      await w.find('.node-name').trigger('dblclick')
      await w.find('.name-input').setValue('Renamed node')
      await w.find('.name-input').trigger('blur')
      await w.vm.$nextTick()

      expect(nodeEditCommandCalls.renameNode).toHaveBeenCalledWith('node-1', 'Renamed node')
      expect(data.name).toBe('Renamed node')
    })
  })

  // --- Fix 13: Package + version display ---

  describe('package info', () => {
    it('displays package name and version', () => {
      const w = mountPanel(makeNodeData())
      const pkgInfo = w.find('.package-info')
      expect(pkgInfo.exists()).toBe(true)
      expect(pkgInfo.text()).toContain('bioimageflow-core')
      expect(pkgInfo.text()).toContain('v0.3.2')
    })
  })

  // --- Fix 14: Collapsible documentation ---

  describe('documentation panel', () => {
    it('renders the documentation panel when tool has documentation', () => {
      const w = mountPanel(makeNodeData())
      expect(w.find('[data-testid="doc-panel"]').exists()).toBe(true)
    })

    it('does not render documentation panel when tool has no documentation', () => {
      const tool = makeTool({ documentation: '' })
      const w = mountPanel(makeNodeData({ tool }))
      expect(w.find('[data-testid="doc-panel"]').exists()).toBe(false)
    })
  })

  // --- Fix 15: Reset to default button ---

  describe('reset to default', () => {
    it('renders reset buttons for each parameter', () => {
      const w = mountPanel(makeNodeData())
      const resetButtons = w.findAll('[data-testid="reset-default"]')
      expect(resetButtons.length).toBeGreaterThan(0)
    })

    it('resets parameter to default value when clicked', async () => {
      const data = makeNodeData()
      data.parameters.sigma = 5.0
      const w = mountPanel(data)
      const resetButtons = w.findAll('[data-testid="reset-default"]')
      // The sigma reset button (second param row since image is first)
      const sigmaReset = resetButtons[1]
      await sigmaReset.trigger('click')
      expect(data.parameters.sigma).toBe(1.0)
    })

    it.each(['starting', 'running', 'stopping'] as const)(
      'makes NodePanel edit controls read-only while execution is %s',
      async (phase) => {
      const w = mountPanel(makeNodeData(), phase)
      await w.vm.$nextTick()

      expect((w.vm as any).isNodeEditingDisabled).toBe(true)
      for (const reset of w.findAll('[data-testid="reset-default"]')) {
        expect(reset.attributes('disabled')).toBeDefined()
      }
      expect(w.find('.param-number input').attributes('disabled')).toBeDefined()
      expect(
        w.find('[data-testid="node-enabled-toggle"]').find('input').attributes('disabled'),
      ).toBeDefined()
      expect(w.find('[data-testid="pin-toggle"]').attributes('disabled')).toBeDefined()
      expect(
        w.find('[data-testid="output-template"]').attributes('disabled'),
      ).toBeDefined()

      await w.find('.node-name').trigger('dblclick')
      expect(w.find('.name-input').exists()).toBe(false)
      expect(nodeEditCommandCalls.renameNode).not.toHaveBeenCalled()
      },
    )
  })

  // --- Fix 16: None toggle for nullable fields ---

  describe('none toggle for nullable fields', () => {
    it('renders none toggle only for nullable fields', () => {
      const w = mountPanel(makeNodeData())
      const noneToggles = w.findAll('[data-testid="none-toggle"]')
      // Only `threshold` is nullable; `sigma` has a default but is non-nullable.
      expect(noneToggles.length).toBe(1)
    })

    it('does not render the toggle for a non-nullable field with a default', () => {
      // Regression: prior to nullable, ANY field with a default got the toggle —
      // which would crash the tool when the user nulled e.g. Atlas's `gaussian_std: int = 60`.
      const tool = makeTool({
        inputs: {
          k: { type: 'int', required: false, nullable: false, connectable: 'never', default: 5 },
        },
      })
      const w = mountPanel(makeNodeData({ tool, parameters: { k: 5 } }))
      expect(w.findAll('[data-testid="none-toggle"]').length).toBe(0)
    })

    it('renders the toggle for a nullable required field (no default)', () => {
      // `int | None` with no default: user must pass *something*, but None is acceptable.
      const tool = makeTool({
        inputs: {
          t: { type: 'int', required: true, nullable: true, connectable: 'never' },
        },
      })
      const w = mountPanel(makeNodeData({ tool, parameters: {} }))
      expect(w.findAll('[data-testid="none-toggle"]').length).toBe(1)
    })

    it('sets parameter to null when toggled via click', async () => {
      const data = makeNodeData()
      data.parameters.threshold = 0.5
      const w = mountPanel(data)
      const noneToggle = w.find('[data-testid="none-toggle"]')
      await noneToggle.trigger('click')
      await w.vm.$nextTick()
      expect(data.parameters.threshold).toBe(null)
    })

    it('toggles between pencil and Ø (pi-ban) icons based on null state', async () => {
      // Icons reflect the action that will happen on click, not the
      // current state — so an editable field shows Ø (click to nullify)
      // and a nulled field shows pencil (click to edit).
      const data = makeNodeData()
      data.parameters.threshold = 0.5
      const w = mountPanel(data)
      const noneToggle = w.find('[data-testid="none-toggle"]')
      // Editable: Ø (pi-ban)
      expect(noneToggle.html()).toContain('pi-ban')
      await noneToggle.trigger('click')
      await w.vm.$nextTick()
      // Nulled: pencil
      expect(noneToggle.html()).toContain('pi-pencil')
    })
  })

  // --- Fix 17: Connectable/Pin checkbox ---

  describe('pin toggle for connectable fields', () => {
    it('renders pin toggle only for connectable fields', () => {
      const w = mountPanel(makeNodeData())
      const pinToggles = w.findAll('[data-testid="pin-toggle"]')
      // 'image' is connectable
      expect(pinToggles.length).toBe(1)
    })

    it('toggles the pinned state via component event', async () => {
      const data = makeNodeData()
      data.pinnedInputs = { image: true }
      const w = mountPanel(data)
      const pinToggle = w.find('[data-testid="pin-toggle"]')
      await pinToggle.trigger('click')
      await w.vm.$nextTick()
      expect(nodeEditCommandCalls.setInputPinned).toHaveBeenCalledWith('node-1', 'image', false)
      expect(data.pinnedInputs.image).toBe(false)
    })

    it('does not hide a currently connected input pin', async () => {
      const data = makeNodeData({
        connectedInputs: { image: 'Source.result' },
        pinnedInputs: { image: false },
      })
      const w = mountPanel(data)
      const pinToggle = w.find('[data-testid="pin-toggle"]')

      expect(pinToggle.attributes('aria-pressed')).toBe('true')
      await pinToggle.trigger('click')
      await w.vm.$nextTick()

      expect(nodeEditCommandCalls.setInputPinned).toHaveBeenCalledWith('node-1', 'image', false)
      expect(data.pinnedInputs.image).toBe(true)
    })

    it('treats both by_default and not_by_default as connectable (pin visible)', () => {
      const tool = makeTool({
        inputs: {
          a: { type: 'float', required: true, nullable: false, connectable: 'by_default' },
          b: { type: 'float', required: true, nullable: false, connectable: 'not_by_default' },
          c: { type: 'float', required: true, nullable: false, connectable: 'never' },
        },
      })
      const data = makeNodeData({ tool, pinnedInputs: { a: true, b: true } })
      const w = mountPanel(data)
      // Per the T6 decision: treat both by_default and not_by_default as
      // connectable and always show the pin. `never` hides it.
      expect(w.findAll('[data-testid="pin-toggle"]').length).toBe(2)
    })
  })

  describe('new wire-format fields', () => {
    it('accepts image_spec and new field shape', () => {
      const tool = makeTool({
        inputs: {
          mask: {
            type: 'ImageFile',
            required: true,
            nullable: false,
            connectable: 'by_default',
            display_name: 'Input mask',
            description: 'Binary mask',
            image_spec: {
              semantics: ['binary'],
              layouts: ['YX', 'ZYX'],
              dtypes: [],
              formats: [],
            },
          },
        },
      })
      const data = makeNodeData({ tool, pinnedInputs: { mask: true } })
      const w = mountPanel(data)
      // Field renders with a pin toggle (connectable !== 'never').
      expect(w.findAll('[data-testid="pin-toggle"]').length).toBe(1)
    })
  })

  // --- Fix 18: Always-visible help text ---

  describe('parameter help text', () => {
    it('does not render help toggle buttons for field descriptions', () => {
      const w = mountPanel(makeNodeData())
      const helpToggles = w.findAll('[data-testid="help-toggle"]')
      expect(helpToggles.length).toBe(0)
    })

    it('shows parameter descriptions by default', () => {
      const w = mountPanel(makeNodeData())
      const helpTexts = w.findAll('[data-testid="param-help-text"]')
      expect(helpTexts.length).toBe(3)
      expect(w.text()).toContain('Input image path')
      expect(w.text()).toContain('Blur strength')
      expect(w.text()).toContain('Optional threshold')
    })
  })

  // --- Fix 19: Output template editing ---

  describe('output template editing', () => {
    it('renders editable template inputs for path-typed outputs', () => {
      const w = mountPanel(makeNodeData())
      const templateInputs = w.findAll('[data-testid="output-template"]')
      // Both result (ImageFile) and mask (MaskPath) are path-typed
      expect(templateInputs.length).toBe(2)
    })

    it('does not render template input for non-path outputs', () => {
      const tool = makeTool({
        outputs: {
          count: { type: 'int' },
          label: { type: 'str' },
        },
      })
      const w = mountPanel(makeNodeData({ tool, output_templates: {} }))
      const templateInputs = w.findAll('[data-testid="output-template"]')
      expect(templateInputs.length).toBe(0)
    })

    it('does not render template input for DataFrameTool path outputs (column declarations)', () => {
      // DataFrameTool Outputs are column declarations, not file paths.
      // Files (a source DataFrameTool) declares `path: Path` to enable
      // downstream column-ref validation — it must NOT render a template editor.
      const tool = makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        inputs: {
          path: { type: 'Path', required: true, nullable: false, connectable: 'never', description: 'Directory' },
          pattern: { type: 'str', required: false, nullable: false, connectable: 'never', default: '*' },
        },
        outputs: {
          path: { type: 'Path' },
          filename: { type: 'str' },
        },
      })
      const w = mountPanel(makeNodeData({ tool, output_templates: {} }))
      const templateInputs = w.findAll('[data-testid="output-template"]')
      expect(templateInputs.length).toBe(0)
    })

    it('routes template values through the active canvas command', async () => {
      const data = makeNodeData()
      const w = mountPanel(data)

      await w.findAll('[data-testid="output-template"]')[0].setValue('/tmp/result.tif')
      await w.vm.$nextTick()

      expect(nodeEditCommandCalls.setOutputTemplate).toHaveBeenCalledWith(
        'node-1',
        'result',
        '/tmp/result.tif',
      )
      expect(data.output_templates.result).toBe('/tmp/result.tif')
    })
  })

  describe('sub-workflow publishing controls', () => {
    it('shows publishing controls for a normal workflow context and only publishes connectable inputs', async () => {
      const data = makeNodeData({
        publicationContext: {
          published_inputs: [],
          published_outputs: [],
        },
      })
      const w = mountPanel(data)

      const inputButtons = w.findAll('[data-testid="publish-input-toggle"]')
      expect(inputButtons).toHaveLength(1)
      expect(w.find('[data-testid="publish-output-toggle-result"]').exists()).toBe(true)
      expect(w.find('[data-testid="publish-output-toggle-mask"]').exists()).toBe(true)

      await inputButtons[0].trigger('click')
      await w.vm.$nextTick()

      expect(nodeEditCommandCalls.togglePublishedInput).toHaveBeenCalledWith(
        'node-1',
        'image',
      )
      expect((data as any).publicationContext.published_inputs).toEqual([
        expect.objectContaining({
          name: 'node-1.image',
          internal_node_id: 'node-1',
          internal_field: 'image',
          kind: 'input',
        }),
      ])
      expect((data as any).publicationContext.published_inputs[0].schema)
        .toStrictEqual(data.tool.inputs.image)
      expect(w.find('[data-testid="published-input-name-image"]').exists()).toBe(true)
      expect(w.find('[data-testid="published-input-name-sigma"]').exists()).toBe(false)
    })

    it('publishes and unpublishes an internal parameter with a stable default name', async () => {
      const data = makeNodeData({
        subWorkflowContext: {
          parentNodeId: 'sub_1',
          published_inputs: [],
          published_outputs: [],
        },
      })
      const w = mountPanel(data)

      const buttons = w.findAll('[data-testid="publish-input-toggle"]')
      const imageButton = buttons[0]
      await imageButton.trigger('click')
      await w.vm.$nextTick()

      expect(nodeEditCommandCalls.togglePublishedInput).toHaveBeenCalledWith(
        'node-1',
        'image',
      )

      expect((data as any).subWorkflowContext.published_inputs).toEqual([
        expect.objectContaining({
          name: 'node-1.image',
          internal_node_id: 'node-1',
          internal_field: 'image',
          kind: 'input',
          schema: data.tool.inputs.image,
          default: null,
        }),
      ])
      expect(w.find('[data-testid="published-input-name-image"]').exists()).toBe(true)

      await imageButton.trigger('click')
      expect(nodeEditCommandCalls.togglePublishedInput).toHaveBeenCalledTimes(2)
      expect((data as any).subWorkflowContext.published_inputs).toEqual([])
    })

    it('prevents publishing an output with a name already used by an input', async () => {
      const data = makeNodeData({
        subWorkflowContext: {
          parentNodeId: 'sub_1',
          published_inputs: [{
            name: 'node-1.result',
            internal_node_id: 'node-1',
            internal_field: 'sigma',
            kind: 'parameter',
            schema: {},
            default: 1.0,
          }],
          published_outputs: [],
        },
      })
      const w = mountPanel(data)

      await w.find('[data-testid="publish-output-toggle-result"]').trigger('click')

      expect(nodeEditCommandCalls.togglePublishedOutput).toHaveBeenCalledWith(
        'node-1',
        'result',
      )
      expect((data as any).subWorkflowContext.published_outputs).toEqual([])
      expect(w.find('[data-testid="publish-name-error"]').text()).toContain('already used')
    })

    it('routes published names and surfaces duplicate and empty-name results', async () => {
      const data = makeNodeData({
        publicationContext: {
          published_inputs: [{
            name: 'input_image',
            internal_node_id: 'node-1',
            internal_field: 'image',
            kind: 'input',
            schema: {},
            default: null,
          }],
          published_outputs: [{
            name: 'result_path',
            internal_node_id: 'node-1',
            internal_output: 'result',
            schema: {},
          }],
        },
      })
      const w = mountPanel(data)
      const inputName = w.find('[data-testid="published-input-name-image"]')
      const outputName = w.find('[data-testid="published-output-name-result"]')

      await inputName.setValue('  source_image  ')
      await w.vm.$nextTick()
      expect(nodeEditCommandCalls.renamePublishedInput).toHaveBeenCalledWith(
        'node-1',
        'image',
        '  source_image  ',
      )
      expect((data as any).publicationContext.published_inputs[0].name)
        .toBe('source_image')
      expect(w.find('[data-testid="publish-name-error"]').exists()).toBe(false)

      await outputName.setValue('source_image')
      await w.vm.$nextTick()
      expect(nodeEditCommandCalls.renamePublishedOutput).toHaveBeenCalledWith(
        'node-1',
        'result',
        'source_image',
      )
      expect((data as any).publicationContext.published_outputs[0].name)
        .toBe('result_path')
      expect(w.find('[data-testid="publish-name-error"]').text()).toContain('already used')

      await outputName.setValue('   ')
      await w.vm.$nextTick()
      expect(w.find('[data-testid="publish-name-error"]').text()).toContain('cannot be empty')

      await outputName.setValue('renamed_result')
      await w.vm.$nextTick()
      expect((data as any).publicationContext.published_outputs[0].name)
        .toBe('renamed_result')
      expect(w.find('[data-testid="publish-name-error"]').exists()).toBe(false)
    })

    it.each(['starting', 'running', 'stopping'] as const)(
      'disables publication toggles and names while execution is %s',
      async (phase) => {
      const data = makeNodeData({
        publicationContext: {
          published_inputs: [{
            name: 'input_image',
            internal_node_id: 'node-1',
            internal_field: 'image',
            kind: 'input',
            schema: {},
            default: null,
          }],
          published_outputs: [{
            name: 'result_path',
            internal_node_id: 'node-1',
            internal_output: 'result',
            schema: {},
          }],
        },
      })
      const w = mountPanel(data, phase)
      await w.vm.$nextTick()

      for (const toggle of w.findAll('.publish-toggle-btn')) {
        expect(toggle.attributes('disabled')).toBeDefined()
      }
      expect(
        w.find('[data-testid="published-input-name-image"]').attributes('disabled'),
      ).toBeDefined()
      expect(
        w.find('[data-testid="published-output-name-result"]').attributes('disabled'),
      ).toBeDefined()
      },
    )
  })

  // --- Path input: file/folder pickers (pywebview bridge) ---

  describe('path input widgets', () => {
    function mockPywebviewApi() {
      return {
        select_file: vi.fn(),
        select_files: vi.fn(),
        select_folder: vi.fn(),
        save_file: vi.fn(),
        set_title: vi.fn(),
        reveal_path: vi.fn(),
      }
    }

    afterEach(() => {
      delete window.pywebview
      vi.restoreAllMocks()
    })

    function makePathTool(): ToolMetadata {
      return makeTool({
        inputs: {
          input_image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default', description: 'Image file' },
          work_dir: { type: 'Path', required: true, nullable: false, connectable: 'never', description: 'Working directory' },
        },
        outputs: { result: { type: 'ImageFile' } },
      })
    }

    it('renders a text input and file button for ImageFile (non-optional, no default)', () => {
      const data = makeNodeData({ tool: makePathTool(), parameters: {}, pinnedInputs: { input_image: true } })
      const w = mountPanel(data)
      // The widget must render — previously this rendered the "null" label
      // because an undefined parameter was treated as nulled.
      expect(w.find('[data-testid="path-input-input_image"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-file-input_image"]').exists()).toBe(true)
      expect(w.find('.null-indicator').exists()).toBe(false)
    })

    it('renders both file and folder buttons for plain Path in desktop mode', () => {
      window.pywebview = { api: mockPywebviewApi() }

      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)
      expect(w.find('[data-testid="select-file-work_dir"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-folder-work_dir"]').exists()).toBe(true)
    })

    it('hides the folder button for plain Path in browser mode', () => {
      // No window.pywebview — browser mode.
      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)
      expect(w.find('[data-testid="select-file-work_dir"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-folder-work_dir"]').exists()).toBe(false)
    })

    it('renders only a file button for ImageFile (no folder button)', () => {
      const data = makeNodeData({ tool: makePathTool(), parameters: {}, pinnedInputs: { input_image: true } })
      const w = mountPanel(data)
      expect(w.find('[data-testid="select-file-input_image"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-folder-input_image"]').exists()).toBe(false)
    })

    it('calls the pywebview select_file bridge and stores the chosen path', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue('/absolute/chosen/image.tif')
      window.pywebview = { api }

      const data = makeNodeData({ tool: makePathTool(), parameters: {}, pinnedInputs: { input_image: true } })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-input_image"]').trigger('click')
      await flushPromises()

      expect(api.select_file).toHaveBeenCalledTimes(1)
      expect(data.parameters.input_image).toBe('/absolute/chosen/image.tif')
    })

    it('calls the pywebview select_folder bridge and stores the chosen path', async () => {
      const api = mockPywebviewApi()
      api.select_folder.mockResolvedValue('/absolute/chosen/dir')
      window.pywebview = { api }

      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)

      await w.find('[data-testid="select-folder-work_dir"]').trigger('click')
      await flushPromises()

      expect(api.select_folder).toHaveBeenCalledTimes(1)
      expect(data.parameters.work_dir).toBe('/absolute/chosen/dir')
    })

    it('passes image extensions to the native dialog for ImageFile fields', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue('/chosen.tif')
      window.pywebview = { api }

      const data = makeNodeData({
        tool: makePathTool(),
        parameters: {},
        pinnedInputs: { input_image: true },
      })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-input_image"]').trigger('click')
      await flushPromises()

      const [, fileTypes] = api.select_file.mock.calls[0]
      expect(fileTypes).toEqual(
        expect.arrayContaining(['*.tif', '*.tiff', '*.png', '*.jpg']),
      )
    })

    it('passes no filter for plain Path fields', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue('/chosen')
      window.pywebview = { api }

      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-work_dir"]').trigger('click')
      await flushPromises()

      const [, fileTypes] = api.select_file.mock.calls[0]
      expect(fileTypes).toEqual([])
    })

    it('does not overwrite the parameter when the user cancels the native dialog', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue(null)
      window.pywebview = { api }

      const data = makeNodeData({
        tool: makePathTool(),
        parameters: { input_image: '/existing/path.tif' },
        pinnedInputs: { input_image: true },
      })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-input_image"]').trigger('click')
      await flushPromises()

      expect(data.parameters.input_image).toBe('/existing/path.tif')
    })

    it('shows the current parameter value in the text input', () => {
      const data = makeNodeData({
        tool: makePathTool(),
        parameters: { input_image: '/preset/image.tif' },
        pinnedInputs: { input_image: true },
      })
      const w = mountPanel(data)
      const input = w
        .find('[data-testid="path-input-input_image"]')
        .find('input')
      expect((input.element as HTMLInputElement).value).toBe('/preset/image.tif')
    })
  })

  // --- Multi-selection ---

  it('shows multi-select message when multiple nodes are selected', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    uiStore.setSelectedNodes(['node-1', 'node-2'])
    uiStore.setGraphNodes([
      { id: 'node-1', data: makeNodeData() },
      { id: 'node-2', data: makeNodeData({ name: 'Blur 2' }) },
    ])
    const w = mount(NodePanel, {
      global: { plugins: [pinia, PrimeVue] },
    })
    expect(w.find('.multi-select').exists()).toBe(true)
    expect(w.find('.multi-select').text()).toContain('2 nodes selected')
  })

  describe('validation errors', () => {
    it('renders no error banner when validationResult is null', () => {
      const w = mountPanel(makeNodeData())
      expect(
        w.find('[data-testid="node-validation-errors"]').exists(),
      ).toBe(false)
    })

    it('renders error list scoped to the selected node', () => {
      // Mount first (creates pinia), then push a validation result into
      // the shared useGraphSync singleton so NodePanel can see it.
      const w = mountPanel(makeNodeData())
      const { validationResult } = useGraphSync()
      validationResult.value = {
        valid: false,
        node_statuses: {},
        errors: [
          {
            type: 'parameter_invalid',
            detail: "Input is not a valid path",
            node: 'node-1',
            edge_id: null,
            field: 'path',
          },
          {
            // Error on a different node — must be excluded.
            type: 'parameter_invalid',
            detail: 'other',
            node: 'other',
            edge_id: null,
            field: 'x',
          },
        ],
      }
      return w.vm.$nextTick().then(() => {
        const banner = w.find('[data-testid="node-validation-errors"]')
        expect(banner.exists()).toBe(true)
        expect(banner.text()).toContain('path')
        expect(banner.text()).toContain('Input is not a valid path')
        expect(banner.text()).not.toContain('other')
      })
    })

    it('banner disappears once errors are cleared', async () => {
      const w = mountPanel(makeNodeData())
      const { validationResult } = useGraphSync()
      validationResult.value = {
        valid: false,
        node_statuses: {},
        errors: [
          {
            type: 'missing_connection',
            detail: 'nope',
            node: 'node-1',
            edge_id: null,
            field: 'image',
          },
        ],
      }
      await w.vm.$nextTick()
      expect(
        w.find('[data-testid="node-validation-errors"]').exists(),
      ).toBe(true)
      validationResult.value = { valid: true, node_statuses: {}, errors: [] }
      await w.vm.$nextTick()
      expect(
        w.find('[data-testid="node-validation-errors"]').exists(),
      ).toBe(false)
    })
  })

  describe('execution output', () => {
    it('renders failed-node error and traceback from execution state', async () => {
      const w = mountPanel(makeNodeData())
      useExecutionStore().applyNodeState({
        node_id: 'node-1',
        status: 'failed',
        cached: false,
        error: 'Node failed',
        traceback: 'Traceback line 1\nTraceback line 2',
      })
      await w.vm.$nextTick()

      const error = w.find('[data-testid="node-runtime-error"]')
      expect(error.exists()).toBe(true)
      expect(error.text()).toContain('Node failed')
      expect(error.text()).toContain('Traceback line 2')
    })

    it('renders selected-node logs and hides other nodes', async () => {
      const w = mountPanel(makeNodeData())
      const logger = useLoggerStore()
      logger.addEntry({ level: 'INFO', message: 'selected log', nodeId: 'node-1', timestamp: 1 })
      logger.addEntry({ level: 'INFO', message: 'other log', nodeId: 'node-2', timestamp: 2 })
      await w.vm.$nextTick()

      const list = w.find('[data-testid="node-log-list"]')
      expect(list.text()).toContain('selected log')
      expect(list.text()).not.toContain('other log')
    })

    it('filters selected-node logs independently by level', async () => {
      const w = mountPanel(makeNodeData())
      const logger = useLoggerStore()
      logger.addEntry({ level: 'DEBUG', message: 'debug log', nodeId: 'node-1', timestamp: 1 })
      logger.addEntry({ level: 'ERROR', message: 'error log', nodeId: 'node-1', timestamp: 2 })
      await w.vm.$nextTick()

      expect(w.find('[data-testid="node-log-list"]').text()).toContain('error log')
      expect(w.find('[data-testid="node-log-list"]').text()).not.toContain('debug log')

      await w.find('[data-testid="node-log-level-DEBUG"]').trigger('click')
      expect(w.find('[data-testid="node-log-list"]').text()).toContain('debug log')
    })

    it('renders node log messages as escaped text', async () => {
      const w = mountPanel(makeNodeData())
      useLoggerStore().addEntry({
        level: 'INFO',
        message: '<script>alert(1)</script>',
        nodeId: 'node-1',
        timestamp: 1,
      })
      await w.vm.$nextTick()

      const message = w.find('[data-testid="node-log-message"]')
      expect(message.text()).toBe('<script>alert(1)</script>')
      expect(w.find('script').exists()).toBe(false)
    })
  })
})
