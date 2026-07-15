<script setup lang="ts">
import { computed, ref, watch, markRaw, nextTick, onMounted, onBeforeUnmount, provide } from 'vue'
import { VueFlow, useVueFlow, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import ToolNode from './ToolNode.vue'
import ColumnRefEdge from './ColumnRefEdge.vue'
import PositionalEdge from './PositionalEdge.vue'
import CanvasErrorBanner from './CanvasErrorBanner.vue'
import NodeContextMenu from './NodeContextMenu.vue'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useUIStore } from '@/stores/ui'
import { generateNodeId, generateNodeName } from '@/utils/nodeIdGenerator'
import {
  getMemoryClipboardPayload,
  prepareClipboardPaste,
  readClipboardPayloadResult,
  serializeGraphSelection,
  writeClipboardPayload,
} from '@/utils/clipboard'
import { useUndoRedo } from '@/composables/useUndoRedo'
import { serializeGraph, useGraphSync } from '@/composables/useGraphSync'
import { useCanvasPersistence } from '@/composables/useCanvasPersistence'
import { useCanvasCommands } from '@/composables/useCanvasCommands'
import { useAutoSave } from '@/composables/useAutoSave'
import { useExecutionLock } from '@/composables/useExecutionLock'
import { useStatusReconciliation, type NodeStateMessage } from '@/composables/useStatusReconciliation'
import { useValidationErrors } from '@/composables/useValidationErrors'
import { useErrorReporting } from '@/composables/useErrorReporting'
import { useHotReload } from '@/composables/useHotReload'
import { useExecutionStore } from '@/stores/execution'
import { useDataTableStore } from '@/stores/dataTable'
import { useResolvedOutputsStore } from '@/stores/resolvedOutputs'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { graphStateToVueFlow } from '@/utils/workflowGraph'
import { reconcileOutputTemplates } from '@/utils/outputTemplates'
import { createSubWorkflowFromSelection } from '@/utils/subWorkflow'
import type { GraphState, MissingTool, NodeState, PublishedInput, PublishedOutput, WorkflowInfo } from '@/api/types'
import { api } from '@/api/client'
import { useToast } from 'primevue/usetoast'
import type { ClipboardPayload, PasteSummary } from '@/utils/clipboard'
import type { ToolMetadata } from '@/api/types'
import { useSubWorkflowSessionsStore } from '@/stores/subWorkflowSessions'
import {
  canvasIdFromPanelId,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'

const emit = defineEmits<{
  'graph-changed': [payload: { nodes: any[]; edges: any[] }]
  'node-selected': [nodeIds: string[]]
}>()

const props = defineProps<{
  subWorkflowSessionId?: string
  parentCanvasPanelId?: string
  params?: {
    panelId?: string
    parentCanvasPanelId?: string
    workflowName?: string
    workflowDisplayName?: string
    graph?: GraphState
    missingTools?: MissingTool[]
    dirty?: boolean
    params?: {
      panelId?: string
      parentCanvasPanelId?: string
      workflowName?: string
      workflowDisplayName?: string
      graph?: GraphState
      missingTools?: MissingTool[]
      dirty?: boolean
    }
  }
}>()

// Vue Flow's NodeTypesObject/EdgeTypesObject uses very strict component
// constraints that Vue's SFC-inferred types don't satisfy. The runtime
// contract (`key -> component`) is what VueFlow actually uses.
const nodeTypes = {
  tool: markRaw(ToolNode),
  sub_workflow: markRaw(ToolNode),
} as unknown as Record<string, object>

const edgeTypes = {
  column_ref: markRaw(ColumnRefEdge),
  positional: markRaw(PositionalEdge),
} as unknown as Record<string, object>

const toolRegistryStore = useToolRegistryStore()
const uiStore = useUIStore()
const workflowStore = useWorkflowStore()
const workflowDraftStore = useWorkflowDraftStore()
const subWorkflowSessionsStore = useSubWorkflowSessionsStore()
const autoSave = useAutoSave()
const resolvedOutputsStore = useResolvedOutputsStore()
const dataTableStore = useDataTableStore()
const isSubWorkflowEditor = props.subWorkflowSessionId != null && props.subWorkflowSessionId !== ''
const canvasPanelId = componentPanelId()
const canvasId = canvasIdFromPanelId(canvasPanelId)
const initialCanvasParams = dockviewParams()
const initialNestedSession = props.subWorkflowSessionId
  ? subWorkflowSessionsStore.sessionById(props.subWorkflowSessionId)
  : null
const ownedWorkflowName = ref<string | null>(
  isSubWorkflowEditor
    ? initialNestedSession?.parentWorkflowName ?? null
    : initialCanvasParams?.workflowName ?? workflowStore.currentName ?? null,
)
const ownedWorkflowDisplayName = ref<string | null>(
  isSubWorkflowEditor
    ? initialNestedSession?.parentNodeName ?? null
    : initialCanvasParams?.workflowDisplayName
      ?? workflowStore.current?.display_name
      ?? null,
)

// ToolNode must always read the map owned by this mounted canvas.
const canvasResolvedOutputs = resolvedOutputsStore.resolvedOutputsForCanvas(canvasId)
provide('bioimageflow:resolvedOutputs', canvasResolvedOutputs)

const {
  project,
  addNodes,
  addEdges,
  removeNodes,
  removeEdges,
  getNodes,
  getEdges,
  setNodes,
  setEdges,
  updateEdge,
  onConnect,
  onNodesChange,
  onEdgeUpdate,
  onEdgeUpdateEnd,
  onNodeDragStart,
  onNodeDragStop,
  fitView,
} = useVueFlow(canvasPanelId)

const canvasDescriptor: CanvasSessionDescriptor = isSubWorkflowEditor
    ? {
        kind: 'nested',
        canvasId,
        sessionId: props.subWorkflowSessionId!,
        parentCanvasId: canvasIdFromPanelId(
          props.parentCanvasPanelId
          ?? initialCanvasParams?.parentCanvasPanelId
          ?? 'canvas',
        ),
      }
    : {
        kind: 'root',
        canvasId,
        workflowId: initialCanvasParams?.workflowName ?? null,
      }
const graphSync = useGraphSync({
  descriptor: canvasDescriptor,
  getWorkflowId: owningWorkflowId,
})
const canvasPersistence = useCanvasPersistence({
  descriptor: canvasDescriptor,
  getWorkflowId: owningWorkflowId,
})
const canvasCommands = useCanvasCommands({
  descriptor: canvasDescriptor,
  save: isSubWorkflowEditor ? () => saveSubWorkflowSession() : undefined,
})
uiStore.setCanvasWorkflow(
  canvasId,
  ownedWorkflowName.value,
  ownedWorkflowDisplayName.value,
)
uiStore.setCanvasGraphNodes(canvasId, getNodes.value)
const {
  syncGraph,
  syncGraphState,
  flushNow,
  validationResult,
  syncState,
  dispose: disposeGraphSync,
} = graphSync
const {
  queueGraph: queueCanvasPersistence,
  initializeFromDraft: initializeCanvasPersistenceFromDraft,
  resolveFromDraft: resolveCanvasPersistenceFromDraft,
  isPending: isCanvasPersistencePending,
  dispose: disposeCanvasPersistence,
} = canvasPersistence
const { edgeErrors } = useValidationErrors(validationResult)
const { reportError } = useErrorReporting()
const undoRedo = useUndoRedo<{ nodes: any[]; edges: any[] }>()
const { isLocked } = useExecutionLock()
const executionStore = useExecutionStore()

// Status reconciliation: mark nodes provisional during debounce; clear when
// the authoritative validation response arrives.
const reconciliationNodes = ref<NodeState[]>([])
const wsMessages = ref<NodeStateMessage[]>([])
const {
  reconciledStatuses,
  markProvisional,
  applyValidationResult,
} = useStatusReconciliation(reconciliationNodes, validationResult, wsMessages)

watch(validationResult, (result) => {
  applyValidationResult(result)
  if (!result?.node_statuses) return
  for (const node of getNodes.value) {
    const status = result.node_statuses[node.id]
    if (!status || !node.data) continue
    if (node.data.status !== status.status) {
      node.data.status = status.status
    }
    if (node.data.provisional) {
      node.data.provisional = false
    }
  }
})

// Mirror per-edge validation errors onto each edge's `data.errors` so the
// edge component can render the red stroke + tooltip.
watch(
  edgeErrors,
  (byEdge) => {
    for (const edge of getEdges.value) {
      const errs = byEdge[edge.id] ?? []
      const prev = (edge.data as { errors?: unknown[] } | undefined)?.errors ?? []
      // Cheap reference check to avoid noisy reactive churn when the result
      // hasn't changed shape.
      if (errs.length === 0 && prev.length === 0) continue
      edge.data = { ...(edge.data ?? {}), errors: errs }
    }
  },
  { deep: true },
)

// Live per-node status from the execution store takes precedence while an
// execution is running and for its terminal transition. Later idle snapshots
// must not overwrite validation for a graph edited after that execution.
watch(
  [() => executionStore.isRunning, () => executionStore.nodeStatuses],
  ([running, statuses], [wasRunning]) => {
    if (!statuses || (!running && !wasRunning)) return
    for (const node of getNodes.value) {
      const s = statuses[node.id]
      if (s && node.data && node.data.status !== s.status) {
        node.data.status = s.status
      }
    }
  },
  { deep: true },
)

const clipboardData = ref<ClipboardPayload | null>(getMemoryClipboardPayload())
const canvasRef = ref<HTMLDivElement | null>(null)
const nodeContextMenu = ref<{
  nodeId: string
  position: { x: number; y: number }
  enabled: boolean
  canOpenSubWorkflow: boolean
} | null>(null)
const dragStartPositions = ref<Record<string, { x: number; y: number }>>({})
const rootPublishedInputs = ref<PublishedInput[]>([])
const rootPublishedOutputs = ref<PublishedOutput[]>([])
const lastAuthoritativeGraph = ref<GraphState | null>(null)
const isActiveCanvasTab = ref(true)
const hasLoadedGraphState = ref(false)
const remoteDraftAction = ref<'apply' | 'keep' | 'copy' | null>(null)
const remoteDraftActionError = ref<string | null>(null)
const remoteDraftResolutionMessage = ref<string | null>(null)
let isApplyingGraphState = false
let isCanvasUnmounted = false
let isAutoApplyingRemoteDraft = false
let isRefreshingToolMetadata = false
let clipboardToast: ReturnType<typeof useToast> | null = null

const hasLocalRemoteDraftConflict = computed(() => (
  uiStore.canvasHasUnsavedChanges(canvasId) || isCanvasPersistencePending.value
))

const shouldShowRemoteDraftConflict = computed(() => {
  if (isSubWorkflowEditor) return false
  if (!isActiveCanvasTab.value) return false
  if (!hasLoadedGraphState.value) return false
  if (workflowDraftStore.remoteAvailableRevision === null) return false
  if (!hasLocalRemoteDraftConflict.value) return false
  const workflowName = workflowIdentity().workflowName
  return typeof workflowName === 'string'
    && workflowName.length > 0
    && workflowDraftStore.workflowId === workflowName
})

const isResolvingRemoteDraftConflict = computed(() => remoteDraftAction.value !== null)

const shouldFitViewOnInit = computed(() => {
  const params = dockviewParams()
  if (Array.isArray(params?.graph?.nodes)) return params.graph.nodes.length > 0
  return false
})

interface SubWorkflowApplyPayload {
  graph: GraphState
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
}

interface PublicationContext {
  parentNodeId?: string
  published_inputs: PublishedInput[]
  published_outputs: PublishedOutput[]
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function rememberAuthoritativeGraph(graph: GraphState): GraphState {
  const snapshot = deepClone(graph)
  lastAuthoritativeGraph.value = snapshot
  return snapshot
}

function graphWithAuthoritativeEdges(state: {
  nodes: any[]
  edges: any[]
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
}): GraphState {
  const graph = serializeGraph(state) as GraphState
  const previous = lastAuthoritativeGraph.value
  if (previous !== null) {
    graph.edges = deepClone(previous.edges ?? []) as GraphState['edges']
  }
  return graph
}

function dockviewParams() {
  return props.params?.params ?? props.params
}

function componentPanelId(): string {
  if (props.subWorkflowSessionId) {
    return `sub-workflow:${encodeURIComponent(props.subWorkflowSessionId)}`
  }
  return dockviewParams()?.panelId ?? 'canvas'
}

function workflowIdentity() {
  return {
    workflowName: ownedWorkflowName.value,
    workflowDisplayName: ownedWorkflowDisplayName.value,
  }
}

function owningWorkflowId(): string | null {
  if (!props.subWorkflowSessionId) return ownedWorkflowName.value
  return subWorkflowSessionsStore.sessionById(props.subWorkflowSessionId)
    ?.parentWorkflowName ?? ownedWorkflowName.value
}

function adoptRecoveredWorkflowIdentity(recovered: {
  workflowName: string
  workflowDisplayName: string
}): void {
  ownedWorkflowName.value = recovered.workflowName
  ownedWorkflowDisplayName.value = recovered.workflowDisplayName
  uiStore.setCanvasWorkflow(
    canvasId,
    recovered.workflowName,
    recovered.workflowDisplayName,
  )
}

function workflowInfoId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

function workflowUrl(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/')
}

type GraphLike = { nodes?: unknown[] }

function nestedGraphFromNode(node: any): GraphLike | null {
  const graph = node?.sub_workflow ?? node?.data?.sub_workflow
  return graph && typeof graph === 'object' ? graph as GraphLike : null
}

function sourceWorkflowNameFromNode(node: any): string | null {
  const source = node?.source_workflow_name ?? node?.data?.source_workflow_name
  return typeof source === 'string' && source.length > 0 ? source : null
}

function graphContainsWorkflow(graph: GraphLike | null | undefined, workflowName: string): boolean {
  if (!graph || !Array.isArray(graph.nodes)) return false
  for (const node of graph.nodes) {
    if (sourceWorkflowNameFromNode(node) === workflowName) return true
    if (graphContainsWorkflow(nestedGraphFromNode(node), workflowName)) return true
  }
  return false
}

function containingWorkflowNames(): string[] {
  if (!isSubWorkflowEditor) {
    const name = workflowIdentity().workflowName
    return typeof name === 'string' ? [name] : []
  }
  if (!props.subWorkflowSessionId) return []
  const session = subWorkflowSessionsStore.sessionById(props.subWorkflowSessionId)
  return [session?.parentWorkflowName, session?.parentSourceWorkflowName]
    .filter((name): name is string => typeof name === 'string' && name.length > 0)
}

function wouldCreateWorkflowContainmentCycle(workflowName: string, graph: GraphLike): boolean {
  return containingWorkflowNames().some((containerName) => (
    workflowName === containerName || graphContainsWorkflow(graph, containerName)
  ))
}

function showWorkflowContainmentError(workflowName: string): void {
  clipboardToast?.add({
    severity: 'warn',
    summary: 'Workflow cannot contain itself',
    detail: `Dropping '${workflowName}' here would create a direct or indirect workflow cycle.`,
    life: 5000,
  })
}

function currentPublicationContext(): PublicationContext | null {
  if (!isSubWorkflowEditor) {
    return {
      published_inputs: rootPublishedInputs.value,
      published_outputs: rootPublishedOutputs.value,
    }
  }
  if (!props.subWorkflowSessionId) return null
  const session = subWorkflowSessionsStore.sessionById(props.subWorkflowSessionId)
  if (!session) return null
  return {
    parentNodeId: session.parentNodeId,
    published_inputs: session.published_inputs,
    published_outputs: session.published_outputs,
  }
}

function attachPublicationContext(node: any) {
  const context = currentPublicationContext()
  if (!context) return node
  node.data ??= {}
  node.data.publicationContext = context
  if (isSubWorkflowEditor) {
    node.data.subWorkflowContext = context
  }
  return node
}

function attachPublicationContextToNodes(nodes: any[]) {
  return nodes.map((node) => attachPublicationContext(node))
}

// --- Workflow startup / graph application ---

async function applyGraphState(
  graph: GraphState,
  missingTools: MissingTool[] = [],
  dirty = false,
) {
  if (isCanvasUnmounted) return
  if (!isSubWorkflowEditor) {
    rootPublishedInputs.value = deepClone(graph.published_inputs ?? []) as PublishedInput[]
    rootPublishedOutputs.value = deepClone(graph.published_outputs ?? []) as PublishedOutput[]
  }
  const vueFlowGraph = graphStateToVueFlow(
    graph,
    toolRegistryStore.getToolByName,
    missingTools,
  )
  attachPublicationContextToNodes(vueFlowGraph.nodes)
  isApplyingGraphState = true
  try {
    setNodes([])
    setEdges([])
    await nextTick()
    if (isCanvasUnmounted) return
    setNodes(vueFlowGraph.nodes)
    // Wait for node components (and their <Handle> DOM elements) to mount
    // before setting edges — Vue Flow resolves edge endpoints against live
    // handle elements, so edges added in the same tick as nodes render with
    // no visible path.
    await nextTick()
    if (isCanvasUnmounted) return
    setEdges(vueFlowGraph.edges)
    if (isCanvasUnmounted) return
    syncGraphState(rememberAuthoritativeGraph(graph))
    if (!isSubWorkflowEditor) {
      const identity = workflowIdentity()
      uiStore.setCanvasWorkflow(
        canvasId,
        identity.workflowName,
        identity.workflowDisplayName,
      )
      window.dispatchEvent(new CustomEvent('bioimageflow:canvas-context-updated', {
        detail: {
          panelId: componentPanelId(),
          workflowName: identity.workflowName,
          workflowDisplayName: identity.workflowDisplayName,
        },
      }))
      if (dirty) {
        uiStore.markCanvasDirty(canvasId)
      } else {
        uiStore.markCanvasClean(canvasId)
      }
    }
  } finally {
    isApplyingGraphState = false
  }
}

async function ensureDefaultWorkflow() {
  const base = 'Untitled'
  const names = new Set(workflowStore.workflows.map((workflow) => workflowInfoId(workflow)))
  let name = base
  let suffix = 2
  while (names.has(name)) {
    name = `${base}_${suffix}`
    suffix += 1
  }
  const workflow = await workflowStore.createWorkflow(
    { name, display_name: name },
    canvasId,
  )
  const workflowName = workflowInfoId(workflow)
  const draft = await workflowDraftStore.loadDraft(workflowName).catch(() => null)
  if (draft !== null) initializeCanvasPersistenceFromDraft(draft)
  return {
    graph: { nodes: [], edges: [] } as GraphState,
    workflowName,
    workflowDisplayName: workflow.display_name ?? workflowName,
  }
}

async function recoverStartupWorkflow() {
  await workflowStore.fetchWorkflowTree().catch(() => workflowStore.fetchWorkflows())
  let autoSaved = await autoSave.loadMostRecentAutoSave()
  const lastOpened = await autoSave.getLastOpenedWorkflow()
  const workflowNames = new Set(workflowStore.flattenedWorkflows.map((workflow) => workflowInfoId(workflow)))
  if (autoSaved !== null && !workflowNames.has(autoSaved.name)) {
    await autoSave.clearAutoSave(autoSaved.name)
    autoSaved = null
  }
  if (lastOpened !== null && !workflowNames.has(lastOpened)) {
    await autoSave.setLastOpenedWorkflow(null)
  }
  const targetName = autoSaved?.name ?? lastOpened
  const exists = targetName
    ? workflowNames.has(targetName)
    : false

  if (targetName && exists) {
    let serverGraph: GraphState
    try {
      serverGraph = await workflowStore.loadWorkflow(targetName, canvasId)
    } catch {
      await autoSave.clearAutoSave(targetName)
      await autoSave.setLastOpenedWorkflow(null)
      const fallback = await ensureDefaultWorkflow()
      return {
        ...fallback,
        dirty: false,
      }
    }
    const workflow = workflowStore.workflows.find(
      candidate => workflowInfoId(candidate) === targetName,
    )
    const serverModified = Date.parse(workflow?.last_modified ?? '')
    const draft = await workflowDraftStore.loadDraft(targetName).catch(() => null)
    if (draft !== null) initializeCanvasPersistenceFromDraft(draft)
    const draftModified = Date.parse(draft?.updated_at ?? '')
    const latestPersistedModified = Math.max(
      Number.isFinite(serverModified) ? serverModified : 0,
      Number.isFinite(draftModified) ? draftModified : 0,
    )
    const matchingAutoSave = autoSaved?.name === targetName ? autoSaved : null
    const autoSaveIsFresh =
      matchingAutoSave !== null &&
      (latestPersistedModified === 0 || matchingAutoSave.timestamp > latestPersistedModified)
    if (
      matchingAutoSave !== null &&
      Number.isFinite(serverModified) &&
      !autoSaveIsFresh
    ) {
      await autoSave.clearAutoSave(targetName)
    }
    return {
      graph: autoSaveIsFresh
        ? matchingAutoSave.graph
        : draft?.graph ?? serverGraph,
      dirty: autoSaveIsFresh || draft?.dirty_against_saved === true,
      workflowName: targetName,
      workflowDisplayName: workflow?.display_name ?? targetName,
    }
  }

  const fallback = await ensureDefaultWorkflow()
  return {
    ...fallback,
    dirty: false,
  }
}

function initialGraphFromDockviewParams(): {
  graph: GraphState
  missingTools?: MissingTool[]
  dirty?: boolean
} | null {
  const params = dockviewParams()
  if (!params?.graph) return null
  return {
    graph: params.graph,
    missingTools: params.missingTools,
    dirty: params.dirty,
  }
}

function handleCanvasTabActivatedEvent(event: Event) {
  const detail = (event as CustomEvent<{ panelId?: string }>).detail
  isActiveCanvasTab.value = detail?.panelId === componentPanelId()
  if (!isActiveCanvasTab.value) return
  trackDraftWorkflowForActiveRootCanvas()
  uiStore.setCanvasGraphNodes(canvasId, getNodes.value)
  if (lastAuthoritativeGraph.value !== null) {
    syncGraphState(lastAuthoritativeGraph.value)
  }
  void maybeApplyRemoteDraftToActiveCanvas()
}

function trackDraftWorkflowForActiveRootCanvas(): void {
  if (isSubWorkflowEditor) return
  const workflowName = workflowIdentity().workflowName
  if (typeof workflowName !== 'string' || workflowName.length === 0) return
  workflowDraftStore.trackWorkflow(workflowName)
}

function currentWorkflowName(): string | null {
  const workflowName = workflowIdentity().workflowName
  return typeof workflowName === 'string' && workflowName.length > 0
    ? workflowName
    : null
}

function currentSerializedGraph(): GraphState {
  return serializeGraph(currentVueFlowState() as any) as GraphState
}

function remoteDraftErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function showRemoteDraftActionError(summary: string, err: unknown): void {
  const detail = remoteDraftErrorMessage(err)
  remoteDraftActionError.value = detail
  clipboardToast?.add({
    severity: 'error',
    summary,
    detail,
    life: 5000,
  })
}

function markWorkflowDirtyFromDraft(dirty: boolean): void {
  if (dirty) {
    uiStore.markCanvasDirty(canvasId)
  } else {
    uiStore.markCanvasClean(canvasId)
  }
}

async function applyAgentDraftChanges(): Promise<void> {
  const workflowName = currentWorkflowName()
  if (!workflowName || isResolvingRemoteDraftConflict.value) return
  remoteDraftAction.value = 'apply'
  remoteDraftActionError.value = null
  remoteDraftResolutionMessage.value = null
  workflowDraftStore.cancelPendingSave()
  try {
    const draft = await workflowDraftStore.loadDraft(workflowName)
    await applyGraphState(
      draft.graph,
      workflowStore.missingTools,
      draft.dirty_against_saved,
    )
    resolveCanvasPersistenceFromDraft(draft)
  } catch (err) {
    showRemoteDraftActionError('Could not apply agent changes', err)
  } finally {
    remoteDraftAction.value = null
  }
}

async function keepCurrentCanvasDraft(): Promise<void> {
  const workflowName = currentWorkflowName()
  if (!workflowName || isResolvingRemoteDraftConflict.value) return
  remoteDraftAction.value = 'keep'
  remoteDraftActionError.value = null
  remoteDraftResolutionMessage.value = null
  try {
    const response = await workflowDraftStore.overwriteDraftWithGraph(
      workflowName,
      currentSerializedGraph(),
    )
    resolveCanvasPersistenceFromDraft(response)
    markWorkflowDirtyFromDraft(response.dirty_against_saved)
  } catch (err) {
    showRemoteDraftActionError('Could not keep your canvas', err)
  } finally {
    remoteDraftAction.value = null
  }
}

function nextAgentCopyWorkflowName(baseName: string): string {
  const existing = new Set(workflowStore.workflows.map((workflow) => workflowInfoId(workflow)))
  if (workflowStore.currentName) existing.add(workflowStore.currentName)
  let suffix = 2
  let name = `${baseName}_agent_${suffix}`
  while (existing.has(name)) {
    suffix += 1
    name = `${baseName}_agent_${suffix}`
  }
  return name
}

function rememberCreatedWorkflow(info: WorkflowInfo): void {
  const id = workflowInfoId(info)
  if (workflowStore.workflows.some((workflow) => workflowInfoId(workflow) === id)) return
  workflowStore.workflows = [...workflowStore.workflows, info]
}

async function saveAgentDraftAsCopy(): Promise<void> {
  const workflowName = currentWorkflowName()
  if (!workflowName || isResolvingRemoteDraftConflict.value) return
  remoteDraftAction.value = 'copy'
  remoteDraftActionError.value = null
  remoteDraftResolutionMessage.value = null
  try {
    const remoteDraft = await workflowDraftStore.fetchLatestDraft(workflowName)
    const copyName = nextAgentCopyWorkflowName(workflowName)
    const { data } = await api.post<WorkflowInfo>('/api/v1/workflows', {
      name: copyName,
      display_name: copyName,
    })
    rememberCreatedWorkflow(data)
    await api.put<WorkflowInfo>(
      `/api/v1/workflows/${workflowUrl(workflowInfoId(data))}`,
      { graph: remoteDraft.graph },
    )
    remoteDraftResolutionMessage.value = `Agent version saved as ${workflowInfoId(data)}.`
    clipboardToast?.add({
      severity: 'success',
      summary: 'Agent version saved',
      detail: workflowInfoId(data),
      life: 5000,
    })
  } catch (err) {
    showRemoteDraftActionError('Could not save agent version', err)
  } finally {
    remoteDraftAction.value = null
  }
}

function handleToolRenamedEvent(event: Event) {
  const detail = (event as CustomEvent<{ old_name: string; new_name: string }>).detail
  if (!detail?.old_name || !detail?.new_name) return
  let changed = false
  const fresh = toolRegistryStore.getToolByName(detail.new_name) ?? null
  for (const node of getNodes.value as any[]) {
    if (node.data?.toolName !== detail.old_name) continue
    node.data.toolName = detail.new_name
    node.data.tool = fresh
    node.data.output_templates = reconcileOutputTemplates(
      fresh,
      node.data.output_templates ?? {},
    )
    node.data.missingTool = null
    changed = true
  }
  if (changed) emitGraphChanged()
}

async function maybeApplyRemoteDraftToActiveCanvas(): Promise<void> {
  const remoteRevision = workflowDraftStore.remoteAvailableRevision
  if (remoteRevision === null) return
  if (!hasLoadedGraphState.value) return
  if (isSubWorkflowEditor) return
  if (!isActiveCanvasTab.value) return
  if (hasLocalRemoteDraftConflict.value) return
  if (isAutoApplyingRemoteDraft) return

  const workflowName = workflowIdentity().workflowName
  if (typeof workflowName !== 'string' || workflowName.length === 0) return
  if (workflowDraftStore.workflowId !== workflowName) return

  isAutoApplyingRemoteDraft = true
  try {
    const draft = await workflowDraftStore.loadDraft(workflowName)
    await applyGraphState(
      draft.graph,
      workflowStore.missingTools,
      draft.dirty_against_saved,
    )
    resolveCanvasPersistenceFromDraft(draft)
  } catch (err) {
    console.warn('[canvas] Failed to auto-apply remote workflow draft:', err)
  } finally {
    isAutoApplyingRemoteDraft = false
  }
}

watch(
  () => [
    workflowDraftStore.remoteAvailableRevision,
    hasLoadedGraphState.value,
    isActiveCanvasTab.value,
    hasLocalRemoteDraftConflict.value,
  ] as const,
  () => {
    void maybeApplyRemoteDraftToActiveCanvas()
  },
)

watch(
  () => workflowDraftStore.remoteAvailableRevision,
  (revision) => {
    if (revision !== null) {
      remoteDraftActionError.value = null
      remoteDraftResolutionMessage.value = null
    }
  },
)

function handleToolDeletedEvent(event: Event) {
  const detail = (event as CustomEvent<{ tool_name: string }>).detail
  if (!detail?.tool_name) return
  let changed = false
  for (const node of getNodes.value as any[]) {
    if (node.data?.toolName !== detail.tool_name) continue
    node.data.tool = null
    node.data.missingTool = {
      node_id: node.id,
      tool_name: detail.tool_name,
      installed_versions: [],
    }
    changed = true
  }
  if (changed) emitGraphChanged()
}

function closeNodeContextMenu() {
  nodeContextMenu.value = null
}

function onNodeContextMenu(payload: any) {
  const event = payload.event
  const node = payload.node
  if (!event || !node || typeof event.clientX !== 'number') return
  event.preventDefault()
  const rect = canvasRef.value?.getBoundingClientRect()
  nodeContextMenu.value = {
    nodeId: node.id,
    position: {
      x: event.clientX - (rect?.left ?? 0),
      y: event.clientY - (rect?.top ?? 0),
    },
    enabled: node.data?.enabled !== false,
    canOpenSubWorkflow: node.data?.sub_workflow != null,
  }
}

function onNodeDoubleClick(payload: any) {
  const node = payload.node
  if (!node?.data?.sub_workflow) return
  openSubWorkflow(node.id)
}

function runContextSubWorkflowAction() {
  const menu = nodeContextMenu.value
  if (!menu) return
  if (menu.canOpenSubWorkflow) {
    openSubWorkflow(menu.nodeId)
  } else {
    createSelectedSubWorkflow()
  }
  closeNodeContextMenu()
}

function toggleContextNodeEnabled() {
  const menu = nodeContextMenu.value
  if (!menu) return
  const node = getNodes.value.find((n: any) => n.id === menu.nodeId)
  if (!node?.data) return
  node.data.enabled = node.data.enabled === false
  closeNodeContextMenu()
  emitGraphChanged()
}

function deleteContextNode() {
  const menu = nodeContextMenu.value
  if (!menu) return
  for (const node of getNodes.value as any[]) {
    node.selected = node.id === menu.nodeId
  }
  closeNodeContextMenu()
  deleteSelected()
}

// Hot-reload watcher: subscribes to toolRegistryStore.tools mutations
// driven by useWebSocket and updates affected canvas nodes (badge,
// schema swap, optimistic out_of_date, flushNow). useToast throws when
// no ToastService is provided (e.g. in unit tests that mount CanvasView
// in isolation), so guard it. The toast surfaces "Field 'X' was removed
// by the tool update." when a focused field vanishes from the new
// schema.
let hotReloadToast: ReturnType<typeof useToast> | null = null
try {
  hotReloadToast = useToast()
} catch {
  /* no ToastService — useHotReload still runs without the toast surface */
}
clipboardToast = hotReloadToast
if (clipboardToast === null) {
  try {
    clipboardToast = useToast()
  } catch {
    /* no ToastService — clipboard operations still work without toasts */
  }
}
useHotReload({
  toast: hotReloadToast === null
    ? undefined
    : (message: string) => {
        hotReloadToast!.add({
          severity: 'warn',
          summary: 'Tool reloaded',
          detail: message,
          life: 5000,
        })
      },
})

async function loadSubWorkflowSessionDraft() {
  const sessionId = props.subWorkflowSessionId
  if (!sessionId) return
  const session = subWorkflowSessionsStore.sessionById(sessionId)
  await applyGraphState(session?.draft ?? { nodes: [], edges: [] })
  if (isCanvasUnmounted) return
  hasLoadedGraphState.value = true
}

onMounted(async () => {
  if (!isSubWorkflowEditor) {
    window.addEventListener(
      'bioimageflow:apply-sub-workflow-session',
      handleApplySubWorkflowSessionEvent as EventListener,
    )
    window.addEventListener('bioimageflow:tool-renamed', handleToolRenamedEvent)
    window.addEventListener('bioimageflow:tool-deleted', handleToolDeletedEvent)
  }
  window.addEventListener('bioimageflow:edit-command', handleEditCommandEvent as EventListener)
  window.addEventListener(
    'bioimageflow:canvas-tab-activated',
    handleCanvasTabActivatedEvent as EventListener,
  )
  if (toolRegistryStore.tools.length === 0) {
    await toolRegistryStore.fetchTools()
  }
  if (isCanvasUnmounted) return
  if (isSubWorkflowEditor) {
    await loadSubWorkflowSessionDraft()
    return
  }
  const initialGraph = initialGraphFromDockviewParams()
  if (initialGraph) {
    await applyGraphState(
      initialGraph.graph,
      initialGraph.missingTools ?? [],
      initialGraph.dirty ?? false,
    )
    if (isCanvasUnmounted) return
    hasLoadedGraphState.value = true
    return
  }
  const recovered = await recoverStartupWorkflow()
  if (isCanvasUnmounted) return
  adoptRecoveredWorkflowIdentity(recovered)
  await applyGraphState(
    recovered.graph,
    workflowStore.missingTools,
    recovered.dirty,
  )
  if (isCanvasUnmounted) return
  hasLoadedGraphState.value = true
})

onBeforeUnmount(() => {
  isCanvasUnmounted = true
  dataTableStore.releaseCanvas(canvasId)
  resolvedOutputsStore.releaseCanvas(canvasId)
  disposeGraphSync()
  disposeCanvasPersistence()
  canvasCommands.dispose()
  uiStore.releaseCanvasPresentation(canvasId)
  if (!isSubWorkflowEditor) {
    window.removeEventListener(
      'bioimageflow:apply-sub-workflow-session',
      handleApplySubWorkflowSessionEvent as EventListener,
    )
    window.removeEventListener('bioimageflow:tool-renamed', handleToolRenamedEvent)
    window.removeEventListener('bioimageflow:tool-deleted', handleToolDeletedEvent)
  }
  window.removeEventListener('bioimageflow:edit-command', handleEditCommandEvent as EventListener)
  window.removeEventListener(
    'bioimageflow:canvas-tab-activated',
    handleCanvasTabActivatedEvent as EventListener,
  )
})

// --- Node drag tracking (undo support) ---

onNodeDragStart(({ nodes }) => {
  const positions: Record<string, { x: number; y: number }> = {}
  for (const node of nodes) {
    positions[node.id] = { x: node.position.x, y: node.position.y }
  }
  dragStartPositions.value = positions
})

onNodeDragStop(({ nodes }) => {
  const start = dragStartPositions.value
  const moved = nodes.some((node) => {
    const prev = start[node.id]
    if (!prev) return true
    return prev.x !== node.position.x || prev.y !== node.position.y
  })
  if (moved) {
    emitGraphChanged()
  }
  dragStartPositions.value = {}
})

// --- Connection handling ---

/**
 * Remove any edge already targeting (nodeId, targetHandle) so that the input
 * pin is left with at most one incoming connection. Positional inputs don't
 * have this constraint — each positional index is its own pin.
 */
function clearExistingIncomingEdge(nodeId: string, targetHandle: string) {
  if (targetHandle.startsWith('__positional_')) return
  const existing = getEdges.value.filter(
    (e: any) => e.target === nodeId && e.targetHandle === targetHandle,
  )
  if (existing.length === 0) return
  removeEdges(existing.map((e: any) => e.id))
  cleanupDisconnectedInput(nodeId, targetHandle)
}

onConnect((connection) => {
  if (isLocked.value) return
  const targetHandle = connection.targetHandle ?? ''

  // Reject positional edges into source DataFrameTools (accepts_upstream=false).
  if (targetHandle.startsWith('__positional_')) {
    const targetNode = getNodes.value.find((n: any) => n.id === connection.target)
    const targetTool: ToolMetadata | undefined =
      (targetNode?.data?.tool as ToolMetadata | undefined) ??
      toolRegistryStore.getToolByName(targetNode?.data?.toolName)
    if (targetTool?.accepts_upstream === false) {
      const sourceNode = getNodes.value.find(
        (n: any) => n.id === connection.source,
      )
      const sourceLabel =
        sourceNode?.data?.name ?? sourceNode?.id ?? connection.source
      const targetLabel =
        targetNode?.data?.name ?? targetNode?.id ?? connection.target
      reportError({
        kind: 'edge_rejected',
        detail: `${targetLabel} is a source node and does not accept upstream input from ${sourceLabel}.`,
      })
      return
    }
  }

  // Enforce one incoming edge per (non-positional) input. When users drag from
  // an already-connected input pin, Vue Flow issues a fresh connect rather than
  // an edge-update; this keeps the graph consistent either way.
  clearExistingIncomingEdge(connection.target, targetHandle)

  const edgeIsHeader = isHeaderHandle(targetHandle) || isHeaderHandle(connection.sourceHandle)
  const newEdge = {
    id: `e-${connection.source}-${connection.sourceHandle}-${connection.target}-${targetHandle}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle,
    targetHandle,
    type: edgeIsHeader ? 'positional' : 'column_ref',
  }
  addEdges([newEdge])

  // Update connectedInputs on target node
  const targetNode = getNodes.value.find((n: any) => n.id === connection.target)
  if (targetNode) {
    const sourceNode = getNodes.value.find((n: any) => n.id === connection.source)
    const sourceLabel = sourceNode
      ? `${sourceNode.data?.name ?? sourceNode.id}.${connection.sourceHandle ?? 'output'}`
      : ''
    targetNode.data.connectedInputs = {
      ...targetNode.data.connectedInputs,
      [targetHandle]: sourceLabel,
    }
    pinConnectedBodyInput(targetNode, targetHandle, connection.sourceHandle)
    // Drop any constant the user (or default-seeding) had stashed for this
    // input. The wire schema says `parameters` carries non-connected fields
    // only, and a stray value here (notably ``null``) would otherwise ride
    // along into the lib payload and override the upstream binding.
    if (!edgeIsHeader && targetNode.data.parameters
        && targetHandle in targetNode.data.parameters) {
      const next = { ...targetNode.data.parameters }
      delete next[targetHandle]
      targetNode.data.parameters = next
    }
  }

  // A new positional edge into a dynamic_outputs node changes its resolved
  // schema (e.g. CrossJoin's column union depends on the upstream tables).
  if (targetHandle.startsWith('__positional_')) {
    refreshIfDynamicOutputs(connection.target)
  }

  emitGraphChanged()
})

onNodesChange((changes) => {
  const hasSelectionChange = changes.some((c: any) => c.type === 'select')
  if (hasSelectionChange) {
    const selectedIds = getNodes.value
      .filter((n: any) => n.selected)
      .map((n: any) => n.id)
    uiStore.setCanvasSelectedNodes(canvasId, selectedIds)
    emit('node-selected', selectedIds)
  }
})

// Sync graph nodes to UI store for NodePanel
watch(getNodes, (nodes) => {
  uiStore.setCanvasGraphNodes(canvasId, nodes)
}, { deep: true })

// Persist in-place node-data edits made from NodePanel (parameters, rename,
// enable/disable, pin toggles, output templates). Vue Flow's structural
// events (drag, connect, add, delete) already call emitGraphChanged
// themselves — but parameter edits mutate node.data directly with no
// corresponding event, so without this watcher they never reach IndexedDB
// or the backend. Watching only NodePanel-owned fields keeps drag/selection/
// status/connectedInputs mutations from re-triggering a full sync.
watch(
  () => getNodes.value.map((n: any) => ({
    id: n.id,
    name: n.data?.name,
    parameters: n.data?.parameters,
    enabled: n.data?.enabled,
    pinnedInputs: n.data?.pinnedInputs,
    output_templates: n.data?.output_templates,
    sub_workflow: n.data?.sub_workflow,
    published_inputs: n.data?.published_inputs,
    published_outputs: n.data?.published_outputs,
  })).concat([{
    id: '__root_publication_context__',
    name: null,
    parameters: null,
    enabled: true,
    pinnedInputs: null,
    output_templates: null,
    sub_workflow: null,
    published_inputs: rootPublishedInputs.value,
    published_outputs: rootPublishedOutputs.value,
  }]),
  () => {
    if (isApplyingGraphState) return
    if (isRefreshingToolMetadata) return
    emitGraphChanged()
  },
  { deep: true },
)

// Refresh the per-node tool metadata snapshot whenever the registry's
// tools list changes (typically after a "Set current" version switch in
// the Manage Tools dialog, or an install/uninstall). Each node was created
// with a frozen ToolMetadata copy in `data.tool`, so without this watcher
// the package version + schema in the GUI would stay pinned at creation
// time even though the workflow actually executes against the new
// version.
//
// Nodes whose package_version actually changed are flagged `out_of_date`
// so the user knows they need to re-run — schema changes between versions
// can invalidate cached results.
watch(
  () => toolRegistryStore.tools,
  (tools) => {
    if (isApplyingGraphState) return
    if (!tools || tools.length === 0) return
    const byName = new Map(tools.map((t) => [t.name, t]))
    let changed = false
    isRefreshingToolMetadata = true
    try {
      for (const n of getNodes.value as any[]) {
        const toolName = n.data?.toolName
        if (!toolName) continue
        const fresh = byName.get(toolName)
        if (!fresh) continue
        const prev = n.data.tool
        if (prev && prev.package_version === fresh.package_version) continue
        n.data.tool = fresh
        n.data.output_templates = reconcileOutputTemplates(
          fresh,
          n.data.output_templates ?? {},
        )
        // Only invalidate executed nodes — leave unexecuted/failed/disabled
        // alone so the version switch doesn't visually thrash the canvas.
        if (n.data.status === 'executed') {
          n.data.status = 'out_of_date'
        }
        changed = true
      }
    } finally {
      void nextTick().then(() => {
        isRefreshingToolMetadata = false
      })
    }
    if (changed) {
      const graph = rememberAuthoritativeGraph(
        graphWithAuthoritativeEdges(currentVueFlowState()),
      )
      syncGraphState(graph)
    }
  },
  { deep: false },
)

// Debounced refresh of resolved outputs when parameters change on
// dynamic_outputs nodes. Edge connect/disconnect events refresh explicitly
// (see refreshIfDynamicOutputs) — Vue's deep watcher doesn't reliably notice
// in-place edge mutations on the underlying graph store.
watch(
  () => getNodes.value
    .filter((n: any) => n.data?.tool?.dynamic_outputs === true)
    .map((n: any) => ({ id: n.id, parameters: n.data?.parameters })),
  (entries) => {
    for (const entry of entries) {
      refreshIfDynamicOutputs(entry.id)
    }
  },
  { deep: true },
)

/**
 * Trigger a debounced resolved-output refresh on `nodeId` if the node has
 * `dynamic_outputs === true`. The store will additionally walk downstream
 * along positional edges and refresh any other dynamic_outputs node
 * reachable from this one.
 */
function refreshIfDynamicOutputs(nodeId: string): void {
  const node = getNodes.value.find((n: any) => n.id === nodeId)
  const tool: ToolMetadata | undefined =
    (node?.data?.tool as ToolMetadata | undefined) ??
    toolRegistryStore.getToolByName(node?.data?.toolName)
  if (tool?.dynamic_outputs !== true) return
  const getGraph = () => ({ nodes: getNodes.value, edges: getEdges.value })
  const getToolForNode = (id: string): ToolMetadata | undefined => {
    const n = getNodes.value.find((nn: any) => nn.id === id)
    return n?.data?.tool ?? toolRegistryStore.getToolByName(n?.data?.toolName)
  }
  resolvedOutputsStore.refreshCanvasResolvedOutputs(
    canvasId,
    nodeId,
    getGraph,
    getToolForNode,
  )
}

/**
 * Detach the edge targeting (nodeId, targetHandle). Called by InputPin when a
 * user grabs a connected input pin — removing the edge lets Vue Flow's
 * connection gesture take over from the upstream source with the cursor as
 * the new endpoint. Vue Flow's default edges-updatable mechanism (grab near
 * the edge endpoint) is still enabled so users have both paths to redirect a
 * connection.
 */
function disconnectEdgeByInput(edgeId: string) {
  const edge = getEdges.value.find((e: any) => e.id === edgeId)
  if (!edge) return
  const targetHandle = edge.targetHandle ?? ''
  const target = edge.target
  cleanupDisconnectedInput(target, targetHandle)
  removeEdges([edgeId])
  if (targetHandle.startsWith('__positional_')) {
    refreshIfDynamicOutputs(target)
  }
  emitGraphChanged()
}

provide('bioimageflow:disconnectEdge', disconnectEdgeByInput)

// Edges whose endpoint was successfully moved during the current update
// gesture. Used by onEdgeUpdateEnd to distinguish "moved to another pin" from
// "dropped on empty space".
const updatedEdgeIds = new Set<string>()

onEdgeUpdate(({ edge, connection }) => {
  updatedEdgeIds.add(edge.id)

  const newTarget = connection.target ?? edge.target
  const newTargetHandle = connection.targetHandle ?? edge.targetHandle ?? ''
  const newSource = connection.source ?? edge.source
  const newSourceHandle = connection.sourceHandle ?? edge.sourceHandle ?? ''

  // Clean up old connectedInputs entry before rewriting
  cleanupDisconnectedInput(edge.target, edge.targetHandle ?? '')

  // Enforce single incoming edge on the new target input. Skip when the edge
  // is being updated into the same slot (the edge itself is the existing one).
  if (edge.target !== newTarget || edge.targetHandle !== newTargetHandle) {
    clearExistingIncomingEdge(newTarget, newTargetHandle)
  }

  // Update the edge in place so Vue Flow's EdgeWrapper keeps tracking the
  // same record through pointerup. Removing + re-adding here makes
  // `edge.value` go undefined, which makes onEdgeUpdateEnd receive an
  // undefined edge and throw — Vue Flow then skips its own endConnection
  // cleanup and a pending connection line keeps following the cursor.
  updateEdge(edge, {
    source: newSource,
    target: newTarget,
    sourceHandle: newSourceHandle,
    targetHandle: newTargetHandle,
  }, false)

  // Update connectedInputs on the new target node
  const targetNode = getNodes.value.find((n: any) => n.id === newTarget)
  if (targetNode) {
    const sourceNode = getNodes.value.find((n: any) => n.id === newSource)
    const sourceLabel = sourceNode
      ? `${sourceNode.data?.name ?? sourceNode.id}.${newSourceHandle || 'output'}`
      : ''
    targetNode.data.connectedInputs = {
      ...targetNode.data.connectedInputs,
      [newTargetHandle]: sourceLabel,
    }
    pinConnectedBodyInput(targetNode, newTargetHandle, newSourceHandle)
    // Mirror the onConnect cleanup: drop any constant for this input so
    // the wire payload carries non-connected fields only.
    const newEdgeIsHeader = isHeaderHandle(newTargetHandle) || isHeaderHandle(newSourceHandle)
    if (!newEdgeIsHeader && targetNode.data.parameters
        && newTargetHandle in targetNode.data.parameters) {
      const next = { ...targetNode.data.parameters }
      delete next[newTargetHandle]
      targetNode.data.parameters = next
    }
  }

  // Refresh schemas on either side of a positional re-route — both the old
  // and the new targets may have dynamic_outputs schemas to recompute.
  if ((edge.targetHandle ?? '').startsWith('__positional_')) {
    refreshIfDynamicOutputs(edge.target)
  }
  if (newTargetHandle.startsWith('__positional_')) {
    refreshIfDynamicOutputs(newTarget)
  }

  emitGraphChanged()
})

// Edge disconnect: dragging a connected handle to empty space (no onEdgeUpdate
// fired for this gesture).
onEdgeUpdateEnd(({ edge }) => {
  if (!edge) return
  if (updatedEdgeIds.delete(edge.id)) return
  const targetHandle = edge.targetHandle ?? ''
  const target = edge.target
  removeEdges([edge.id])
  cleanupDisconnectedInput(target, targetHandle)
  if (targetHandle.startsWith('__positional_')) {
    refreshIfDynamicOutputs(target)
  }
  emitGraphChanged()
})

// --- Connected-input bookkeeping ---

/**
 * After an edge targeting `targetHandle` on `nodeId` is removed,
 * remove that key from connectedInputs and, for positional inputs,
 * reindex the remaining entries so there are no gaps.
 */
function cleanupDisconnectedInput(nodeId: string, targetHandle: string) {
  const node = getNodes.value.find((n: any) => n.id === nodeId)
  if (!node) return

  const ci = { ...node.data.connectedInputs }
  delete ci[targetHandle]

  if (targetHandle.startsWith('__positional_')) {
    reindexPositionalInputs(node, ci)
  } else {
    node.data.connectedInputs = ci
  }
}

/**
 * Compact positional entries so they are numbered 0..N-1 without gaps.
 * Also updates the targetHandle on the corresponding edges.
 */
function reindexPositionalInputs(
  node: any,
  ci: Record<string, string>,
) {
  // Collect currently connected positional entries, sorted by old index
  const positionalEntries = Object.entries(ci)
    .filter(([k]) => k.startsWith('__positional_'))
    .sort(([a], [b]) => {
      const ai = parseInt(a.replace('__positional_', ''), 10)
      const bi = parseInt(b.replace('__positional_', ''), 10)
      return ai - bi
    })

  // Remove all old positional keys
  for (const key of Object.keys(ci)) {
    if (key.startsWith('__positional_')) {
      delete ci[key]
    }
  }

  // Re-insert with compact indices and update edges
  positionalEntries.forEach(([oldKey, label], newIndex) => {
    const newKey = `__positional_${newIndex}`
    ci[newKey] = label

    if (oldKey !== newKey) {
      // Update the corresponding edge's targetHandle
      const edge = getEdges.value.find(
        (e: any) => e.target === node.id && e.targetHandle === oldKey,
      )
      if (edge) {
        edge.targetHandle = newKey
        edge.id = `e-${edge.source}-${edge.sourceHandle}-${edge.target}-${newKey}`
      }
    }
  })

  node.data.connectedInputs = ci
}

// --- Validation ---

/**
 * Determine whether a handle belongs to the header region (DataFrame-level)
 * or the body region (column-level / field-level).
 */
function isHeaderHandle(handle: string | null | undefined): boolean {
  if (!handle) return false
  return handle.startsWith('__positional_') || handle === '__dataframe_out'
}

function pinConnectedBodyInput(
  targetNode: any,
  targetHandle: string,
  sourceHandle: string | null | undefined,
): void {
  if (!targetHandle || isHeaderHandle(targetHandle) || isHeaderHandle(sourceHandle)) return
  const tool = toolForNode(targetNode)
  const field = tool?.inputs?.[targetHandle]
  if (!field || field.connectable === 'never') return
  targetNode.data.pinnedInputs = {
    ...(targetNode.data.pinnedInputs ?? {}),
    [targetHandle]: true,
  }
}

function toolForNode(node: any): ToolMetadata | undefined {
  return (node?.data?.tool as ToolMetadata | undefined)
    ?? toolRegistryStore.getToolByName(node?.data?.toolName)
}

function isSubWorkflowNode(node: any): boolean {
  return node?.data?.toolName === '__sub_workflow__' || node?.data?.sub_workflow != null
}

function publishedSchemaType(schema: unknown): string | undefined {
  if (!schema || typeof schema !== 'object') return undefined
  const type = (schema as { type?: unknown }).type
  return typeof type === 'string' ? type : undefined
}

function outputTypeForHandle(node: any, handle: string): string | undefined {
  const tool = toolForNode(node)
  const sourceOutput = tool?.outputs?.[handle] as { type?: string } | undefined
  let sourceType = sourceOutput?.type
  if (!sourceType && tool?.dynamic_outputs) {
    const resolved = canvasResolvedOutputs[node.id]
    if (resolved?.resolved && resolved.columns) {
      const col = (resolved.columns as Record<string, any>)[handle]
      sourceType = col?.type
    }
  }
  if (sourceType) return sourceType
  if (!isSubWorkflowNode(node)) return undefined
  const published = (node.data?.published_outputs ?? []).find(
    (item: PublishedOutput) => item.name === handle,
  )
  return publishedSchemaType(published?.schema)
}

function inputTypeForHandle(node: any, handle: string): string | undefined {
  const tool = toolForNode(node)
  const targetInput = tool?.inputs?.[handle]
  if (targetInput?.type) return targetInput.type
  if (!isSubWorkflowNode(node)) return undefined
  const published = (node.data?.published_inputs ?? []).find(
    (item: PublishedInput) => item.name === handle,
  )
  return publishedSchemaType(published?.schema)
}

function isValidConnection(connection: {
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
}): boolean {
  // 0. Cross-region rejection: header handles must connect to header,
  //    body handles must connect to body.
  const sourceIsHeader = isHeaderHandle(connection.sourceHandle)
  const targetIsHeader = isHeaderHandle(connection.targetHandle)
  if (sourceIsHeader !== targetIsHeader) {
    return false
  }

  // 1. Type compatibility check
  const sourceNode = getNodes.value.find((n: any) => n.id === connection.source)
  const targetNode = getNodes.value.find((n: any) => n.id === connection.target)
  if (!sourceNode || !targetNode) return false

  // Prefer the tool metadata carried on the node itself — the registry may
  // not be populated yet during restore-on-mount (fetch is async), and a
  // missing tool here would silently fail every edge with EDGE_INVALID.
  const sourceTool = toolForNode(sourceNode)
  const targetTool = toolForNode(targetNode)
  if (
    (!sourceTool && !isSubWorkflowNode(sourceNode))
    || (!targetTool && !isSubWorkflowNode(targetNode))
  ) {
    return false
  }

  // 1b. Reject positional edges into source DataFrameTools
  const th = connection.targetHandle ?? ''
  if (th.startsWith('__positional_') && targetTool?.accepts_upstream === false) {
    return false
  }

  if (connection.sourceHandle && connection.targetHandle) {
    // Skip type checks for header-to-header connections (DataFrame-level)
    if (!sourceIsHeader) {
      const sourceType = outputTypeForHandle(sourceNode, connection.sourceHandle)
      const targetType = inputTypeForHandle(targetNode, connection.targetHandle)
      if (sourceType && targetType) {
        // "any" type is compatible with any consumer input type.
        if (sourceType === 'any') {
          // Accept — skip type-mismatch rejection.
        } else {
          // Path-family types (Path / ImageFile / MaskPath) all share the same
          // runtime carrier (a filesystem path); the distinction is metadata
          // (image_spec semantics, formats, layouts). Treat them as mutually
          // compatible at the frontend pre-flight; the bioimageflow library
          // performs the authoritative semantic check on graph validate.
          const PATH_FAMILY = new Set(['Path', 'ImageFile', 'MaskPath'])
          const same = sourceType === targetType
          const bothPath = PATH_FAMILY.has(sourceType) && PATH_FAMILY.has(targetType)
          if (!same && !bothPath) return false
        }
      }
    }
  }

  // 2. Cycle detection: reject if target is an ancestor of source
  if (hasPath(connection.target, connection.source)) {
    return false
  }

  return true
}

function hasPath(from: string, to: string): boolean {
  const visited = new Set<string>()
  const stack = [from]
  const edges = getEdges.value

  while (stack.length > 0) {
    const current = stack.pop()!
    if (current === to) return true
    if (visited.has(current)) continue
    visited.add(current)

    for (const edge of edges) {
      if (edge.source === current && !visited.has(edge.target)) {
        stack.push(edge.target)
      }
    }
  }
  return false
}

// --- Drop handling ---

function onDrop(event: DragEvent) {
  event.preventDefault()
  if (isLocked.value) return
  const workflowName = event.dataTransfer?.getData('application/bioimageflow-workflow')
  if (workflowName) {
    const rect = (canvasRef.value as HTMLElement).getBoundingClientRect()
    const position = project({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    })
    void onAddWorkflowNode({ workflowName, position })
    return
  }
  const toolName = event.dataTransfer?.getData('application/bioimageflow-tool')
  if (!toolName) return

  const rect = (canvasRef.value as HTMLElement).getBoundingClientRect()
  const position = project({
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  })

  onAddNode({ toolName, position })
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

// --- Node creation ---

function onAddNode({
  toolName,
  position,
}: {
  toolName: string
  position?: { x: number; y: number }
}) {
  if (isLocked.value) return
  const tool = toolRegistryStore.getToolByName(toolName)
  if (!tool) return

  const existingIds = getNodes.value.map((n: any) => n.id)
  const existingNames = getNodes.value.map((n: any) => n.data?.name ?? '')

  const id = generateNodeId(tool.name, existingIds)
  const name = generateNodeName(tool.name, existingNames, tool.display_name)

  // Build default parameters from tool inputs
  const parameters: Record<string, unknown> = {}
  for (const [key, field] of Object.entries(tool.inputs)) {
    if (field.default !== undefined) {
      parameters[key] = field.default
    }
  }

  // Build default pinned state from connectable inputs
  // Only default to pinned (true) for required Path-type fields
  const pinnedInputs: Record<string, boolean> = {}
  for (const [key, field] of Object.entries(tool.inputs)) {
    if (field.connectable !== 'never') {
      const isPathType = ['Path', 'ImageFile', 'MaskPath'].includes(field.type)
      pinnedInputs[key] = isPathType && field.required
    }
  }

  const output_templates = reconcileOutputTemplates(tool)

  const newNode = {
    id,
    type: 'tool',
    position: position ?? { x: 0, y: 0 },
    data: {
      name,
      toolName,
      tool,
      status: 'unexecuted',
      parameters,
      collapsed: false,
      enabled: true,
      connectedInputs: {},
      pinnedInputs,
      output_templates,
    },
  }

  attachPublicationContext(newNode)
  addNodes([newNode])
  emitGraphChanged()
}

async function onAddWorkflowNode({
  workflowName,
  position,
}: {
  workflowName: string
  position?: { x: number; y: number }
}) {
  if (isLocked.value) return
  try {
    const { data } = await api.get(`/api/v1/workflows/${workflowName}`)
    const graph = data.graph as GraphState
    if (wouldCreateWorkflowContainmentCycle(workflowName, graph)) {
      showWorkflowContainmentError(workflowName)
      return
    }
    const info = data.info as { display_name?: string; name?: string }
    const existingIds = getNodes.value.map((n: any) => n.id)
    const existingNames = getNodes.value.map((n: any) => n.data?.name ?? '')
    const id = generateNodeId('__sub_workflow__', existingIds)
    const name = generateNodeName(
      info.display_name ?? workflowName,
      existingNames,
      info.display_name ?? workflowName,
    )
    const newNode = {
      id,
      type: 'sub_workflow',
      position: position ?? { x: 0, y: 0 },
      data: {
        name,
        toolName: '__sub_workflow__',
        tool: null,
        status: 'unexecuted',
        parameters: {},
        collapsed: false,
        enabled: true,
        connectedInputs: {},
        pinnedInputs: {},
        output_templates: {},
        sub_workflow: graph,
        published_inputs: graph.published_inputs ?? [],
        published_outputs: graph.published_outputs ?? [],
        source_workflow_name: workflowName,
      },
    }
    attachPublicationContext(newNode)
    addNodes([newNode])
    emitGraphChanged()
  } catch (e: unknown) {
    clipboardToast?.add({
      severity: 'error',
      summary: 'Open workflow failed',
      detail: e instanceof Error ? e.message : String(e),
      life: 5000,
    })
  }
}

// --- Selection + Keyboard ---

function deleteSelected() {
  if (isLocked.value) return
  const selectedNodes = getNodes.value.filter((n: any) => n.selected)
  if (selectedNodes.length === 0) {
    // Delete selected edges
    const selectedEdges = getEdges.value.filter((e: any) => e.selected)
    if (selectedEdges.length === 0) return
    // Clean up connectedInputs for each removed edge
    const positionalTargets = new Set<string>()
    for (const edge of selectedEdges) {
      cleanupDisconnectedInput(edge.target, edge.targetHandle ?? '')
      if ((edge.targetHandle ?? '').startsWith('__positional_')) {
        positionalTargets.add(edge.target)
      }
    }
    removeEdges(selectedEdges.map((e: any) => e.id))
    for (const id of positionalTargets) {
      refreshIfDynamicOutputs(id)
    }
    emitGraphChanged()
    return
  }

  const selectedNodeIds = new Set(selectedNodes.map((n: any) => n.id))

  // Remove edges connected to deleted nodes
  const edgesToRemove = getEdges.value.filter(
    (e: any) => selectedNodeIds.has(e.source) || selectedNodeIds.has(e.target),
  )

  // Clean up connectedInputs on surviving target nodes
  const survivingPositionalTargets = new Set<string>()
  for (const edge of edgesToRemove) {
    if (!selectedNodeIds.has(edge.target)) {
      cleanupDisconnectedInput(edge.target, edge.targetHandle ?? '')
      if ((edge.targetHandle ?? '').startsWith('__positional_')) {
        survivingPositionalTargets.add(edge.target)
      }
    }
  }

  removeEdges(edgesToRemove.map((e: any) => e.id))
  removeNodes(selectedNodes.map((n: any) => n.id))
  for (const id of survivingPositionalTargets) {
    refreshIfDynamicOutputs(id)
  }
  emitGraphChanged()
}

function copySelected() {
  if (isLocked.value) return
  const selectedIds = new Set(
    getNodes.value.filter((n: any) => n.selected).map((n: any) => n.id),
  )
  if (selectedIds.size === 0) return

  const graph = serializeGraph({
    nodes: getNodes.value,
    edges: getEdges.value,
  })
  const payload = serializeGraphSelection(
    graph,
    selectedIds,
    toolRegistryStore.getToolByName,
    { sourceWorkflowName: owningWorkflowId() ?? undefined },
  )
  clipboardData.value = payload
  void writeClipboardPayload(payload)
}

function ensureClipboardToast(): ReturnType<typeof useToast> | null {
  return clipboardToast
}

function summarizeNames(names: string[], limit = 3): string {
  const unique = [...new Set(names)].filter(Boolean)
  if (unique.length <= limit) return unique.join(', ')
  return `${unique.slice(0, limit).join(', ')} and ${unique.length - limit} more`
}

function showPasteSummary(summary: PasteSummary) {
  const toast = ensureClipboardToast()
  if (!toast) return
  const hasParameterDefaults =
    summary.parameterResets.length > 0
    || summary.omittedRequiredParameters.length > 0

  if (summary.missingTools.length > 0) {
    toast.add({
      severity: 'warn',
      summary: 'Some pasted tools are missing',
      detail: summarizeNames(summary.missingTools),
      life: 5000,
    })
  }
  if (summary.versionMismatches.length > 0) {
    const versionDetails = summary.versionMismatches.map((item) => {
      const from = item.sourceVersion ?? 'unknown'
      const to = item.targetVersion ?? 'unknown'
      return `${item.nodeName} (${item.packageName ?? 'package'} ${from} -> ${to})`
    })
    toast.add({
      severity: 'warn',
      summary: 'Pasted tool versions differ',
      detail: `${summarizeNames(versionDetails)}${hasParameterDefaults ? '. Some parameters were reset to defaults.' : ''}`,
      life: 5000,
    })
  }
  if (
    summary.parameterResets.length > 0
    || summary.removedParameters.length > 0
    || summary.omittedRequiredParameters.length > 0
  ) {
    const affected = [
      ...summary.parameterResets,
      ...summary.removedParameters,
      ...summary.omittedRequiredParameters,
    ].map((item) => item.nodeName)
    toast.add({
      severity: 'warn',
      summary: 'Pasted parameters were reconciled',
      detail: summarizeNames(affected),
      life: 5000,
    })
  }
}

function vueFlowNodeFromClipboardNode(n: ClipboardPayload['nodes'][number]) {
  const tool = toolRegistryStore.getToolByName(n.tool_name)
  const pinnedInputs: Record<string, boolean> = {}
  let output_templates: Record<string, string> = {}
  if (tool) {
    for (const [key, field] of Object.entries(tool.inputs)) {
      if (field.connectable !== 'never') {
        const isPathType = ['Path', 'ImageFile', 'MaskPath'].includes(field.type)
        pinnedInputs[key] = isPathType && field.required
      }
    }
    output_templates = reconcileOutputTemplates(tool, n.output_templates ?? {})
  }
  return {
    id: n.id,
    type: 'tool',
    position: { x: n.position[0], y: n.position[1] },
    data: {
      name: n.name,
      toolName: n.tool_name,
      tool: tool ?? null,
      status: 'unexecuted',
      parameters: n.parameters,
      resources: n.resources ?? {},
      collapsed: n.collapsed ?? false,
      enabled: n.enabled ?? true,
      connectedInputs: {},
      pinnedInputs,
      output_templates,
      sub_workflow: n.sub_workflow ?? null,
      published_inputs: n.published_inputs ?? [],
      published_outputs: n.published_outputs ?? [],
      sub_workflow_readonly_reason: n.sub_workflow_readonly_reason ?? null,
      source_workflow_name: n.source_workflow_name ?? null,
    },
  }
}

function vueFlowEdgeFromClipboardEdge(e: ClipboardPayload['edges'][number]) {
  if (e.type === 'positional') {
    return {
      id: e.id,
      source: e.source_node,
      target: e.target_node,
      sourceHandle: '__dataframe_out',
      targetHandle: `__positional_${e.positional_index}`,
      type: 'positional',
    }
  }
  return {
    id: e.id,
    source: e.source_node,
    target: e.target_node,
    sourceHandle: e.source_output,
    targetHandle: e.target_input,
    type: 'column_ref',
  }
}

function currentVueFlowState(): {
  nodes: any[]
  edges: any[]
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
} {
  return {
    nodes: getNodes.value.map((n: any) => ({ ...n })),
    edges: getEdges.value.map((e: any) => ({ ...e })),
    published_inputs: rootPublishedInputs.value,
    published_outputs: rootPublishedOutputs.value,
  }
}

function populateConnectedInputsForPastedNodes(nodes: any[], edges: any[]) {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  for (const edge of edges) {
    const targetNode = byId.get(edge.target)
    if (!targetNode) continue
    const targetHandle = edge.targetHandle ?? ''
    if (!targetHandle) continue
    const sourceHandle = edge.sourceHandle ?? 'output'
    targetNode.data.connectedInputs = {
      ...(targetNode.data.connectedInputs ?? {}),
      [targetHandle]: `${edge.source}.${sourceHandle}`,
    }
    pinConnectedBodyInput(targetNode, targetHandle, edge.sourceHandle)
  }
}

async function pasteFromClipboard() {
  if (isLocked.value) return
  const readResult = await readClipboardPayloadResult()
  if (readResult.kind === 'empty') return
  if (readResult.kind === 'invalid') {
    const toast = ensureClipboardToast()
    toast?.add({
      severity: 'warn',
      summary: 'Clipboard does not contain BioImageFlow nodes',
      detail: readResult.reason,
      life: 5000,
    })
    return
  }
  if (readResult.kind === 'unsupported_version') {
    const toast = ensureClipboardToast()
    toast?.add({
      severity: 'warn',
      summary: 'Unsupported clipboard version',
      detail: `Clipboard version ${String(readResult.version)} is not supported.`,
      life: 5000,
    })
    return
  }
  const payload = readResult.payload
  clipboardData.value = payload

  const existingIds = getNodes.value.map((n: any) => n.id)
  const existingNames = getNodes.value.map((n: any) => n.data?.name ?? '')

  const prepared = prepareClipboardPaste(
    payload,
    {
      existingIds,
      existingNames,
      existingEdgeIds: getEdges.value.map((edge: any) => edge.id),
      getToolByName: toolRegistryStore.getToolByName,
    },
  )
  if (prepared.nodes.length === 0) {
    const toast = ensureClipboardToast()
    toast?.add({
      severity: 'warn',
      summary: 'No tools found',
      detail: 'No tools found for the pasted nodes. Install the required packages first.',
      life: 5000,
    })
    return
  }

  const newNodes = attachPublicationContextToNodes(
    prepared.nodes.map(vueFlowNodeFromClipboardNode),
  )
  const newEdges = prepared.edges.map(vueFlowEdgeFromClipboardEdge)
  populateConnectedInputsForPastedNodes(newNodes, newEdges)

  undoRedo.push(currentVueFlowState())
  addNodes(newNodes)
  addEdges(newEdges)
  showPasteSummary(prepared.summary)
  emitGraphChanged()
}

function createSelectedSubWorkflow() {
  if (isLocked.value) return
  const selectedIds = new Set(
    getNodes.value.filter((n: any) => n.selected).map((n: any) => n.id),
  )
  if (selectedIds.size === 0) return

  const id = generateNodeId('__sub_workflow__', getNodes.value.map((n: any) => n.id))
  const name = generateNodeName(
    'SubWorkflow',
    getNodes.value.map((n: any) => n.data?.name ?? ''),
    'Sub-workflow',
  )
  const result = createSubWorkflowFromSelection({
    nodes: getNodes.value,
    edges: getEdges.value,
    selectedNodeIds: selectedIds,
    subWorkflowId: id,
    subWorkflowName: name,
  })
  attachPublicationContextToNodes(result.nodes as any[])
  setNodes(result.nodes as any)
  setEdges(result.edges)
  uiStore.setCanvasSelectedNodes(canvasId, [id])
  emitGraphChanged()
}

function openSubWorkflow(nodeId: string) {
  const node = getNodes.value.find((n: any) => n.id === nodeId)
  if (!node?.data?.sub_workflow) return null
  const session = subWorkflowSessionsStore.openSession({
    parentWorkflowName: owningWorkflowId(),
    parentSourceWorkflowName: node.data.source_workflow_name ?? null,
    parentNodeId: node.id,
    parentNodeName: node.data.name ?? node.id,
    graph: node.data.sub_workflow,
    published_inputs: node.data.published_inputs ?? [],
    published_outputs: node.data.published_outputs ?? [],
    readonlyReason: node.data.sub_workflow_readonly_reason ?? null,
  })
  window.dispatchEvent(new CustomEvent('bioimageflow:sub-workflow-session-opened', {
    detail: {
      sessionId: session.id,
      parentNodeId: node.id,
      parentCanvasPanelId: canvasPanelId,
    },
  }))
  return session
}

function stablePublishedInputKey(input: PublishedInput): string {
  return `${input.internal_node_id}:${input.internal_field}`
}

function stablePublishedOutputKey(output: PublishedOutput): string {
  return `${output.internal_node_id}:${output.internal_output}`
}

function inputRenameMap(
  previous: PublishedInput[],
  next: PublishedInput[],
): Map<string, string | null> {
  const nextByKey = new Map(next.map((pin) => [stablePublishedInputKey(pin), pin.name]))
  const result = new Map<string, string | null>()
  for (const pin of previous) {
    result.set(pin.name, nextByKey.get(stablePublishedInputKey(pin)) ?? null)
  }
  return result
}

function outputRenameMap(
  previous: PublishedOutput[],
  next: PublishedOutput[],
): Map<string, string | null> {
  const nextByKey = new Map(next.map((pin) => [stablePublishedOutputKey(pin), pin.name]))
  const result = new Map<string, string | null>()
  for (const pin of previous) {
    result.set(pin.name, nextByKey.get(stablePublishedOutputKey(pin)) ?? null)
  }
  return result
}

function reconcilePublishedParentState(
  parentNodeId: string,
  previousInputs: PublishedInput[],
  previousOutputs: PublishedOutput[],
  nextInputs: PublishedInput[],
  nextOutputs: PublishedOutput[],
) {
  const inputNames = new Set(nextInputs.map((pin) => pin.name))
  const inputRenames = inputRenameMap(previousInputs, nextInputs)
  const outputRenames = outputRenameMap(previousOutputs, nextOutputs)
  const nextEdges: any[] = []

  for (const edge of getEdges.value) {
    if (edge.target === parentNodeId && inputRenames.has(edge.targetHandle ?? '')) {
      const nextHandle = inputRenames.get(edge.targetHandle ?? '')
      if (nextHandle === null) continue
      nextEdges.push({ ...edge, targetHandle: nextHandle })
      continue
    }
    if (edge.source === parentNodeId && outputRenames.has(edge.sourceHandle ?? '')) {
      const nextHandle = outputRenames.get(edge.sourceHandle ?? '')
      if (nextHandle === null) continue
      nextEdges.push({ ...edge, sourceHandle: nextHandle })
      continue
    }
    nextEdges.push(edge)
  }
  setEdges(nextEdges)

  const parentNode = getNodes.value.find((n: any) => n.id === parentNodeId)
  if (!parentNode?.data) return

  const nextParameters: Record<string, unknown> = {}
  const currentParameters = parentNode.data.parameters ?? {}
  for (const [key, value] of Object.entries(currentParameters)) {
    if (inputRenames.has(key)) {
      const nextName = inputRenames.get(key)
      if (nextName != null) nextParameters[nextName] = value
      continue
    }
    if (!inputNames.has(key)) {
      nextParameters[key] = value
    }
  }
  for (const pin of nextInputs) {
    if (!(pin.name in nextParameters) && pin.default !== null && pin.default !== undefined) {
      nextParameters[pin.name] = pin.default
    }
  }
  parentNode.data.parameters = nextParameters

  const nextPinnedInputs: Record<string, boolean> = {}
  const currentPinnedInputs = parentNode.data.pinnedInputs ?? {}
  for (const pin of nextInputs) {
    const previous = previousInputs.find(
      (candidate) => stablePublishedInputKey(candidate) === stablePublishedInputKey(pin),
    )
    nextPinnedInputs[pin.name] = previous
      ? currentPinnedInputs[previous.name] !== false
      : true
  }
  parentNode.data.pinnedInputs = nextPinnedInputs

  const connectedInputs: Record<string, string> = {}
  for (const edge of nextEdges) {
    if (edge.target !== parentNodeId || !edge.targetHandle) continue
    connectedInputs[edge.targetHandle] = `${edge.source}.${edge.sourceHandle ?? 'output'}`
  }
  parentNode.data.connectedInputs = connectedInputs
}

function applySubWorkflowDraft(
  parentNodeId: string,
  graph: GraphState,
  publishedInterface: {
    published_inputs?: PublishedInput[]
    published_outputs?: PublishedOutput[]
  } = {},
) {
  const node = getNodes.value.find((n: any) => n.id === parentNodeId)
  if (!node?.data) return
  const previousInputs = deepClone(node.data.published_inputs ?? []) as PublishedInput[]
  const previousOutputs = deepClone(node.data.published_outputs ?? []) as PublishedOutput[]
  const nextInputs = deepClone(
    publishedInterface.published_inputs ?? node.data.published_inputs ?? [],
  ) as PublishedInput[]
  const nextOutputs = deepClone(
    publishedInterface.published_outputs ?? node.data.published_outputs ?? [],
  ) as PublishedOutput[]
  reconcilePublishedParentState(
    parentNodeId,
    previousInputs,
    previousOutputs,
    nextInputs,
    nextOutputs,
  )
  node.data.sub_workflow = deepClone(graph)
  node.data.published_inputs = nextInputs
  node.data.published_outputs = nextOutputs
  if (node.data.status === 'executed') {
    node.data.status = 'out_of_date'
  }
  dataTableStore.clearCanvasCache(canvasId, parentNodeId)
  emitGraphChanged()
}

function saveSubWorkflowSession() {
  const sessionId = props.subWorkflowSessionId
  if (!sessionId) return
  const session = subWorkflowSessionsStore.sessionById(sessionId)
  if (!session) return
  const saved = subWorkflowSessionsStore.saveSession(sessionId)
  uiStore.markCanvasClean(canvasId)
  window.dispatchEvent(new CustomEvent('bioimageflow:apply-sub-workflow-session', {
    detail: {
      sessionId,
      parentNodeId: session.parentNodeId,
      graph: saved.graph,
      published_inputs: saved.published_inputs,
      published_outputs: saved.published_outputs,
    },
  }))
}

function handleApplySubWorkflowSessionEvent(event: CustomEvent<{
  parentNodeId?: string
} & Partial<SubWorkflowApplyPayload>>) {
  const detail = event.detail
  if (!detail?.parentNodeId || !detail.graph) return
  applySubWorkflowDraft(detail.parentNodeId, detail.graph, {
    published_inputs: detail.published_inputs,
    published_outputs: detail.published_outputs,
  })
}

function selectAll() {
  for (const node of getNodes.value) {
    node.selected = true
  }
}

function redoGraphChange() {
  if (isLocked.value) return
  const state = undoRedo.redo()
  if (state) {
    setNodes(state.nodes)
    setEdges(state.edges)
    syncGraph(state as any)
    markDirtyAndAutoSave(state)
  }
}

function undoGraphChange() {
  if (isLocked.value) return
  const state = undoRedo.undo()
  if (state) {
    setNodes(state.nodes)
    setEdges(state.edges)
    syncGraph(state as any)
    markDirtyAndAutoSave(state)
  }
}

function handleEditCommandEvent(event: CustomEvent<{ command?: string }>) {
  if (!isActiveCanvasTab.value) return
  if (isLocked.value) return
  switch (event.detail?.command) {
    case 'undo':
      undoGraphChange()
      break
    case 'redo':
      redoGraphChange()
      break
    case 'cut':
      copySelected()
      deleteSelected()
      break
    case 'copy':
      copySelected()
      break
    case 'paste':
      pasteFromClipboard()
      break
    case 'select-all':
      selectAll()
      break
    case 'create-sub-workflow':
      createSelectedSubWorkflow()
      break
  }
}

function handleKeydown(event: KeyboardEvent) {
  const meta = event.metaKey || event.ctrlKey
  const locked = isLocked.value

  if (event.key === 'Delete' || event.key === 'Backspace') {
    if (locked) return
    deleteSelected()
    return
  }

  if (meta && event.key === 'c') {
    if (locked) return
    copySelected()
    return
  }

  if (meta && event.key === 'v') {
    if (locked) return
    pasteFromClipboard()
    return
  }

  if (meta && event.key === 'a') {
    if (locked) return
    event.preventDefault()
    selectAll()
    return
  }

  if (meta && event.key === 's') {
    event.preventDefault()
    if (locked) return
    if (isSubWorkflowEditor) {
      saveSubWorkflowSession()
    }
    return
  }

  if (meta && event.shiftKey && (event.key === 'z' || event.key === 'Z')) {
    if (locked) return
    redoGraphChange()
    return
  }

  if (meta && event.key === 'z') {
    if (locked) return
    undoGraphChange()
    return
  }

  if (meta && event.key === 'Enter') {
    flushNow()
    return
  }

  if (event.key === 'f' || event.key === 'F') {
    if (!meta && !event.shiftKey && !event.altKey) {
      fitView()
      return
    }
  }
}

// --- Graph change emission ---

function markDirtyAndAutoSave(state: { nodes: any[]; edges: any[] }) {
  const name = owningWorkflowId()
  if (!name) return
  const graph = rememberAuthoritativeGraph(serializeGraph(state) as GraphState)
  uiStore.markCanvasDirty(canvasId)
  queueCanvasPersistence(graph)
}

function emitGraphChanged() {
  const state = currentVueFlowState()
  undoRedo.push(state)
  // Update the reconciliation node list to match the current graph.
  reconciliationNodes.value = state.nodes.map((n: any) => ({
    id: n.id,
    name: n.data?.name ?? n.id,
    tool_name: n.data?.toolName ?? '',
    position: [n.position?.x ?? 0, n.position?.y ?? 0],
    parameters: n.data?.parameters ?? {},
    resources: n.data?.resources ?? {},
    output_templates: n.data?.output_templates ?? {},
    enabled: n.data?.enabled ?? true,
    collapsed: n.data?.collapsed ?? false,
    sub_workflow: n.data?.sub_workflow ?? null,
    published_inputs: n.data?.published_inputs ?? [],
    published_outputs: n.data?.published_outputs ?? [],
    sub_workflow_readonly_reason: n.data?.sub_workflow_readonly_reason ?? null,
    source_workflow_name: n.data?.source_workflow_name ?? null,
  })) as NodeState[]
  // Mark all nodes provisional during the debounce window so the UI can
  // render a desaturated status indicator until the server response lands.
  for (const n of state.nodes) {
    const provisionalStatus = n.data?.status ?? 'unexecuted'
    markProvisional(n.id, provisionalStatus)
    if (n.data) {
      n.data.provisional = true
    }
  }
  if (isSubWorkflowEditor && props.subWorkflowSessionId) {
    syncGraph(state as any)
    const graph = rememberAuthoritativeGraph(serializeGraph(state) as GraphState)
    subWorkflowSessionsStore.updateDraft(props.subWorkflowSessionId, graph)
    uiStore.markCanvasDirty(canvasId)
    emit('graph-changed', state)
    return
  }
  syncGraph(state as any)
  markDirtyAndAutoSave(state)
  emit('graph-changed', state)
}

// Expose for testing
defineExpose({
  onAddNode,
  onAddWorkflowNode,
  wouldCreateWorkflowContainmentCycle,
  deleteSelected,
  copySelected,
  pasteFromClipboard,
  selectAll,
  createSelectedSubWorkflow,
  openSubWorkflow,
  applySubWorkflowDraft,
  saveSubWorkflowSession,
  isValidConnection,
  clipboardData,
  reconciledStatuses,
  syncState,
})
</script>

<template>
  <div
    ref="canvasRef"
    class="canvas-view"
    @drop="onDrop"
    @dragover="onDragOver"
    @keydown="handleKeydown"
    tabindex="0"
  >
    <CanvasErrorBanner :validation-result="validationResult" />
    <div
      v-if="shouldShowRemoteDraftConflict"
      class="workflow-draft-conflict"
      role="alert"
    >
      <div class="workflow-draft-conflict__copy">
        <strong>This workflow changed outside the canvas.</strong>
        <span>Choose which version to keep before continuing.</span>
        <span
          v-if="remoteDraftResolutionMessage"
          class="workflow-draft-conflict__success"
        >
          {{ remoteDraftResolutionMessage }}
        </span>
        <span
          v-if="remoteDraftActionError"
          class="workflow-draft-conflict__error"
        >
          {{ remoteDraftActionError }}
        </span>
      </div>
      <div class="workflow-draft-conflict__actions">
        <button
          type="button"
          class="workflow-draft-conflict__button"
          :disabled="isResolvingRemoteDraftConflict"
          @click="applyAgentDraftChanges"
        >
          Apply agent changes
        </button>
        <button
          type="button"
          class="workflow-draft-conflict__button"
          :disabled="isResolvingRemoteDraftConflict"
          @click="keepCurrentCanvasDraft"
        >
          Keep my canvas
        </button>
        <button
          type="button"
          class="workflow-draft-conflict__button"
          :disabled="isResolvingRemoteDraftConflict"
          @click="saveAgentDraftAsCopy"
        >
          Save agent version as copy
        </button>
      </div>
    </div>
    <div
      v-else-if="remoteDraftResolutionMessage"
      class="workflow-draft-resolution"
      role="status"
    >
      {{ remoteDraftResolutionMessage }}
    </div>
    <VueFlow
      :id="canvasPanelId"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :is-valid-connection="isValidConnection"
      :edges-updatable="true"
      :fit-view-on-init="shouldFitViewOnInit"
      @node-context-menu="onNodeContextMenu"
      @node-double-click="onNodeDoubleClick"
    >
      <Background :variant="'dots'" :gap="16" :size="1" />
      <Controls />
    </VueFlow>
    <NodeContextMenu
      v-if="nodeContextMenu"
      :node-id="nodeContextMenu.nodeId"
      :position="nodeContextMenu.position"
      :enabled="nodeContextMenu.enabled"
      :can-open-sub-workflow="nodeContextMenu.canOpenSubWorkflow"
      @rename="closeNodeContextMenu"
      @enable-toggle="toggleContextNodeEnabled"
      @create-sub-workflow="runContextSubWorkflowAction"
      @open-sub-workflow="runContextSubWorkflowAction"
      @delete="deleteContextNode"
      @close="closeNodeContextMenu"
    />
  </div>
</template>

<style scoped>
.canvas-view {
  width: 100%;
  height: 100%;
  outline: none;
  position: relative;
}

.workflow-draft-conflict,
.workflow-draft-resolution {
  position: absolute;
  z-index: 20;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #d97706;
  border-radius: 6px;
  background: #fffbeb;
  color: #78350f;
  box-shadow: 0 8px 20px rgb(0 0 0 / 12%);
}

.workflow-draft-resolution {
  border-color: #15803d;
  background: #f0fdf4;
  color: #14532d;
}

.workflow-draft-conflict__copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  font-size: 0.9rem;
  line-height: 1.35;
}

.workflow-draft-conflict__error {
  color: #b91c1c;
}

.workflow-draft-conflict__success {
  color: #15803d;
}

.workflow-draft-conflict__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.workflow-draft-conflict__button {
  border: 1px solid #d97706;
  border-radius: 6px;
  background: #ffffff;
  color: #78350f;
  cursor: pointer;
  font: inherit;
  font-size: 0.85rem;
  line-height: 1.2;
  padding: 6px 10px;
}

.workflow-draft-conflict__button:disabled {
  cursor: progress;
  opacity: 0.65;
}

@media (max-width: 720px) {
  .workflow-draft-conflict,
  .workflow-draft-resolution {
    align-items: stretch;
    flex-direction: column;
  }

  .workflow-draft-conflict__actions {
    justify-content: flex-start;
  }
}
</style>
