import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import {
  computed,
  defineComponent,
  h,
  nextTick,
  provide,
  reactive,
} from 'vue'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import InputText from 'primevue/inputtext'

vi.mock('@vue-flow/core', () => ({
  Handle: defineComponent({
    name: 'Handle',
    props: ['type', 'position', 'id'],
    template: '<div class="mock-handle vue-flow__handle" />',
  }),
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
  useVueFlow: () => ({ getEdges: computed(() => []) }),
}))

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

import type { GraphState, ToolMetadata } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import CanvasPersistenceFeedback from '@/components/canvas/CanvasPersistenceFeedback.vue'
import ToolNode from '@/components/canvas/ToolNode.vue'
import NodePanel from '@/components/panels/NodePanel.vue'
import {
  _resetCanvasCommandsForTest,
  useCanvasCommands,
} from '@/composables/useCanvasCommands'
import {
  _resetCanvasPersistenceForTest,
  useCanvasPersistence,
  type CanvasPersistenceApi,
  type CanvasPersistenceTransports,
} from '@/composables/useCanvasPersistence'
import {
  CANVAS_STATUS_PROJECTION_KEY,
  _resetCanvasStatusProjectionForTest,
  useCanvasStatusProjection,
  type CanvasStatusProjectionApi,
} from '@/composables/useCanvasStatusProjection'
import {
  _resetGraphSyncForTest,
  serializeGraph,
  useGraphSync,
} from '@/composables/useGraphSync'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'
import { makeRootCanvasDescriptor } from '@/test-utils/canvasFixtures'
import { deferred, type Deferred } from '@/test-utils/asyncFixtures'
import { makeGraph, makeGraphNode, makeValidationResult } from '@/test-utils/graphFixtures'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'
import { makeWorkflowDraft } from '@/test-utils/persistenceFixtures'

const WORKFLOW_ID = 'parameter-feedback'
const NODE_ID = 'files'

const tool: ToolMetadata = {
  name: 'files',
  display_name: 'Files',
  package: 'bioimageflow-core',
  package_version: '1.0.0',
  tool_type: 'ProcessingTool',
  accepts_upstream: false,
  dynamic_outputs: false,
  dataframe_output: false,
  documentation: '',
  tags: [],
  categories: [],
  inputs: {
    path: {
      type: 'Path',
      required: true,
      nullable: false,
      connectable: 'never',
    },
  },
  outputs: {},
  environment: null,
  source_kind: 'package',
  editable: false,
}

interface HarnessResources {
  persistence: CanvasPersistenceApi
  statusProjection: CanvasStatusProjectionApi
}

interface HarnessFixture {
  accepted: Deferred<WorkflowDraftResponse>
  initialDraft: WorkflowDraftResponse
  pinia: Pinia
  putDraft: ReturnType<typeof vi.fn<CanvasPersistenceTransports['putDraft']>>
  resources: HarnessResources
  wrapper: VueWrapper
}

function acceptedStatus(
  status: 'executed' | 'out_of_date',
) {
  return {
    node_id: NODE_ID,
    status,
    cached: status === 'executed',
  } as const
}

function initialGraph(): GraphState {
  return makeGraph({
    nodes: [makeGraphNode({
      type: 'tool',
      id: NODE_ID,
      name: 'Files',
      tool_name: 'files',
      parameters: { path: '/data/old' },
    })],
  })
}

function mountHarness(): HarnessFixture {
  const pinia = createPinia()
  setActivePinia(pinia)
  const accepted = deferred<WorkflowDraftResponse>()
  const graph = initialGraph()
  const initialDraft = makeWorkflowDraft({
    workflow_id: WORKFLOW_ID,
    draft_revision: 1,
    graph,
    validation: makeValidationResult({
      node_statuses: { [NODE_ID]: acceptedStatus('executed') },
    }),
  })
  const putDraft = vi.fn<CanvasPersistenceTransports['putDraft']>(
    async () => accepted.promise,
  )
  const transports: CanvasPersistenceTransports = {
    fetchDraft: vi.fn(async () => initialDraft),
    putDraft,
    writeRecovery: vi.fn(async () => {}),
  }
  const resources = {} as HarnessResources

  const Harness = defineComponent({
    name: 'ParameterEditFeedbackHarness',
    setup() {
      const descriptor = makeRootCanvasDescriptor(WORKFLOW_ID)
      const persistence = useCanvasPersistence({
        descriptor,
        getWorkflowId: () => WORKFLOW_ID,
        transports,
        debounceMs: 0,
      })
      persistence.initializeFromDraft(initialDraft)
      const graphSync = useGraphSync({
        descriptor,
        getWorkflowId: () => WORKFLOW_ID,
      })
      const nodeData = reactive({
        nodeType: 'tool' as const,
        name: 'Files',
        toolName: 'files',
        tool,
        status: 'executed',
        parameters: { path: '/data/old' },
        resources: {},
        output_templates: {},
        collapsed: false,
        enabled: true,
        connectedInputs: {},
        pinnedInputs: {},
      })
      const canvasNodes = reactive([{
        id: NODE_ID,
        type: 'tool',
        data: nodeData,
        position: { x: 0, y: 0 },
      }])
      const statusProjection = useCanvasStatusProjection({
        descriptor,
        nodes: computed(() => canvasNodes.map(node => ({
          id: node.id,
          enabled: node.data.enabled,
        }))),
        validationResult: graphSync.validationResult,
        acceptedDraftRevision: persistence.acceptedDraftRevision,
      })
      provide(CANVAS_STATUS_PROJECTION_KEY, statusProjection)
      useCanvasCommands({
        descriptor,
        renameNode: () => false,
        setNodeEnabled: () => false,
        setInputPinned: () => false,
        setOutputTemplate: () => false,
        toggleWorkflowInput: () => ({ status: 'unchanged' }),
        toggleWorkflowOutput: () => ({ status: 'unchanged' }),
        renameWorkflowInput: () => ({ status: 'unchanged' }),
        renameWorkflowOutput: () => ({ status: 'unchanged' }),
        updateParameter: (nodeId, key, value) => {
          const node = canvasNodes.find(candidate => candidate.id === nodeId)
          if (!node) return false
          const presentationStatus = statusProjection
            .statusForNode(nodeId)
            ?.presentationStatus
          node.data.parameters = {
            ...node.data.parameters,
            [key]: value,
          }
          statusProjection.stageCurrentSemanticStatuses()
          statusProjection.stageSemanticStatus(nodeId, {
            node_id: nodeId,
            status: 'unexecuted',
            cached: false,
          }, presentationStatus)
          persistence.queueGraph(serializeGraph({ nodes: canvasNodes, edges: [] }))
          return true
        },
      })
      const ui = useUIStore()
      ui.setCanvasWorkflow(descriptor.canvasId, WORKFLOW_ID, 'Parameter feedback')
      ui.setCanvasGraphNodes(descriptor.canvasId, canvasNodes)
      ui.setCanvasSelectedNodes(descriptor.canvasId, [NODE_ID])
      canvasSessionRegistry.activate(descriptor.canvasId)
      resources.persistence = persistence
      resources.statusProjection = statusProjection

      return () => h('div', { class: 'parameter-edit-feedback-harness' }, [
        h(ToolNode, { id: NODE_ID, data: nodeData }),
        h(NodePanel),
        h(CanvasPersistenceFeedback, {
          state: persistence.persistenceState.value,
          issue: persistence.persistenceIssue.value,
        }),
      ])
    },
  })

  const wrapper = mount(Harness, {
    global: primeVueTestGlobal({ pinia }),
  })
  return { accepted, initialDraft, pinia, putDraft, resources, wrapper }
}

function visibleNodeStatus(wrapper: VueWrapper): string {
  return wrapper.get('.tool-node').classes().find(name => name.startsWith('status-'))!
}

function panelStatus(wrapper: VueWrapper): string {
  return wrapper.get('.status-badge').text()
}

async function editPath(wrapper: VueWrapper, value: string): Promise<void> {
  wrapper
    .get('[data-testid="path-input-path"]')
    .findComponent(InputText)
    .vm.$emit('update:modelValue', value)
  await nextTick()
}

async function startPersistence(
  fixture: HarnessFixture,
): Promise<{ result: Promise<unknown> }> {
  const result = fixture.resources.persistence.flush().catch(error => error)
  await flushPromises()
  expect(fixture.putDraft).toHaveBeenCalledOnce()
  return { result }
}

describe('parameter-edit semantic and persistence feedback', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    _resetCanvasPersistenceForTest()
    _resetCanvasCommandsForTest()
    _resetCanvasStatusProjectionForTest()
    vi.useFakeTimers()
  })

  afterEach(() => {
    canvasSessionRegistry.dispose()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('keeps visible status stable until delayed acceptance then transitions once', async () => {
    const fixture = mountHarness()
    const visibleSequence = [visibleNodeStatus(fixture.wrapper)]
    const panelSequence = [panelStatus(fixture.wrapper)]

    await editPath(fixture.wrapper, '/data/new')
    visibleSequence.push(visibleNodeStatus(fixture.wrapper))
    panelSequence.push(panelStatus(fixture.wrapper))

    expect(fixture.resources.statusProjection.statusForNode(NODE_ID)).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(fixture.wrapper.get('.tool-node').classes()).not.toContain('provisional')
    expect(fixture.wrapper.text()).not.toContain('provisional')
    expect(fixture.resources.persistence.persistenceState.value).toBe('saving')

    const { result: persistenceResult } = await startPersistence(fixture)
    await vi.advanceTimersByTimeAsync(200)
    expect(fixture.wrapper.get('[data-testid="canvas-persistence-saving"]').text())
      .toBe('Saving…')
    expect(visibleNodeStatus(fixture.wrapper)).toBe('status-executed')
    expect(panelStatus(fixture.wrapper)).toBe('executed')

    const queuedGraph = fixture.putDraft.mock.calls[0]![1].graph
    fixture.accepted.resolve(makeWorkflowDraft({
      ...fixture.initialDraft,
      draft_revision: 2,
      dirty_against_saved: true,
      graph: queuedGraph,
      validation: makeValidationResult({
        node_statuses: { [NODE_ID]: acceptedStatus('out_of_date') },
      }),
    }))
    await persistenceResult
    await nextTick()
    visibleSequence.push(visibleNodeStatus(fixture.wrapper))
    panelSequence.push(panelStatus(fixture.wrapper))

    expect(fixture.resources.statusProjection.statusForNode(NODE_ID)).toMatchObject({
      status: 'out_of_date',
      presentationStatus: 'out_of_date',
      source: 'validation',
    })
    expect(visibleSequence).toEqual([
      'status-executed',
      'status-executed',
      'status-out-of-date',
    ])
    expect(panelSequence).toEqual(['executed', 'executed', 'out_of_date'])
    const feedback = fixture.wrapper.getComponent(CanvasPersistenceFeedback)
    expect(feedback.text()).toBe('')
    expect(feedback.find('[role="status"]').exists()).toBe(false)
    expect(feedback.find('[role="alert"]').exists()).toBe(false)
    fixture.wrapper.unmount()
  })

  it('keeps the node understandable and the failed-save message durable', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const fixture = mountHarness()
    await editPath(fixture.wrapper, '/data/new')
    const { result: persistenceResult } = await startPersistence(fixture)

    fixture.accepted.reject(new Error('network unavailable'))
    await persistenceResult
    await nextTick()

    expect(fixture.resources.statusProjection.statusForNode(NODE_ID)).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(visibleNodeStatus(fixture.wrapper)).toBe('status-executed')
    expect(panelStatus(fixture.wrapper)).toBe('executed')
    expect(fixture.wrapper.get('.tool-node').classes()).not.toContain('provisional')
    const issue = fixture.wrapper.get('[data-testid="canvas-persistence-issue"]')
    expect(issue.text()).toContain('Changes could not be saved')
    expect(issue.text()).toContain('still queued on this canvas')
    expect(issue.text()).toContain('network unavailable')
    expect(issue.attributes('role')).toBe('alert')
    expect(fixture.wrapper.get('[data-testid="canvas-persistence-retry"]'))
      .toBeTruthy()

    await vi.advanceTimersByTimeAsync(60_000)
    expect(fixture.wrapper.get('[data-testid="canvas-persistence-issue"]').text())
      .toContain('network unavailable')
    expect(warning).toHaveBeenCalledWith(
      '[canvas-persistence] Failed to save workflow draft:',
      expect.objectContaining({ message: 'network unavailable' }),
    )
    fixture.wrapper.unmount()
  })
})
