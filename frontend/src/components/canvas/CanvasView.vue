<script setup lang="ts">
import { computed, ref, watch, markRaw, nextTick, onMounted, onBeforeUnmount, provide } from 'vue'
import { VueFlow, useVueFlow, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import ToolNode from './ToolNode.vue'
import ColumnEdge from './ColumnEdge.vue'
import DataFrameEdge from './DataFrameEdge.vue'
import CanvasErrorBanner from './CanvasErrorBanner.vue'
import CanvasPersistenceFeedback from './CanvasPersistenceFeedback.vue'
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
import { serializeGraph as serializeCanvasGraph, useGraphSync } from '@/composables/useGraphSync'
import {
  useCanvasPersistence,
  type CanvasPersistenceIssue,
  type CanvasPersistenceState,
} from '@/composables/useCanvasPersistence'
import {
  useCanvasCommands,
  type CanvasInterfaceCommandResult,
  type CanvasInterfaceRejectionReason,
} from '@/composables/useCanvasCommands'
import { useExecutionLock } from '@/composables/useExecutionLock'
import {
  CANVAS_STATUS_PROJECTION_KEY,
  useCanvasStatusProjection,
} from '@/composables/useCanvasStatusProjection'
import { useValidationErrors } from '@/composables/useValidationErrors'
import { useErrorReporting } from '@/composables/useErrorReporting'
import {
  useFieldFocusTracker,
  type FieldFocusTarget,
} from '@/composables/useFieldFocusTracker'
import { useExecutionStore } from '@/stores/execution'
import { useDataTableStore } from '@/stores/dataTable'
import { useResolvedOutputsStore } from '@/stores/resolvedOutputs'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { useCanvasLifecycleStore } from '@/stores/canvasLifecycle'
import { graphStateToVueFlow } from '@/utils/workflowGraph'
import { reconcileOutputTemplates } from '@/utils/outputTemplates'
import { groupIntoWorkflow } from '@/utils/workflowGrouping'
import type { GraphState, MissingTool, WorkflowInput, WorkflowOutput, WorkflowInfo } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import { api } from '@/api/client'
import { useToast } from 'primevue/usetoast'
import type { ClipboardPayload, PasteSummary } from '@/utils/clipboard'
import type { ToolMetadata } from '@/api/types'
import type { WorkflowSourcePreview } from '@/api/types'
import {
  applyWorkflowSourceOperation,
  previewWorkflowSourceUpdate,
} from '@/api/workflowSources'
import { resetWorkflowDraftToSaved } from '@/api/workflowDrafts'
import { loadRootWorkflowPresentation } from '@/services/rootWorkflowPresentation'
import {
  useNestedWorkflowSessionsStore,
  type NestedWorkflowParentConflictReason,
} from '@/stores/nestedWorkflowSessions'
import {
  canvasIdFromPanelId,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'
import { graphDocumentsEqual } from '@/sessions/graphDocument'
import { isNestedSnapshotPersistenceConflict } from '@/sessions/nestedSnapshotPersistence'
import { connectionSourceLabel } from '@/utils/displayNames'
import {
  decodeEndpointHandle,
  encodeEndpointHandle,
  isDataFrameEndpoint,
} from '@/utils/endpointHandles'

const emit = defineEmits<{
  'graph-changed': [payload: { nodes: any[]; edges: any[] }]
  'node-selected': [nodeIds: string[]]
}>()

const props = defineProps<{
  nestedWorkflowSessionId?: string
  parentCanvasPanelId?: string
  params?: {
    panelId?: string
    parentCanvasPanelId?: string
    workflowName?: string
    workflowDisplayName?: string
    graph?: GraphState
    missingTools?: MissingTool[]
    dirty?: boolean
    draft?: WorkflowDraftResponse
    params?: {
      panelId?: string
      parentCanvasPanelId?: string
      workflowName?: string
      workflowDisplayName?: string
      graph?: GraphState
      missingTools?: MissingTool[]
      dirty?: boolean
      draft?: WorkflowDraftResponse
    }
  }
}>()

// Vue Flow's NodeTypesObject/EdgeTypesObject uses very strict component
// constraints that Vue's SFC-inferred types don't satisfy. The runtime
// contract (`key -> component`) is what VueFlow actually uses.
const nodeTypes = {
  tool: markRaw(ToolNode),
  workflow: markRaw(ToolNode),
} as unknown as Record<string, object>

const edgeTypes = {
  column: markRaw(ColumnEdge),
  dataframe: markRaw(DataFrameEdge),
} as unknown as Record<string, object>

const toolRegistryStore = useToolRegistryStore()
const uiStore = useUIStore()
const workflowStore = useWorkflowStore()
const workflowDraftStore = useWorkflowDraftStore()
const nestedWorkflowSessionsStore = useNestedWorkflowSessionsStore()
const resolvedOutputsStore = useResolvedOutputsStore()
const dataTableStore = useDataTableStore()
const isNestedWorkflowEditor = props.nestedWorkflowSessionId != null && props.nestedWorkflowSessionId !== ''
const canvasPanelId = componentPanelId()
const canvasId = canvasIdFromPanelId(canvasPanelId)
const initialCanvasParams = dockviewParams()
const initialNestedSession = props.nestedWorkflowSessionId
  ? nestedWorkflowSessionsStore.sessionById(props.nestedWorkflowSessionId)
  : null
if (isNestedWorkflowEditor && !initialNestedSession) {
  throw new Error('Nested CanvasView requires an accepted durable snapshot session')
}
const nestedParentCanvasPanelId = initialNestedSession?.parentCanvasId
const ownedWorkflowName = ref<string | null>(
  isNestedWorkflowEditor
    ? initialNestedSession?.parentWorkflowName ?? null
    : initialCanvasParams?.workflowName ?? workflowStore.currentName ?? null,
)
const ownedWorkflowDisplayName = ref<string | null>(
  isNestedWorkflowEditor
    ? initialNestedSession?.parentNodeName ?? null
    : initialCanvasParams?.workflowDisplayName
      ?? workflowStore.current?.display_name
      ?? null,
)

// ToolNode must always read the map owned by this mounted canvas.
dataTableStore.registerCanvas(canvasId)
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

function canvasConnectionSourceLabel(
  sourceNode: any,
  sourceHandle: string | null | undefined,
): string {
  const resolvedOutput = sourceNode?.id && sourceHandle
    ? canvasResolvedOutputs[sourceNode.id]?.columns?.[sourceHandle]
    : undefined
  return connectionSourceLabel(sourceNode, sourceHandle, resolvedOutput)
}

function refreshConnectedInputLabels(): void {
  for (const edge of getEdges.value) {
    if (!edge.targetHandle) continue
    const sourceNode = getNodes.value.find((node: any) => node.id === edge.source)
    const targetNode = getNodes.value.find((node: any) => node.id === edge.target)
    if (!targetNode?.data) continue
    targetNode.data.connectedInputs = {
      ...(targetNode.data.connectedInputs ?? {}),
      [edge.targetHandle]: canvasConnectionSourceLabel(
        sourceNode ?? { id: edge.source },
        edge.sourceHandle,
      ),
    }
  }
}

watch(canvasResolvedOutputs, refreshConnectedInputLabels, { deep: true })

const canvasDescriptor: CanvasSessionDescriptor = isNestedWorkflowEditor
    ? {
        kind: 'nested',
        canvasId,
        sessionId: props.nestedWorkflowSessionId!,
        parentCanvasId: canvasIdFromPanelId(nestedParentCanvasPanelId!),
      }
    : {
        kind: 'root',
        canvasId,
        workflowId: initialCanvasParams?.workflowName ?? null,
      }
const canvasPersistence = useCanvasPersistence({
  descriptor: canvasDescriptor,
  getWorkflowId: owningWorkflowId,
})
if (!isNestedWorkflowEditor && initialCanvasParams?.draft) {
  canvasPersistence.initializeFromDraft(initialCanvasParams.draft)
}
const graphSync = useGraphSync({
  descriptor: canvasDescriptor,
  getWorkflowId: owningWorkflowId,
  nestedSnapshot: initialNestedSession && props.nestedWorkflowSessionId
    ? {
        initialSnapshot: nestedWorkflowSessionsStore.snapshotForSession(
          props.nestedWorkflowSessionId,
        ),
        onAccepted: snapshot => nestedWorkflowSessionsStore.acceptSnapshot(
          props.nestedWorkflowSessionId!,
          snapshot,
        ),
      }
    : undefined,
})
const canvasCommands = useCanvasCommands({
  descriptor: canvasDescriptor,
  save: isNestedWorkflowEditor ? () => saveNestedWorkflowSession() : undefined,
  addToolNode: (toolName, parameters) => onAddNode({
    toolName,
    parameters,
    position: canvasCenterPosition(),
  }),
  renameNode,
  setNodeEnabled,
  setInputPinned,
  setOutputTemplate,
  toggleWorkflowInput,
  toggleWorkflowOutput,
  renameWorkflowInput,
  renameWorkflowOutput,
  updateParameter: updateNodeParameter,
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
  revalidateGraphState,
  flushNow,
  resolveConflictKeepingLocal,
  resolveConflictUsingRemote,
  validationResult,
  syncState,
  dispose: disposeGraphSync,
} = graphSync
const graphSyncLastError = graphSync.lastError ?? ref<unknown | null>(null)
const {
  queueGraph: queueCanvasPersistence,
  initializeFromDraft: initializeCanvasPersistenceFromDraft,
  resolveFromDraft: resolveCanvasPersistenceFromDraft,
  isPending: isCanvasPersistencePending,
  dispose: disposeCanvasPersistence,
} = canvasPersistence
const rootPersistenceState = canvasPersistence.persistenceState
  ?? ref<CanvasPersistenceState>('idle')
const rootPersistenceIssue = canvasPersistence.persistenceIssue
  ?? ref<CanvasPersistenceIssue | null>(null)
const rootPersistenceHasConflict = canvasPersistence.hasConflict ?? ref(false)
const { edgeErrors } = useValidationErrors(validationResult)
const { reportError } = useErrorReporting()
const undoRedo = useUndoRedo<CanvasHistoryState>()
const executionLock = useExecutionLock()
const canvasLifecycleStore = useCanvasLifecycleStore()
const lifecycleOperation = computed(() => canvasLifecycleStore.operationFor(canvasId))
const nestedConflictResolution = ref<'keep-local' | 'use-remote' | null>(null)
const isInstallingAuthoritativeDraft = ref(false)
const isLocked = computed(() => (
  executionLock.isLocked.value
  || lifecycleOperation.value !== null
  || nestedConflictResolution.value !== null
  || isInstallingAuthoritativeDraft.value
))
const executionStore = useExecutionStore()
const fieldFocusTracker = useFieldFocusTracker()
const statusNodes = computed(() => getNodes.value.map(node => ({
  id: node.id,
  enabled: node.data?.enabled !== false,
})))
const canvasStatusProjection = useCanvasStatusProjection({
  descriptor: canvasDescriptor,
  nodes: statusNodes,
  validationResult,
  acceptedDraftRevision: canvasPersistence.acceptedDraftRevision,
})
const projectedStatuses = canvasStatusProjection.statuses
provide(CANVAS_STATUS_PROJECTION_KEY, canvasStatusProjection)

function applyValidationEdgeErrors(): void {
  // Mirror per-edge validation errors so edge components can render them.
  const byEdge = edgeErrors.value
  for (const edge of getEdges.value) {
    const errs = byEdge[edge.id] ?? []
    const prev = (edge.data as { errors?: unknown[] } | undefined)?.errors ?? []
    if (errs.length === 0 && prev.length === 0) continue
    edge.data = { ...(edge.data ?? {}), errors: errs }
  }
}

watch(validationResult, applyValidationEdgeErrors, { deep: true })

const clipboardData = ref<ClipboardPayload | null>(getMemoryClipboardPayload())
const canvasRef = ref<HTMLDivElement | null>(null)
const nodeContextMenu = ref<{
  nodeId: string
  position: { x: number; y: number }
  enabled: boolean
  canOpenNestedWorkflow: boolean
  hasWorkspaceSource: boolean
  sourceWorkflowId: string | null
} | null>(null)
const dragStartPositions = ref<Record<string, { x: number; y: number }>>({})
const rootWorkflowInputs = ref<WorkflowInput[]>([])
const rootWorkflowOutputs = ref<WorkflowOutput[]>([])
const lastAuthoritativeGraph = ref<GraphState | null>(null)
const isActiveCanvasTab = ref(true)
const hasLoadedGraphState = ref(false)
const remoteDraftAction = ref<'apply' | 'keep' | 'copy' | null>(null)
const remoteDraftActionError = ref<string | null>(null)
const remoteDraftResolutionMessage = ref<string | null>(null)
const nestedPersistenceIssue = ref<CanvasPersistenceIssue | null>(null)
let nestedPersistenceIssueVersion = 0
let nestedPersistenceError: unknown = null
let isApplyingGraphState = false
let isCanvasUnmounted = false
let isAutoApplyingRemoteDraft = false
let rootEditEpoch = 0
let hotReloadToast: ReturnType<typeof useToast> | null = null
let clipboardToast: ReturnType<typeof useToast> | null = null

const hasLocalRemoteDraftConflict = computed(() => (
  uiStore.canvasHasUnsavedChanges(canvasId) || isCanvasPersistencePending.value
))

const isPendingFrontendDraftEcho = computed(() => (
  rootPersistenceState.value === 'saving'
  && workflowDraftStore.remoteUpdatedBy === 'frontend'
  && !rootPersistenceHasConflict.value
))

const shouldShowRemoteDraftConflict = computed(() => {
  if (isNestedWorkflowEditor) return false
  if (!isActiveCanvasTab.value) return false
  if (!hasLoadedGraphState.value) return false
  if (
    workflowDraftStore.remoteAvailableRevision === null
    && !rootPersistenceHasConflict.value
  ) return false
  if (isPendingFrontendDraftEcho.value) return false
  if (!hasLocalRemoteDraftConflict.value) return false
  const workflowName = workflowIdentity().workflowName
  return typeof workflowName === 'string'
    && workflowName.length > 0
    && workflowDraftStore.workflowId === workflowName
})

const nestedPersistenceState = computed<CanvasPersistenceState>(() => {
  if (!isNestedWorkflowEditor) return 'idle'
  if (syncState.value === 'pending') return 'saving'
  if (syncState.value === 'conflict') return 'conflict'
  if (syncState.value === 'error') return 'error'
  return 'idle'
})

watch(
  [syncState, graphSyncLastError],
  ([state, error]) => {
    if (
      !isNestedWorkflowEditor
      || (state !== 'error' && state !== 'conflict')
    ) {
      nestedPersistenceError = null
      nestedPersistenceIssue.value = null
      return
    }
    if (
      nestedPersistenceIssue.value !== null
      && nestedPersistenceError === error
    ) return
    nestedPersistenceError = error
    nestedPersistenceIssueVersion += 1
    const isConflict = state === 'conflict'
      && isNestedSnapshotPersistenceConflict(error)
    const errorDetail = error instanceof Error ? error.message.trim() : ''
    const conflictRevision = isConflict ? error.currentRevision : null
    const detail = isConflict
      ? `${errorDetail || 'The nested-workflow changed elsewhere.'} `
        + `${conflictRevision === null ? '' : `The current revision is ${conflictRevision}. `}`
        + 'Use latest snapshot replaces this canvas with that version. '
        + 'Keep my changes retries the latest local snapshot against that revision.'
      : errorDetail.length > 0
        ? `Your latest nested-workflow changes remain on this canvas. ${errorDetail}`
        : 'Your latest nested-workflow changes remain on this canvas.'
    nestedPersistenceIssue.value = {
      id: `${canvasId}:nested-persistence:${nestedPersistenceIssueVersion}`,
      version: nestedPersistenceIssueVersion,
      kind: isConflict ? 'conflict' : 'error',
      source: 'draft',
      summary: isConflict
        ? 'nested-workflow changes need attention'
        : 'nested-workflow changes could not be saved',
      detail,
      dismissed: false,
    }
  },
  { flush: 'sync', immediate: true },
)

const canvasPersistenceFeedbackState = computed<CanvasPersistenceState>(() => {
  if (lifecycleOperation.value !== null || shouldShowRemoteDraftConflict.value) {
    return 'idle'
  }
  if (isNestedWorkflowEditor) return nestedPersistenceState.value
  return rootPersistenceState.value === 'conflict'
    ? 'idle'
    : rootPersistenceState.value
})

const canvasPersistenceFeedbackIssue = computed<CanvasPersistenceIssue | null>(() => {
  if (shouldShowRemoteDraftConflict.value) return null
  const issue = isNestedWorkflowEditor
    ? nestedPersistenceIssue.value
    : rootPersistenceIssue.value
  return !isNestedWorkflowEditor && issue?.kind === 'conflict' ? null : issue
})

async function retryCanvasPersistence(issueId: string): Promise<void> {
  const issue = canvasPersistenceFeedbackIssue.value
  if (issue === null || issue.id !== issueId) return
  try {
    if (isNestedWorkflowEditor) {
      await flushNow()
    } else {
      await canvasPersistence.retryPersistence()
    }
  } catch {
    // The canonical persistence resource retains and republishes the issue.
  }
}

async function resolveCanvasPersistenceConflict(issueId: string): Promise<void> {
  const issue = canvasPersistenceFeedbackIssue.value
  if (
    !isNestedWorkflowEditor
    || issue === null
    || issue.id !== issueId
    || issue.kind !== 'conflict'
    || nestedConflictResolution.value !== null
  ) return
  nestedConflictResolution.value = 'keep-local'
  try {
    await resolveConflictKeepingLocal()
  } catch {
    // The canonical nested persistence resource retains the unresolved issue.
  } finally {
    nestedConflictResolution.value = null
  }
}

async function useLatestNestedPersistenceSnapshot(issueId: string): Promise<void> {
  const issue = canvasPersistenceFeedbackIssue.value
  const sessionId = props.nestedWorkflowSessionId
  if (
    !isNestedWorkflowEditor
    || !sessionId
    || issue === null
    || issue.id !== issueId
    || issue.kind !== 'conflict'
    || nestedConflictResolution.value !== null
  ) return
  nestedConflictResolution.value = 'use-remote'
  try {
    const accepted = await resolveConflictUsingRemote()
    if (accepted === null || isCanvasUnmounted) return
    nestedWorkflowSessionsStore.updateDraft(sessionId, accepted.graph)
    await applyGraphState(accepted.graph, [], false, false)
    if (nestedWorkflowSessionsStore.isDirty(sessionId)) {
      uiStore.markCanvasDirty(canvasId)
    } else {
      uiStore.markCanvasClean(canvasId)
    }
  } catch {
    // The canonical nested persistence resource retains the unresolved issue.
  } finally {
    nestedConflictResolution.value = null
  }
}

function dismissCanvasPersistenceIssue(issueId: string): void {
  if (isNestedWorkflowEditor) {
    const issue = nestedPersistenceIssue.value
    if (issue === null || issue.id !== issueId || issue.dismissed) return
    nestedPersistenceIssue.value = { ...issue, dismissed: true }
    return
  }
  canvasPersistence.dismissPersistenceIssue(issueId)
}

function reopenCanvasPersistenceConflict(issueId: string): void {
  if (!isNestedWorkflowEditor) return
  const issue = nestedPersistenceIssue.value
  if (
    issue === null
    || issue.id !== issueId
    || issue.kind !== 'conflict'
    || !issue.dismissed
  ) return
  nestedPersistenceIssue.value = { ...issue, dismissed: false }
}

const isResolvingRemoteDraftConflict = computed(() => remoteDraftAction.value !== null)

const shouldFitViewOnInit = computed(() => {
  const params = dockviewParams()
  if (Array.isArray(params?.graph?.nodes)) return params.graph.nodes.length > 0
  return false
})

interface NestedWorkflowApplyPayload {
  graph: GraphState
}

type NestedWorkflowParentApplyResult =
  | { status: 'applied' }
  | { status: 'conflict'; reason: NestedWorkflowParentConflictReason }
  | { status: 'rejected'; reason: 'locked' }

interface InterfaceContext {
  parentNodeId?: string
  inputs: WorkflowInput[]
  outputs: WorkflowOutput[]
}

interface CanvasVueFlowState {
  nodes: any[]
  edges: any[]
  interface?: GraphState['interface']
}

interface CanvasHistoryState extends CanvasVueFlowState {
  interface: GraphState['interface']
}

interface GraphChangeOptions {
  state?: CanvasVueFlowState
  authoritativeGraph?: GraphState
  statusesAlreadyStaged?: boolean
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function rememberAuthoritativeGraph(graph: GraphState): GraphState {
  const snapshot = deepClone(graph)
  lastAuthoritativeGraph.value = snapshot
  return snapshot
}

function serializeGraph(state: CanvasVueFlowState): GraphState {
  const previous = lastAuthoritativeGraph.value
  const identity = workflowIdentity()
  const context = currentInterfaceContext()
  return serializeCanvasGraph({
    ...state,
    schema_version: previous?.schema_version ?? 1,
    name: previous?.name ?? identity.workflowName ?? 'workflow',
    display_name: previous?.display_name
      ?? identity.workflowDisplayName
      ?? identity.workflowName
      ?? 'Workflow',
    interface: state.interface ?? (context
      ? { inputs: context.inputs, outputs: context.outputs }
      : { inputs: [], outputs: [] }),
    config: previous?.config,
  })
}

function graphWithAuthoritativeEdges(state: {
  nodes: any[]
  edges: any[]
  interface?: GraphState['interface']
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
  if (props.nestedWorkflowSessionId) {
    return `nested-workflow:${encodeURIComponent(props.nestedWorkflowSessionId)}`
  }
  const panelId = dockviewParams()?.panelId
  if (!panelId) {
    throw new Error('Root CanvasView requires a canonical workflow panel id')
  }
  return panelId
}

function workflowIdentity() {
  return {
    workflowName: ownedWorkflowName.value,
    workflowDisplayName: ownedWorkflowDisplayName.value,
  }
}

function owningWorkflowId(): string | null {
  if (!props.nestedWorkflowSessionId) return ownedWorkflowName.value
  return nestedWorkflowSessionsStore.sessionById(props.nestedWorkflowSessionId)
    ?.parentWorkflowName ?? ownedWorkflowName.value
}

function workflowInfoId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

function workflowUrl(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/')
}

type GraphLike = { nodes?: unknown[] }

function nestedGraphFromNode(node: any): GraphLike | null {
  const graph = node?.workflow ?? node?.data?.workflow
  return graph && typeof graph === 'object' ? graph as GraphLike : null
}

function sourceWorkflowNameFromNode(node: any): string | null {
  const source = node?.source ?? node?.data?.source
  return source?.kind === 'workspace' && typeof source.workflow_id === 'string'
    ? source.workflow_id
    : null
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
  if (!isNestedWorkflowEditor) {
    const name = workflowIdentity().workflowName
    return typeof name === 'string' ? [name] : []
  }
  if (!props.nestedWorkflowSessionId) return []
  const session = nestedWorkflowSessionsStore.sessionById(props.nestedWorkflowSessionId)
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

function currentInterfaceContext(): InterfaceContext | null {
  if (!isNestedWorkflowEditor) {
    return {
      inputs: rootWorkflowInputs.value,
      outputs: rootWorkflowOutputs.value,
    }
  }
  if (!props.nestedWorkflowSessionId) return null
  const session = nestedWorkflowSessionsStore.sessionById(props.nestedWorkflowSessionId)
  if (!session) return null
  return {
    parentNodeId: session.parentNodeId,
    inputs: session.draft.interface.inputs,
    outputs: session.draft.interface.outputs,
  }
}

function attachInterfaceContext(node: any) {
  const context = currentInterfaceContext()
  if (!context) return node
  node.data ??= {}
  node.data.workflowInterfaceContext = context
  if (isNestedWorkflowEditor) {
    node.data.nestedWorkflowContext = context
  }
  return node
}

function attachInterfaceContextToNodes(nodes: any[]) {
  return nodes.map((node) => attachInterfaceContext(node))
}

function refreshInterfaceContextOnNodes(): void {
  for (const node of getNodes.value) attachInterfaceContext(node)
}

function replaceWorkflowInterface(
  inputs: WorkflowInput[],
  outputs: WorkflowOutput[],
): boolean {
  if (!isNestedWorkflowEditor) {
    rootWorkflowInputs.value = inputs
    rootWorkflowOutputs.value = outputs
    refreshInterfaceContextOnNodes()
    return true
  }
  if (!props.nestedWorkflowSessionId) return false
  const session = nestedWorkflowSessionsStore.sessionById(props.nestedWorkflowSessionId)
  if (!session) return false
  session.draft = {
    ...session.draft,
    interface: { inputs: deepClone(inputs), outputs: deepClone(outputs) },
  }
  refreshInterfaceContextOnNodes()
  return true
}

function replaceWorkflowInputs(inputs: WorkflowInput[]): boolean {
  const context = currentInterfaceContext()
  if (!context) return false
  return replaceWorkflowInterface(inputs, context.outputs)
}

function replaceWorkflowOutputs(outputs: WorkflowOutput[]): boolean {
  const context = currentInterfaceContext()
  if (!context) return false
  return replaceWorkflowInterface(context.inputs, outputs)
}

// --- Workflow startup / graph application ---

async function applyGraphState(
  graph: GraphState,
  missingTools: MissingTool[] = [],
  dirty = false,
  synchronize = true,
) {
  if (isCanvasUnmounted) return
  if (!isNestedWorkflowEditor) {
    rootWorkflowInputs.value = deepClone(graph.interface.inputs)
    rootWorkflowOutputs.value = deepClone(graph.interface.outputs)
  }
  const vueFlowGraph = graphStateToVueFlow(
    graph,
    toolRegistryStore.getToolByName,
    missingTools,
  )
  attachInterfaceContextToNodes(vueFlowGraph.nodes)
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
    refreshConnectedInputLabels()
    applyValidationEdgeErrors()
    if (isCanvasUnmounted) return
    const authoritativeGraph = rememberAuthoritativeGraph(graph)
    if (synchronize) syncGraphState(authoritativeGraph)
    undoRedo.clear()
    undoRedo.push(canvasHistoryState(currentVueFlowState(), authoritativeGraph))
    if (!isNestedWorkflowEditor) {
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
    requestToolReconciliation()
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

async function handleRestoreSavedCanvasEvent(event: Event): Promise<void> {
  const detail = (event as CustomEvent<{
    canvasId?: string
    draft?: WorkflowDraftResponse
    handled?: boolean
    resolve?: () => void
    reject?: (error: unknown) => void
  }>).detail
  if (detail?.canvasId !== canvasId || !detail.draft) return
  detail.handled = true
  try {
    await applyGraphState(detail.draft.graph, workflowStore.missingTools, false)
    detail.resolve?.()
  } catch (error) {
    detail.reject?.(error)
  }
}

function trackDraftWorkflowForActiveRootCanvas(): void {
  if (isNestedWorkflowEditor) return
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

function remoteDraftActionSupersededMessage(): void {
  remoteDraftActionError.value = 'The canvas changed while that request was pending. Review the latest canvas and choose again.'
}

async function installAuthoritativeRootDraft(
  draft: WorkflowDraftResponse,
): Promise<boolean> {
  if (isCanvasUnmounted) return false
  isInstallingAuthoritativeDraft.value = true
  try {
    await applyGraphState(
      draft.graph,
      workflowStore.missingTools,
      draft.dirty_against_saved,
    )
    if (isCanvasUnmounted) return false
    resolveCanvasPersistenceFromDraft(draft)
    workflowDraftStore.acknowledgeAcceptedDraft(draft)
    return true
  } finally {
    isInstallingAuthoritativeDraft.value = false
    requestToolReconciliation()
  }
}

async function applyAgentDraftChanges(): Promise<void> {
  const workflowName = currentWorkflowName()
  if (!workflowName || isResolvingRemoteDraftConflict.value) return
  const editEpoch = rootEditEpoch
  remoteDraftAction.value = 'apply'
  remoteDraftActionError.value = null
  remoteDraftResolutionMessage.value = null
  try {
    const draft = await workflowDraftStore.fetchLatestDraft(workflowName)
    const currentRemoteRevision = workflowDraftStore.remoteAvailableRevision
    if (
      isCanvasUnmounted
      || rootEditEpoch !== editEpoch
      || lifecycleOperation.value !== null
      || currentWorkflowName() !== workflowName
      || workflowDraftStore.workflowId !== workflowName
      || (
        currentRemoteRevision !== null
        && draft.draft_revision < currentRemoteRevision
      )
    ) {
      remoteDraftActionSupersededMessage()
      return
    }
    await installAuthoritativeRootDraft(draft)
  } catch (err) {
    showRemoteDraftActionError('Could not apply agent changes', err)
  } finally {
    remoteDraftAction.value = null
  }
}

async function keepCurrentCanvasDraft(): Promise<void> {
  const workflowName = currentWorkflowName()
  if (!workflowName || isResolvingRemoteDraftConflict.value) return
  const editEpoch = rootEditEpoch
  const submittedGraph = currentSerializedGraph()
  remoteDraftAction.value = 'keep'
  remoteDraftActionError.value = null
  remoteDraftResolutionMessage.value = null
  try {
    const response = await workflowDraftStore.overwriteDraftWithGraph(
      workflowName,
      submittedGraph,
    )
    if (isCanvasUnmounted) return
    const hasNewerLocalEdit = rootEditEpoch !== editEpoch
    const latestGraph = hasNewerLocalEdit ? currentSerializedGraph() : null
    resolveCanvasPersistenceFromDraft(response)
    if (latestGraph !== null) {
      queueCanvasPersistence(latestGraph)
      uiStore.markCanvasDirty(canvasId)
    } else {
      markWorkflowDirtyFromDraft(response.dirty_against_saved)
    }
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

function toolSignature(tool: ToolMetadata): string {
  return JSON.stringify(tool)
}

function registrySignatures(tools: ToolMetadata[]): Map<string, string> {
  return new Map(tools.map(tool => [tool.name, toolSignature(tool)]))
}

let previousToolRegistry = registrySignatures(toolRegistryStore.tools)
const pendingToolNames = new Set<string>()
const pendingToolRenames = new Map<string, string>()
const registeredFocusDeferrals = new Set<string>()
const removedFocusedFields = new Set<string>()
let toolReconciliationScheduled = false

function fieldFocusKey(target: FieldFocusTarget): string {
  return JSON.stringify([target.canvasId, target.nodeId, target.fieldName])
}

function resolveRenamedToolName(toolName: string): string {
  let current = toolName
  const visited = new Set<string>()
  while (pendingToolRenames.has(current) && !visited.has(current)) {
    visited.add(current)
    current = pendingToolRenames.get(current)!
  }
  return current
}

function sameJson(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

function missingToolFor(nodeId: string, toolName: string): MissingTool {
  return {
    node_id: nodeId,
    tool_name: toolName,
    installed_versions: [],
  }
}

function warnRemovedFocusedField(fieldName: string): void {
  hotReloadToast?.add({
    severity: 'warn',
    summary: 'Tool reloaded',
    detail: `Field '${fieldName}' was removed by the tool update.`,
    life: 5000,
  })
}

function deferToolReconciliation(
  freshTool: ToolMetadata | null,
  focusedFields: FieldFocusTarget[],
): void {
  for (const target of focusedFields) {
    const key = fieldFocusKey(target)
    if (freshTool && Object.prototype.hasOwnProperty.call(
      freshTool.inputs,
      target.fieldName,
    )) {
      removedFocusedFields.delete(key)
    } else {
      removedFocusedFields.add(key)
    }
    if (registeredFocusDeferrals.has(key)) continue
    registeredFocusDeferrals.add(key)
    fieldFocusTracker.onBlurOnce(target, () => {
      registeredFocusDeferrals.delete(key)
      if (removedFocusedFields.delete(key)) {
        warnRemovedFocusedField(target.fieldName)
      }
      requestToolReconciliation()
    })
  }
}

function requestToolReconciliation(): void {
  if (
    pendingToolNames.size === 0
    || toolReconciliationScheduled
    || isCanvasUnmounted
    || isLocked.value
  ) return
  toolReconciliationScheduled = true
  void Promise.resolve().then(() => {
    toolReconciliationScheduled = false
    reconcilePendingToolState()
  })
}

function reconcilePendingToolState(): void {
  if (pendingToolNames.size === 0 || isCanvasUnmounted) return
  if (
    isLocked.value
    || toolRegistryStore.customToolBusy
    || isApplyingGraphState
  ) return

  let serializedChanged = false
  let runtimeChanged = false
  const deferredNames = new Set<string>()

  for (const node of getNodes.value as any[]) {
    const originalName = node.data?.toolName
    if (node.type !== 'tool' || typeof originalName !== 'string') continue
    if (!pendingToolNames.has(originalName) && !pendingToolRenames.has(originalName)) continue

    const resolvedName = resolveRenamedToolName(originalName)
    const renameChanged = resolvedName !== originalName
    const freshTool = toolRegistryStore.getToolByName(resolvedName) ?? null
    if (renameChanged && freshTool === null) {
      deferredNames.add(originalName)
      continue
    }

    const currentParameters = node.data.parameters ?? {}
    const nextParameters: Record<string, unknown> = {}
    if (freshTool) {
      for (const [key, value] of Object.entries(currentParameters)) {
        if (Object.prototype.hasOwnProperty.call(freshTool.inputs, key)) {
          nextParameters[key] = value
        }
      }
    }
    const nextTemplates = freshTool
      ? reconcileOutputTemplates(freshTool, node.data.output_templates ?? {})
      : node.data.output_templates ?? {}
    const parametersChanged = freshTool !== null
      && !sameJson(currentParameters, nextParameters)
    const templatesChanged = freshTool !== null
      && !sameJson(node.data.output_templates ?? {}, nextTemplates)
    const metadataChanged = freshTool !== null
      && !sameJson(node.data.tool ?? null, freshTool)
    const missingTool = freshTool === null
      ? missingToolFor(node.id, resolvedName)
      : null
    const missingStateChanged = freshTool === null
      ? node.data.tool !== null || !sameJson(node.data.missingTool ?? null, missingTool)
      : node.data.missingTool != null
    const needsReconciliation = renameChanged
      || metadataChanged
      || missingStateChanged
      || parametersChanged
      || templatesChanged
    if (!needsReconciliation) continue

    const focusedFields = fieldFocusTracker.focusedFields(canvasId, node.id)
    if (focusedFields.length > 0) {
      deferToolReconciliation(freshTool, focusedFields)
      deferredNames.add(originalName)
      continue
    }

    if (freshTool === null) {
      node.data.tool = null
      node.data.missingTool = missingTool
      node.data.updatedBadge = false
      runtimeChanged = true
      continue
    }

    if (renameChanged) {
      node.data.toolName = resolvedName
      serializedChanged = true
    }
    if (metadataChanged || missingStateChanged || renameChanged) {
      node.data.tool = freshTool
      node.data.missingTool = null
      node.data.updatedBadge = true
      runtimeChanged = true
    }
    if (parametersChanged) {
      node.data.parameters = nextParameters
      serializedChanged = true
    }
    if (templatesChanged) {
      node.data.output_templates = nextTemplates
      serializedChanged = true
    }
  }

  for (const name of [...pendingToolNames]) {
    if (!deferredNames.has(name)) pendingToolNames.delete(name)
  }

  // A focused A -> B -> C rename retains A as the pending node identity.
  // Preserve every mapping reachable from that identity until it can apply.
  const requiredRenameKeys = new Set<string>()
  for (const pendingName of pendingToolNames) {
    let current = pendingName
    while (
      pendingToolRenames.has(current)
      && !requiredRenameKeys.has(current)
    ) {
      requiredRenameKeys.add(current)
      current = pendingToolRenames.get(current)!
    }
  }
  for (const oldName of [...pendingToolRenames.keys()]) {
    if (!requiredRenameKeys.has(oldName)) pendingToolRenames.delete(oldName)
  }

  if (!serializedChanged && !runtimeChanged) return
  const state = currentVueFlowState()
  const graph = graphWithAuthoritativeEdges(state)
  if (serializedChanged) {
    emitGraphChanged({ authoritativeGraph: graph })
    return
  }
  stageGraphValidation()
  revalidateGraphState(rememberAuthoritativeGraph(graph))
}

function handleToolRenamedEvent(event: Event) {
  const detail = (event as CustomEvent<{ old_name: string; new_name: string }>).detail
  if (!detail?.old_name || !detail?.new_name) return
  pendingToolRenames.set(detail.old_name, detail.new_name)
  pendingToolNames.add(detail.old_name)
  pendingToolNames.add(detail.new_name)
  requestToolReconciliation()
}

async function maybeApplyRemoteDraftToActiveCanvas(): Promise<void> {
  const remoteRevision = workflowDraftStore.remoteAvailableRevision
  if (remoteRevision === null) return
  if (!hasLoadedGraphState.value) return
  if (isNestedWorkflowEditor) return
  if (!isActiveCanvasTab.value) return
  if (lifecycleOperation.value !== null) return
  if (hasLocalRemoteDraftConflict.value) return
  if (isResolvingRemoteDraftConflict.value) return
  if (isInstallingAuthoritativeDraft.value) return
  if (isAutoApplyingRemoteDraft) return

  const workflowName = workflowIdentity().workflowName
  if (typeof workflowName !== 'string' || workflowName.length === 0) return
  if (workflowDraftStore.workflowId !== workflowName) return

  const editEpoch = rootEditEpoch
  isAutoApplyingRemoteDraft = true
  try {
    const draft = await workflowDraftStore.fetchLatestDraft(workflowName)
    const currentRemoteRevision = workflowDraftStore.remoteAvailableRevision
    if (
      isCanvasUnmounted
      || rootEditEpoch !== editEpoch
      || !isActiveCanvasTab.value
      || lifecycleOperation.value !== null
      || hasLocalRemoteDraftConflict.value
      || isResolvingRemoteDraftConflict.value
      || isInstallingAuthoritativeDraft.value
      || currentWorkflowName() !== workflowName
      || workflowDraftStore.workflowId !== workflowName
      || currentRemoteRevision === null
      || draft.draft_revision < currentRemoteRevision
      || draft.draft_revision < remoteRevision
    ) return
    await installAuthoritativeRootDraft(draft)
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
    lifecycleOperation.value,
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
  pendingToolNames.add(detail.tool_name)
  requestToolReconciliation()
}

watch(
  () => toolRegistryStore.tools,
  (tools) => {
    const next = registrySignatures(tools)
    for (const [name, signature] of next) {
      if (previousToolRegistry.get(name) !== signature) pendingToolNames.add(name)
    }
    for (const name of previousToolRegistry.keys()) {
      if (!next.has(name)) pendingToolNames.add(name)
    }
    previousToolRegistry = next
    if (pendingToolNames.size > 0) requestToolReconciliation()
  },
  { deep: true },
)

watch(
  () => executionStore.isMutationLocked,
  (locked) => {
    if (!locked) requestToolReconciliation()
  },
  { flush: 'sync' },
)

watch(
  lifecycleOperation,
  (operation) => {
    if (operation === null) requestToolReconciliation()
  },
  { flush: 'sync' },
)

watch(
  () => toolRegistryStore.customToolBusy,
  (busy) => {
    if (!busy) {
      // renameTool/deleteTool refresh the registry before their caller emits
      // the operation event. Give that continuation one task to add its
      // rename/delete detail before interpreting a removed registry name.
      setTimeout(requestToolReconciliation, 0)
    }
  },
)

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
    canOpenNestedWorkflow: node.data?.workflow != null,
    hasWorkspaceSource: !isNestedWorkflowEditor
      && node.data?.source?.kind === 'workspace',
    sourceWorkflowId: node.data?.source?.kind === 'workspace'
      ? node.data.source.workflow_id
      : null,
  }
}

async function openContextSourceWorkflow() {
  const sourceWorkflowId = nodeContextMenu.value?.sourceWorkflowId
  closeNodeContextMenu()
  if (!sourceWorkflowId) return
  try {
    const presentation = await loadRootWorkflowPresentation(sourceWorkflowId)
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
      detail: {
        graph: presentation.graph,
        workflowName: presentation.workflowName,
        workflowDisplayName: presentation.workflowDisplayName,
        missingTools: presentation.missingTools,
        dirty: presentation.dirty,
        draft: presentation.draft,
        identityGeneration: presentation.identityGeneration,
        serverIdentityGeneration: presentation.serverIdentityGeneration,
      },
    }))
  } catch (error: unknown) {
    clipboardToast?.add({
      severity: 'error',
      summary: 'Open source workflow failed',
      detail: error instanceof Error ? error.message : String(error),
      life: 5000,
    })
  }
}

function describeSourceEffects(preview: WorkflowSourcePreview): string {
  const effects = preview.destructive_effects ?? []
  const sourceChanges = (preview.custom_source_ids_added?.length ?? 0)
    + (preview.custom_source_ids_removed?.length ?? 0)
  if (effects.length === 0 && sourceChanges === 0) {
    return 'Replace this embedded workflow with the current saved source?'
  }
  return `Replace this embedded workflow? This will apply ${effects.length} interface change(s) and ${sourceChanges} workflow-local tool source change(s).`
}

async function updateContextWorkflowFromSource() {
  const menu = nodeContextMenu.value
  closeNodeContextMenu()
  const workflowId = owningWorkflowId()
  if (!menu?.hasWorkspaceSource || !workflowId || isNestedWorkflowEditor) return
  if (uiStore.canvasHasUnsavedChanges(canvasId)) {
    clipboardToast?.add({
      severity: 'warn',
      summary: 'Save the workflow first',
      detail: 'Source updates require a clean saved parent workflow.',
      life: 5000,
    })
    return
  }
  try {
    const fresh = await canvasPersistence.ensureFreshForCriticalOperation()
    if (!fresh) return
    const { data: parent } = await api.get<{ artifact_hash: string }>(
      `/api/v1/workflows/${workflowUrl(workflowId)}`,
    )
    const preview = await previewWorkflowSourceUpdate(workflowId, {
      workflow_path: [menu.nodeId],
      expected_artifact_hash: parent.artifact_hash,
    })
    if (!window.confirm(describeSourceEffects(preview))) return
    const result = await applyWorkflowSourceOperation(workflowId, {
      token: preview.token,
      confirm_effects: preview.destructive_effects ?? [],
    })
    const revision = canvasPersistence.acceptedDraftRevision.value
    if (revision === null) throw new Error('The parent workflow draft is unavailable')
    const accepted = await resetWorkflowDraftToSaved(workflowId, revision)
    initializeCanvasPersistenceFromDraft(accepted)
    await applyGraphState(accepted.graph, [], false, false)
    clipboardToast?.add({
      severity: 'success',
      summary: 'Workflow updated from source',
      detail: `Saved artifact ${result.artifact_hash}`,
      life: 4000,
    })
  } catch (error: unknown) {
    clipboardToast?.add({
      severity: 'error',
      summary: 'Update from source failed',
      detail: error instanceof Error ? error.message : String(error),
      life: 6000,
    })
  }
}

function detachContextWorkflowSource() {
  const menu = nodeContextMenu.value
  closeNodeContextMenu()
  if (!menu?.hasWorkspaceSource || isLocked.value) return
  const node = getNodes.value.find((candidate: any) => candidate.id === menu.nodeId)
  if (!node?.data || node.data.source?.kind !== 'workspace') return
  node.data.source = null
  emitGraphChanged()
}

function onNodeDoubleClick(payload: any) {
  const node = payload.node
  if (!node?.data?.workflow) return
  openNestedWorkflow(node.id)
}

function runContextNestedWorkflowAction() {
  const menu = nodeContextMenu.value
  if (!menu) return
  if (menu.canOpenNestedWorkflow) {
    openNestedWorkflow(menu.nodeId)
  } else {
    createSelectedNestedWorkflow()
  }
  closeNodeContextMenu()
}

function renameContextNode() {
  const menu = nodeContextMenu.value
  if (!menu) return
  const node = getNodes.value.find((candidate: any) => candidate.id === menu.nodeId)
  closeNodeContextMenu()
  if (!node?.data || isLocked.value) return
  const currentName = typeof node.data.name === 'string' ? node.data.name : ''
  const nextName = window.prompt('Rename node', currentName)
  if (nextName !== null) renameNode(menu.nodeId, nextName)
}

function toggleContextNodeEnabled() {
  const menu = nodeContextMenu.value
  if (!menu) return
  const node = getNodes.value.find((n: any) => n.id === menu.nodeId)
  if (node?.data) {
    setNodeEnabled(menu.nodeId, node.data.enabled === false)
  }
  closeNodeContextMenu()
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

// Toast injection is optional in isolated component tests. Hot reload and
// clipboard operations remain functional without a mounted ToastService.
try {
  hotReloadToast = useToast()
} catch {
  /* no ToastService */
}
clipboardToast = hotReloadToast
if (clipboardToast === null) {
  try {
    clipboardToast = useToast()
  } catch {
    /* no ToastService — clipboard operations still work without toasts */
  }
}

async function loadNestedWorkflowSessionDraft() {
  const sessionId = props.nestedWorkflowSessionId
  if (!sessionId) return
  const session = nestedWorkflowSessionsStore.sessionById(sessionId)
  if (!session) return
  await applyGraphState(session.draft)
  if (isCanvasUnmounted) return
  hasLoadedGraphState.value = true
}

async function handleReplaceRootGraphEvent(event: CustomEvent<{
  workflowId?: string
  draft?: WorkflowDraftResponse
}>) {
  if (isNestedWorkflowEditor) return
  const detail = event.detail
  if (!detail?.draft || detail.workflowId !== owningWorkflowId()) return
  initializeCanvasPersistenceFromDraft(detail.draft)
  await applyGraphState(detail.draft.graph, [], false, false)
}

onMounted(async () => {
  window.addEventListener(
    'bioimageflow:apply-nested-workflow-session',
    handleApplyNestedWorkflowSessionEvent as EventListener,
  )
  window.addEventListener('bioimageflow:tool-renamed', handleToolRenamedEvent)
  window.addEventListener('bioimageflow:tool-deleted', handleToolDeletedEvent)
  window.addEventListener('bioimageflow:edit-command', handleEditCommandEvent as EventListener)
  window.addEventListener(
    'bioimageflow:canvas-tab-activated',
    handleCanvasTabActivatedEvent as EventListener,
  )
  window.addEventListener(
    'bioimageflow:restore-saved-canvas',
    handleRestoreSavedCanvasEvent as EventListener,
  )
  window.addEventListener(
    'bioimageflow:replace-root-graph',
    handleReplaceRootGraphEvent as unknown as EventListener,
  )
  if (toolRegistryStore.tools.length === 0) {
    await toolRegistryStore.fetchTools()
  }
  if (isCanvasUnmounted) return
  if (isNestedWorkflowEditor) {
    await loadNestedWorkflowSessionDraft()
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
  throw new Error(`Canvas '${canvasPanelId}' was mounted without an initial graph`)
})

onBeforeUnmount(() => {
  isCanvasUnmounted = true
  for (const node of getNodes.value) fieldFocusTracker.clearTracking(canvasId, node.id)
  registeredFocusDeferrals.clear()
  removedFocusedFields.clear()
  dataTableStore.releaseCanvas(canvasId)
  resolvedOutputsStore.releaseCanvas(canvasId)
  canvasStatusProjection.dispose()
  disposeGraphSync()
  disposeCanvasPersistence()
  canvasCommands.dispose()
  uiStore.releaseCanvasPresentation(canvasId)
  window.removeEventListener(
    'bioimageflow:apply-nested-workflow-session',
    handleApplyNestedWorkflowSessionEvent as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:replace-root-graph',
    handleReplaceRootGraphEvent as unknown as EventListener,
  )
  window.removeEventListener('bioimageflow:tool-renamed', handleToolRenamedEvent)
  window.removeEventListener('bioimageflow:tool-deleted', handleToolDeletedEvent)
  window.removeEventListener('bioimageflow:edit-command', handleEditCommandEvent as EventListener)
  window.removeEventListener(
    'bioimageflow:canvas-tab-activated',
    handleCanvasTabActivatedEvent as EventListener,
  )
  window.removeEventListener(
    'bioimageflow:restore-saved-canvas',
    handleRestoreSavedCanvasEvent as EventListener,
  )
})

// --- Node drag tracking (undo support) ---

onNodeDragStart(({ nodes }) => {
  if (isLocked.value) {
    dragStartPositions.value = {}
    return
  }
  const positions: Record<string, { x: number; y: number }> = {}
  for (const node of nodes) {
    positions[node.id] = { x: node.position.x, y: node.position.y }
  }
  dragStartPositions.value = positions
})

onNodeDragStop(({ nodes }) => {
  const start = dragStartPositions.value
  if (isLocked.value) {
    for (const node of nodes) {
      const position = start[node.id]
      if (position) node.position = { ...position }
    }
    dragStartPositions.value = {}
    return
  }
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
  if (decodeEndpointHandle(targetHandle).kind === 'dataframe-position') {
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
    type: edgeIsHeader ? 'dataframe' : 'column',
  }
  addEdges([newEdge])

  // Update connectedInputs on target node
  const targetNode = getNodes.value.find((n: any) => n.id === connection.target)
  if (targetNode) {
    const sourceNode = getNodes.value.find((n: any) => n.id === connection.source)
    const sourceLabel = canvasConnectionSourceLabel(
      sourceNode ?? { id: connection.source },
      connection.sourceHandle,
    )
    targetNode.data.connectedInputs = {
      ...targetNode.data.connectedInputs,
      [targetHandle]: sourceLabel,
    }
    pinConnectedBodyInput(targetNode, targetHandle, connection.sourceHandle)
    // Drop any constant the user (or default-seeding) had stashed for this
    // input. The wire schema says `parameters` carries non-connected fields
    // only, and a stray value here (notably ``null``) would otherwise ride
    // along into the lib payload and override the upstream binding.
    const targetEndpoint = decodeEndpointHandle(targetHandle)
    const targetParameter = targetEndpoint.kind === 'tool-input' ? targetEndpoint.name : null
    if (!edgeIsHeader && targetParameter && targetNode.data.parameters
        && targetParameter in targetNode.data.parameters) {
      const next = { ...targetNode.data.parameters }
      delete next[targetParameter]
      targetNode.data.parameters = next
    }
  }

  // A new positional edge into a dynamic_outputs node changes its resolved
  // schema (e.g. CrossJoin's column union depends on the upstream tables).
  if (decodeEndpointHandle(targetHandle).kind === 'dataframe-position') {
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
  if (isLocked.value) return
  const edge = getEdges.value.find((e: any) => e.id === edgeId)
  if (!edge) return
  const targetHandle = edge.targetHandle ?? ''
  const target = edge.target
  cleanupDisconnectedInput(target, targetHandle)
  removeEdges([edgeId])
  if (decodeEndpointHandle(targetHandle).kind === 'dataframe-position') {
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
  if (isLocked.value) {
    updatedEdgeIds.delete(edge.id)
    return
  }
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
    const sourceLabel = canvasConnectionSourceLabel(
      sourceNode ?? { id: newSource },
      newSourceHandle,
    )
    targetNode.data.connectedInputs = {
      ...targetNode.data.connectedInputs,
      [newTargetHandle]: sourceLabel,
    }
    pinConnectedBodyInput(targetNode, newTargetHandle, newSourceHandle)
    // Mirror the onConnect cleanup: drop any constant for this input so
    // the wire payload carries non-connected fields only.
    const newEdgeIsHeader = isHeaderHandle(newTargetHandle) || isHeaderHandle(newSourceHandle)
    const newEndpoint = decodeEndpointHandle(newTargetHandle)
    const newParameter = newEndpoint.kind === 'tool-input' ? newEndpoint.name : null
    if (!newEdgeIsHeader && newParameter && targetNode.data.parameters
        && newParameter in targetNode.data.parameters) {
      const next = { ...targetNode.data.parameters }
      delete next[newParameter]
      targetNode.data.parameters = next
    }
  }

  // Refresh schemas on either side of a positional re-route — both the old
  // and the new targets may have dynamic_outputs schemas to recompute.
  if (decodeEndpointHandle(edge.targetHandle ?? '').kind === 'dataframe-position') {
    refreshIfDynamicOutputs(edge.target)
  }
  if (decodeEndpointHandle(newTargetHandle).kind === 'dataframe-position') {
    refreshIfDynamicOutputs(newTarget)
  }

  emitGraphChanged()
})

// Edge disconnect: dragging a connected handle to empty space (no onEdgeUpdate
// fired for this gesture).
onEdgeUpdateEnd(({ edge }) => {
  if (!edge) return
  if (isLocked.value) {
    updatedEdgeIds.delete(edge.id)
    return
  }
  if (updatedEdgeIds.delete(edge.id)) return
  const targetHandle = edge.targetHandle ?? ''
  const target = edge.target
  removeEdges([edge.id])
  cleanupDisconnectedInput(target, targetHandle)
  if (decodeEndpointHandle(targetHandle).kind === 'dataframe-position') {
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

  if (decodeEndpointHandle(targetHandle).kind === 'dataframe-position') {
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
    .filter(([handle]) => decodeEndpointHandle(handle).kind === 'dataframe-position')
    .sort(([a], [b]) => {
      const left = decodeEndpointHandle(a)
      const right = decodeEndpointHandle(b)
      const ai = left.kind === 'dataframe-position' ? left.index : 0
      const bi = right.kind === 'dataframe-position' ? right.index : 0
      return ai - bi
    })

  // Remove all old positional keys
  for (const key of Object.keys(ci)) {
    if (decodeEndpointHandle(key).kind === 'dataframe-position') {
      delete ci[key]
    }
  }

  // Re-insert with compact indices and update edges
  positionalEntries.forEach(([oldKey, label], newIndex) => {
    const newKey = encodeEndpointHandle({ kind: 'dataframe-position', index: newIndex })
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
function isHeaderHandle(handle: string | null | undefined, node?: any): boolean {
  if (!handle) return false
  const endpoint = decodeEndpointHandle(handle)
  if (endpoint.kind === 'dataframe-output'
    || endpoint.kind === 'dataframe-position'
    || endpoint.kind === 'dataframe-input') return true
  if (endpoint.kind === 'workflow-input' && node?.type === 'workflow') {
    return node.data?.workflow?.interface.inputs.some(
      (input: WorkflowInput) => input.id === endpoint.id && input.kind === 'dataframe',
    ) ?? false
  }
  return false
}

function pinConnectedBodyInput(
  targetNode: any,
  targetHandle: string,
  sourceHandle: string | null | undefined,
): void {
  if (!targetHandle || isHeaderHandle(targetHandle) || isHeaderHandle(sourceHandle)) return
  const tool = toolForNode(targetNode)
  const endpoint = decodeEndpointHandle(targetHandle)
  if (endpoint.kind !== 'tool-input') return
  const field = tool?.inputs?.[endpoint.name]
  if (!field || field.connectable === 'never') return
  targetNode.data.pinnedInputs = {
    ...(targetNode.data.pinnedInputs ?? {}),
    [endpoint.name]: true,
  }
}

function toolForNode(node: any): ToolMetadata | undefined {
  return (node?.data?.tool as ToolMetadata | undefined)
    ?? toolRegistryStore.getToolByName(node?.data?.toolName)
}

function isNestedWorkflowNode(node: any): boolean {
  return node?.type === 'workflow' && node?.data?.nodeType === 'workflow'
}

function exposedSchemaType(schema: unknown): string | undefined {
  if (!schema || typeof schema !== 'object') return undefined
  const type = (schema as { type?: unknown }).type
  return typeof type === 'string' ? type : undefined
}

function outputTypeForHandle(node: any, handle: string): string | undefined {
  const endpoint = decodeEndpointHandle(handle)
  const outputIdentity = endpoint.kind === 'tool-output'
    ? endpoint.name
    : endpoint.kind === 'workflow-output' ? endpoint.id : null
  if (outputIdentity === null) return endpoint.kind === 'dataframe-output' ? 'DataFrame' : undefined
  const tool = toolForNode(node)
  const sourceOutput = tool?.outputs?.[outputIdentity] as { type?: string } | undefined
  let sourceType = sourceOutput?.type
  if (!sourceType && tool?.dynamic_outputs) {
    const resolved = canvasResolvedOutputs[node.id]
    if (resolved?.resolved && resolved.columns) {
      const col = (resolved.columns as Record<string, any>)[outputIdentity]
      sourceType = col?.type
    }
  }
  if (sourceType) return sourceType
  if (!isNestedWorkflowNode(node)) return undefined
  const exposed = node.data.workflow.interface.outputs.find(
    (item: WorkflowOutput) => item.id === outputIdentity,
  )
  return exposedSchemaType(exposed?.schema)
}

function inputTypeForHandle(node: any, handle: string): string | undefined {
  const endpoint = decodeEndpointHandle(handle)
  if (endpoint.kind === 'dataframe-position' || endpoint.kind === 'dataframe-input') {
    return 'DataFrame'
  }
  const tool = toolForNode(node)
  const targetInput = endpoint.kind === 'tool-input' ? tool?.inputs?.[endpoint.name] : undefined
  if (targetInput?.type) return targetInput.type
  if (!isNestedWorkflowNode(node)) return undefined
  const exposed = node.data.workflow.interface.inputs.find(
    (item: WorkflowInput) => endpoint.kind === 'workflow-input' && item.id === endpoint.id,
  )
  return exposedSchemaType(exposed?.schema)
}

function isValidConnection(connection: {
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
}): boolean {
  // 0. Cross-region rejection: header handles must connect to header,
  //    body handles must connect to body.
  const sourceNode = getNodes.value.find(node => node.id === connection.source)
  const targetNode = getNodes.value.find(node => node.id === connection.target)
  const sourceIsHeader = isHeaderHandle(connection.sourceHandle, sourceNode)
  const targetIsHeader = isHeaderHandle(connection.targetHandle, targetNode)
  if (sourceIsHeader !== targetIsHeader) {
    return false
  }

  // 1. Type compatibility check
  if (!sourceNode || !targetNode) return false

  // Prefer the tool metadata carried on the node itself — the registry may
  // not be populated yet during restore-on-mount (fetch is async), and a
  // missing tool here would silently fail every edge with EDGE_INVALID.
  const sourceTool = toolForNode(sourceNode)
  const targetTool = toolForNode(targetNode)
  if (
    (!sourceTool && !isNestedWorkflowNode(sourceNode))
    || (!targetTool && !isNestedWorkflowNode(targetNode))
  ) {
    return false
  }

  // 1b. Reject positional edges into source DataFrameTools
  const th = connection.targetHandle ?? ''
  if (decodeEndpointHandle(th).kind === 'dataframe-position'
    && targetTool?.accepts_upstream === false) {
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

function canvasCenterPosition(): { x: number; y: number } | undefined {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return undefined
  return project({ x: rect.width / 2, y: rect.height / 2 })
}

function onAddNode({
  toolName,
  position,
  parameters: parameterOverrides,
}: {
  toolName: string
  position?: { x: number; y: number }
  parameters?: Record<string, unknown>
}): string | null {
  if (isLocked.value) return null
  const tool = toolRegistryStore.getToolByName(toolName)
  if (!tool) return null

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
  Object.assign(parameters, parameterOverrides)

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

  attachInterfaceContext(newNode)
  addNodes([newNode])
  emitGraphChanged()
  return id
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
    const id = generateNodeId('workflow', existingIds)
    const name = generateNodeName(
      info.display_name ?? workflowName,
      existingNames,
      info.display_name ?? workflowName,
    )
    const newNode = {
      id,
      type: 'workflow',
      position: position ?? { x: 0, y: 0 },
      data: {
        nodeType: 'workflow',
        name,
        status: 'unexecuted',
        resources: {},
        collapsed: false,
        enabled: true,
        connectedInputs: {},
        pinnedInputs: Object.fromEntries(
          graph.interface.inputs.map(input => [input.id, true]),
        ),
        workflow: graph,
        bindings: {},
        source: {
          kind: 'workspace',
          workflow_id: workflowName,
          artifact_hash: data.artifact_hash,
        },
      },
    }
    attachInterfaceContext(newNode)
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
      if (decodeEndpointHandle(edge.targetHandle ?? '').kind === 'dataframe-position') {
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
      if (decodeEndpointHandle(edge.targetHandle ?? '').kind === 'dataframe-position') {
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
    { sourceWorkflowId: owningWorkflowId() ?? undefined },
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
  const previous = lastAuthoritativeGraph.value
  const graph = graphStateToVueFlow({
    schema_version: previous?.schema_version ?? 1,
    name: previous?.name ?? 'clipboard',
    display_name: previous?.display_name ?? 'Clipboard',
    nodes: [n],
    edges: [],
    interface: { inputs: [], outputs: [] },
    config: previous?.config ?? {
      storage_path: './bif_data',
      engine: 'wetlands',
      execution: 'parallel',
    },
  }, toolRegistryStore.getToolByName)
  return graph.nodes[0]
}

function vueFlowEdgeFromGraphEdge(
  e: GraphState['edges'][number],
  graphNodes: Array<{ id: string; type?: string }> = getNodes.value,
) {
  if (e.type === 'dataframe') {
    return {
      id: e.id,
      source: e.source_node,
      target: e.target_node,
      sourceHandle: encodeEndpointHandle({ kind: 'dataframe-output' }),
      targetHandle: e.target_position == null
        ? encodeEndpointHandle({ kind: 'workflow-input', id: e.target_input! })
        : encodeEndpointHandle({ kind: 'dataframe-position', index: e.target_position }),
      type: 'dataframe',
    }
  }
  const sourceNode = graphNodes.find(node => node.id === e.source_node)
  const targetNode = graphNodes.find(node => node.id === e.target_node)
  return {
    id: e.id,
    source: e.source_node,
    target: e.target_node,
    sourceHandle: encodeEndpointHandle(sourceNode?.type === 'workflow'
      ? { kind: 'workflow-output', id: e.source_output }
      : { kind: 'tool-output', name: e.source_output }),
    targetHandle: encodeEndpointHandle(targetNode?.type === 'workflow'
      ? { kind: 'workflow-input', id: e.target_input }
      : { kind: 'tool-input', name: e.target_input }),
    type: 'column',
  }
}

function currentVueFlowState(): CanvasVueFlowState {
  const workflowInterface = currentInterfaceContext()
  return {
    nodes: getNodes.value.map((n: any) => ({ ...n })),
    edges: getEdges.value.map((e: any) => ({ ...e })),
    interface: {
      inputs: workflowInterface?.inputs ?? rootWorkflowInputs.value,
      outputs: workflowInterface?.outputs ?? rootWorkflowOutputs.value,
    },
  }
}

function canvasHistoryState(
  state: CanvasVueFlowState = currentVueFlowState(),
  authoritativeGraph?: GraphState,
): CanvasHistoryState {
  const context = currentInterfaceContext()
  return {
    nodes: state.nodes,
    edges: authoritativeGraph
      ? authoritativeGraph.edges.map(edge => vueFlowEdgeFromGraphEdge(edge))
      : state.edges,
    interface: {
      inputs: context?.inputs ?? state.interface?.inputs ?? [],
      outputs: context?.outputs ?? state.interface?.outputs ?? [],
    },
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
      [targetHandle]: canvasConnectionSourceLabel(
        byId.get(edge.source) ?? { id: edge.source },
        sourceHandle,
      ),
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

  const newNodes = attachInterfaceContextToNodes(
    prepared.nodes.map(vueFlowNodeFromClipboardNode),
  )
  const newEdges = prepared.edges.map(edge => vueFlowEdgeFromGraphEdge(edge, prepared.nodes))
  populateConnectedInputsForPastedNodes(newNodes, newEdges)

  addNodes(newNodes)
  addEdges(newEdges)
  showPasteSummary(prepared.summary)
  emitGraphChanged()
}

function createSelectedNestedWorkflow() {
  if (isLocked.value) return
  const selectedIds = new Set(
    getNodes.value.filter((n: any) => n.selected).map((n: any) => n.id),
  )
  if (selectedIds.size === 0) return

  const id = generateNodeId('workflow', getNodes.value.map((n: any) => n.id))
  const name = generateNodeName(
    'NestedWorkflow',
    getNodes.value.map((n: any) => n.data?.name ?? ''),
    'Workflow',
  )
  const result = groupIntoWorkflow({
    nodes: getNodes.value,
    edges: getEdges.value,
    selectedNodeIds: selectedIds,
    workflowNodeId: id,
    workflowNodeName: name,
  })
  attachInterfaceContextToNodes(result.nodes as any[])
  setNodes(result.nodes as any)
  setEdges(result.edges)
  refreshConnectedInputLabels()
  uiStore.setCanvasSelectedNodes(canvasId, [id])
  emitGraphChanged()
}

async function openNestedWorkflow(nodeId: string) {
  if (isLocked.value) return null
  const node = getNodes.value.find((n: any) => n.id === nodeId)
  if (!node?.data?.workflow) return null
  try {
    const owner = props.nestedWorkflowSessionId
      ? { kind: 'nested' as const, session_id: props.nestedWorkflowSessionId }
      : {
          kind: 'root' as const,
          canvas_id: canvasId,
          workflow_id: owningWorkflowId(),
        }
    const { session, created } = await nestedWorkflowSessionsStore.openDurableSessionResult({
      owner,
      parentCanvasId: canvasId,
      parentWorkflowName: owningWorkflowId(),
      parentSourceWorkflowName: node.data.source?.kind === 'workspace'
        ? node.data.source.workflow_id
        : null,
      parentNodeId: node.id,
      parentNodeName: node.data.name ?? node.id,
      graph: node.data.workflow,
    })
    if (
      isCanvasUnmounted
      || isLocked.value
      || getNodes.value.find(candidate => candidate.id === nodeId) !== node
    ) {
      if (created) nestedWorkflowSessionsStore.closeSession(session.id)
      return null
    }
    window.dispatchEvent(new CustomEvent('bioimageflow:nested-workflow-session-opened', {
      detail: {
        sessionId: session.id,
        parentNodeId: node.id,
        parentCanvasPanelId: canvasPanelId,
      },
    }))
    return session
  } catch (error) {
    reportError({
      kind: 'graph_sync_error',
      detail: error instanceof Error
        ? error.message
        : 'Failed to open nested-workflow snapshot',
    })
    return null
  }
}

function reconcileWorkflowParentState(
  parentNodeId: string,
  previousInputs: WorkflowInput[],
  previousOutputs: WorkflowOutput[],
  nextInputs: WorkflowInput[],
  nextOutputs: WorkflowOutput[],
) {
  const removedInputs = new Set(
    previousInputs.filter(input => !nextInputs.some(next => next.id === input.id))
      .map(input => input.id),
  )
  const removedOutputs = new Set(
    previousOutputs.filter(output => !nextOutputs.some(next => next.id === output.id))
      .map(output => output.id),
  )
  const nextEdges = getEdges.value.filter((edge) => {
    if (edge.target === parentNodeId && edge.targetHandle) {
      const target = decodeEndpointHandle(edge.targetHandle)
      if (target.kind === 'workflow-input' && removedInputs.has(target.id)) return false
    }
    if (edge.source === parentNodeId && edge.sourceHandle) {
      const source = decodeEndpointHandle(edge.sourceHandle)
      if (source.kind === 'workflow-output' && removedOutputs.has(source.id)) return false
    }
    return true
  })
  setEdges(nextEdges)

  const parentNode = getNodes.value.find((n: any) => n.id === parentNodeId)
  if (!parentNode?.data) return

  parentNode.data.bindings = Object.fromEntries(
    Object.entries(parentNode.data.bindings ?? {})
      .filter(([id]) => !removedInputs.has(id)),
  )
  parentNode.data.pinnedInputs = Object.fromEntries(
    nextInputs.map(input => [input.id, parentNode.data.pinnedInputs?.[input.id] !== false]),
  )

  const connectedInputs: Record<string, string> = {}
  for (const edge of nextEdges) {
    if (edge.target !== parentNodeId || !edge.targetHandle) continue
    const sourceNode = getNodes.value.find((node: any) => node.id === edge.source)
    connectedInputs[edge.targetHandle] = canvasConnectionSourceLabel(
      sourceNode ?? { id: edge.source },
      edge.sourceHandle,
    )
  }
  parentNode.data.connectedInputs = connectedInputs
}

function applyNestedWorkflowDraft(
  parentNodeId: string,
  graph: GraphState,
): boolean {
  if (isLocked.value) return false
  const node = getNodes.value.find((n: any) => n.id === parentNodeId)
  if (!node?.data) return false
  const parentWasExecuted = canvasStatusProjection.statusForNode(parentNodeId)?.status
    === 'executed'
  const previousInputs = deepClone(node.data.workflow.interface.inputs) as WorkflowInput[]
  const previousOutputs = deepClone(node.data.workflow.interface.outputs) as WorkflowOutput[]
  const nextInputs = deepClone(graph.interface.inputs)
  const nextOutputs = deepClone(graph.interface.outputs)
  reconcileWorkflowParentState(
    parentNodeId,
    previousInputs,
    previousOutputs,
    nextInputs,
    nextOutputs,
  )
  node.data.workflow = deepClone(graph)
  canvasStatusProjection.stageCurrentSemanticStatuses()
  if (parentWasExecuted) {
    canvasStatusProjection.stageSemanticStatus(parentNodeId, {
      node_id: parentNodeId,
      status: 'out_of_date',
      cached: false,
    })
  }
  dataTableStore.clearCanvasCache(canvasId, parentNodeId)
  emitGraphChanged({ statusesAlreadyStaged: true })
  return true
}

async function saveNestedWorkflowSession(): Promise<void> {
  if (isLocked.value) return
  const sessionId = props.nestedWorkflowSessionId
  if (!sessionId) return
  const session = nestedWorkflowSessionsStore.sessionById(sessionId)
  if (!session) return
  try {
    const accepted = await flushNow()
    if (!accepted) return
    if (
      isCanvasUnmounted
      || nestedWorkflowSessionsStore.sessionById(sessionId) !== session
    ) return
    const outcome: { result: NestedWorkflowParentApplyResult } = {
      result: {
        status: 'conflict',
        reason: 'parent_missing',
      },
    }
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-nested-workflow-session', {
      detail: {
        sessionId,
        parentCanvasId: session.parentCanvasId,
        parentNodeId: session.parentNodeId,
        graph: accepted.graph,
        complete: (nextResult: NestedWorkflowParentApplyResult) => {
          outcome.result = nextResult
        },
      },
    }))
    const result = outcome.result
    if (result.status !== 'applied') {
      if (result.status === 'conflict') {
        nestedWorkflowSessionsStore.markParentApplyConflict(sessionId, result.reason)
        uiStore.markCanvasDirty(canvasId)
      }
      reportError({
        kind: 'graph_sync_error',
        detail: nestedWorkflowParentApplyError(result),
        alwaysToast: true,
      })
      return
    }
    nestedWorkflowSessionsStore.markSaved(
      sessionId,
      accepted.graph,
      accepted.snapshotRevision,
      accepted.validation,
    )
    uiStore.markCanvasClean(canvasId)
  } catch (error) {
    reportError({
      kind: 'graph_sync_error',
      detail: error instanceof Error
        ? error.message
        : 'Failed to save nested-workflow snapshot',
    })
  }
}

function nestedWorkflowParentApplyError(result: Exclude<
  NestedWorkflowParentApplyResult,
  { status: 'applied' }
>): string {
  if (result.status === 'rejected') {
    return 'Cannot save nested-workflow while execution is active.'
  }
  if (result.reason === 'parent_changed') {
    return 'Cannot save nested-workflow because its parent node changed after this editor was opened.'
  }
  return 'Cannot save nested-workflow because its parent is no longer available.'
}

function currentNestedWorkflowDocument(node: any): GraphState | null {
  const graph = node?.data?.workflow
  if (
    !graph
    || typeof graph !== 'object'
    || !Array.isArray(graph.nodes)
    || !Array.isArray(graph.edges)
  ) return null
  return deepClone(graph)
}

function handleApplyNestedWorkflowSessionEvent(event: CustomEvent<{
  sessionId?: string
  parentCanvasId?: string
  parentNodeId?: string
  complete?: (result: NestedWorkflowParentApplyResult) => void
} & Partial<NestedWorkflowApplyPayload>>) {
  const detail = event.detail
  if (
    !detail?.sessionId
    || detail.parentCanvasId !== canvasId
    || !detail.parentNodeId
    || !detail.graph
  ) return
  const session = nestedWorkflowSessionsStore.sessionById(detail.sessionId)
  if (
    !session
    || session.parentCanvasId !== canvasId
    || session.parentNodeId !== detail.parentNodeId
  ) return
  const parentNode = getNodes.value.find((node: any) => node.id === detail.parentNodeId)
  if (!parentNode?.data) {
    detail.complete?.({ status: 'conflict', reason: 'parent_missing' })
    return
  }
  const currentDocument = currentNestedWorkflowDocument(parentNode)
  if (
    currentDocument === null
    || !graphDocumentsEqual(currentDocument, session.savedSnapshot)
  ) {
    detail.complete?.({ status: 'conflict', reason: 'parent_changed' })
    return
  }
  const applied = applyNestedWorkflowDraft(detail.parentNodeId, detail.graph)
  detail.complete?.(applied
    ? { status: 'applied' }
    : { status: 'rejected', reason: 'locked' })
}

function selectAll() {
  for (const node of getNodes.value) {
    node.selected = true
  }
}

function historyNodesWithCurrentToolRuntime(nodes: any[]): any[] {
  const currentById = new Map(getNodes.value.map((node: any) => [node.id, node]))
  return nodes.map((node) => {
    const toolName = node.data?.toolName
    if (node.type !== 'tool' || typeof toolName !== 'string') return node

    const tool = toolRegistryStore.getToolByName(toolName) ?? null
    const current = currentById.get(node.id)
    const data = {
      ...node.data,
      tool,
      missingTool: tool === null ? missingToolFor(node.id, toolName) : null,
    }
    if (tool === null) {
      data.updatedBadge = false
    } else if (current?.data?.toolName === toolName) {
      if (current.data.updatedBadge === undefined) {
        delete data.updatedBadge
      } else {
        data.updatedBadge = current.data.updatedBadge
      }
    } else {
      delete data.updatedBadge
    }
    return { ...node, data }
  })
}

function applyHistoryState(state: CanvasHistoryState) {
  isApplyingGraphState = true
  try {
    setNodes(historyNodesWithCurrentToolRuntime(state.nodes))
    setEdges(state.edges)
    refreshConnectedInputLabels()
    if (!replaceWorkflowInterface(state.interface.inputs, state.interface.outputs)) return
    const currentState = currentVueFlowState()
    if (isNestedWorkflowEditor && props.nestedWorkflowSessionId) {
      syncGraph(currentState)
      const graph = rememberAuthoritativeGraph(
        serializeGraph(currentState) as GraphState,
      )
      nestedWorkflowSessionsStore.updateDraft(props.nestedWorkflowSessionId, graph)
      refreshInterfaceContextOnNodes()
      uiStore.markCanvasDirty(canvasId)
    } else {
      markDirtyAndAutoSave(currentState)
    }
  } finally {
    void nextTick().then(() => {
      isApplyingGraphState = false
      requestToolReconciliation()
    })
  }
}

function redoGraphChange() {
  if (isLocked.value) return
  const state = undoRedo.redo()
  if (state) applyHistoryState(state)
}

function undoGraphChange() {
  if (isLocked.value) return
  const state = undoRedo.undo()
  if (state) applyHistoryState(state)
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
    case 'group-into-workflow':
      createSelectedNestedWorkflow()
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
    if (isNestedWorkflowEditor) {
      void saveNestedWorkflowSession()
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

function markDirtyAndAutoSave(
  state: { nodes: any[]; edges: any[] },
  graphOverride?: GraphState,
) {
  const name = owningWorkflowId()
  if (!name) return
  rootEditEpoch += 1
  const graph = graphOverride ?? rememberAuthoritativeGraph(
    serializeGraph(state) as GraphState,
  )
  uiStore.markCanvasDirty(canvasId)
  queueCanvasPersistence(graph)
}

function renameNode(nodeId: string, name: string): boolean {
  if (isLocked.value) return false
  const node = getNodes.value.find((candidate: any) => candidate.id === nodeId)
  if (!node?.data) return false
  const trimmedName = name.trim()
  if (!trimmedName || trimmedName === node.data.name) return false
  if (getNodes.value.some((candidate: any) => (
    candidate.id !== nodeId && candidate.data?.name === trimmedName
  ))) return false
  node.data.name = trimmedName
  for (const edge of getEdges.value) {
    if (edge.source !== nodeId || !edge.targetHandle) continue
    const targetNode = getNodes.value.find((candidate: any) => candidate.id === edge.target)
    if (!targetNode?.data) continue
    targetNode.data.connectedInputs = {
      ...(targetNode.data.connectedInputs ?? {}),
      [edge.targetHandle]: canvasConnectionSourceLabel(node, edge.sourceHandle),
    }
  }
  emitGraphChanged()
  return true
}

function setNodeEnabled(nodeId: string, enabled: boolean): boolean {
  if (isLocked.value) return false
  const node = getNodes.value.find((candidate: any) => candidate.id === nodeId)
  if (!node?.data || node.data.enabled === enabled) return false
  node.data.enabled = enabled
  emitGraphChanged()
  return true
}

function setInputPinned(
  nodeId: string,
  input: string,
  pinned: boolean,
): boolean {
  if (isLocked.value) return false
  const node = getNodes.value.find((candidate: any) => candidate.id === nodeId)
  if (!node?.data) return false
  const nextPinned = input in (node.data.connectedInputs ?? {}) ? true : pinned
  if (node.data.pinnedInputs?.[input] === nextPinned) return false
  node.data.pinnedInputs = {
    ...(node.data.pinnedInputs ?? {}),
    [input]: nextPinned,
  }
  emitGraphChanged()
  return true
}

function setOutputTemplate(
  nodeId: string,
  output: string,
  value: string,
): boolean {
  if (isLocked.value) return false
  const node = getNodes.value.find((candidate: any) => candidate.id === nodeId)
  if (!node?.data || node.data.output_templates?.[output] === value) return false
  node.data.output_templates = {
    ...(node.data.output_templates ?? {}),
    [output]: value,
  }
  emitGraphChanged()
  return true
}

function workflowInterfaceRejected(
  reason: CanvasInterfaceRejectionReason,
  name?: string,
): CanvasInterfaceCommandResult {
  return name === undefined
    ? { status: 'rejected', reason }
    : { status: 'rejected', reason, name }
}

function emitInterfaceChanged(): void {
  const state = currentVueFlowState()
  const graph = graphWithAuthoritativeEdges(state)
  emitGraphChanged({
    state: {
      ...state,
      edges: graph.edges.map(edge => vueFlowEdgeFromGraphEdge(edge)),
    },
  })
}

function workflowInputIndex(
  context: InterfaceContext,
  nodeId: string,
  input: string,
): number {
  return context.inputs.findIndex(item => item.targets.some(target => (
    target.node === nodeId
    && ((target.port.kind === 'field' && target.port.name === input)
      || (target.port.kind === 'workflow' && target.port.id === input))
  )))
}

function workflowOutputIndex(
  context: InterfaceContext,
  nodeId: string,
  output: string,
): number {
  return context.outputs.findIndex(item => (
    item.source.node === nodeId && item.source.column === output
  ))
}

function exposedNameIsUsed(
  context: InterfaceContext,
  name: string,
  except?: { collection: 'input' | 'output'; index: number },
): boolean {
  return context.inputs.some((item, index) => (
    !(except?.collection === 'input' && except.index === index) && item.name === name
  )) || context.outputs.some((item, index) => (
    !(except?.collection === 'output' && except.index === index) && item.name === name
  ))
}

function toggleWorkflowInput(
  nodeId: string,
  input: string,
): CanvasInterfaceCommandResult {
  if (isLocked.value) return workflowInterfaceRejected('locked')
  const node = getNodes.value.find((candidate: any) => candidate.id === nodeId)
  if (!node?.data) return workflowInterfaceRejected('not_found')
  const context = currentInterfaceContext()
  if (!context) return workflowInterfaceRejected('unavailable')
  const existingIndex = workflowInputIndex(context, nodeId, input)
  if (existingIndex >= 0) {
    const nextInputs = context.inputs.filter(
      (_item, index) => index !== existingIndex,
    )
    if (!replaceWorkflowInputs(nextInputs)) return workflowInterfaceRejected('unavailable')
    emitInterfaceChanged()
    return { status: 'changed' }
  }

  const field = toolForNode(node)?.inputs?.[input]
  if (!field) return workflowInterfaceRejected('not_found')
  if (field.connectable === 'never') return workflowInterfaceRejected('not_exposable')
  const name = `${nodeId}.${input}`
  if (exposedNameIsUsed(context, name)) {
    return workflowInterfaceRejected('duplicate_name', name)
  }
  const nextInputs: WorkflowInput[] = [...context.inputs, {
    id: `input-${crypto.randomUUID()}`,
    name,
    kind: 'field',
    schema: deepClone(field),
    default: null,
    targets: [{ node: nodeId, port: { kind: 'field', name: input } }],
  }]
  if (!replaceWorkflowInputs(nextInputs)) return workflowInterfaceRejected('unavailable')
  emitInterfaceChanged()
  return { status: 'changed' }
}

function toggleWorkflowOutput(
  nodeId: string,
  output: string,
): CanvasInterfaceCommandResult {
  if (isLocked.value) return workflowInterfaceRejected('locked')
  const node = getNodes.value.find((candidate: any) => candidate.id === nodeId)
  if (!node?.data) return workflowInterfaceRejected('not_found')
  const context = currentInterfaceContext()
  if (!context) return workflowInterfaceRejected('unavailable')
  const existingIndex = workflowOutputIndex(context, nodeId, output)
  if (existingIndex >= 0) {
    const nextOutputs = context.outputs.filter(
      (_item, index) => index !== existingIndex,
    )
    if (!replaceWorkflowOutputs(nextOutputs)) return workflowInterfaceRejected('unavailable')
    emitInterfaceChanged()
    return { status: 'changed' }
  }

  const field = toolForNode(node)?.outputs?.[output]
  if (!field) return workflowInterfaceRejected('not_found')
  const name = `${nodeId}.${output}`
  if (exposedNameIsUsed(context, name)) {
    return workflowInterfaceRejected('duplicate_name', name)
  }
  const schema: Record<string, unknown> = isRecord(field) ? deepClone(field) : {}
  const nextOutputs: WorkflowOutput[] = [...context.outputs, {
    id: `output-${crypto.randomUUID()}`,
    name,
    schema,
    source: { node: nodeId, column: output },
  }]
  if (!replaceWorkflowOutputs(nextOutputs)) return workflowInterfaceRejected('unavailable')
  emitInterfaceChanged()
  return { status: 'changed' }
}

function renameWorkflowInput(
  nodeId: string,
  input: string,
  name: string,
): CanvasInterfaceCommandResult {
  if (isLocked.value) return workflowInterfaceRejected('locked')
  const context = currentInterfaceContext()
  if (!context) return workflowInterfaceRejected('unavailable')
  const index = workflowInputIndex(context, nodeId, input)
  if (index < 0) return workflowInterfaceRejected('not_found')
  const nextName = name.trim()
  if (!nextName) return workflowInterfaceRejected('empty_name')
  if (context.inputs[index].name === nextName) return { status: 'unchanged' }
  if (exposedNameIsUsed(context, nextName, { collection: 'input', index })) {
    return workflowInterfaceRejected('duplicate_name', nextName)
  }
  const nextInputs = context.inputs.map((item, itemIndex) => (
    itemIndex === index ? { ...item, name: nextName } : item
  ))
  if (!replaceWorkflowInputs(nextInputs)) return workflowInterfaceRejected('unavailable')
  emitInterfaceChanged()
  return { status: 'changed' }
}

function renameWorkflowOutput(
  nodeId: string,
  output: string,
  name: string,
): CanvasInterfaceCommandResult {
  if (isLocked.value) return workflowInterfaceRejected('locked')
  const context = currentInterfaceContext()
  if (!context) return workflowInterfaceRejected('unavailable')
  const index = workflowOutputIndex(context, nodeId, output)
  if (index < 0) return workflowInterfaceRejected('not_found')
  const nextName = name.trim()
  if (!nextName) return workflowInterfaceRejected('empty_name')
  if (context.outputs[index].name === nextName) return { status: 'unchanged' }
  if (exposedNameIsUsed(context, nextName, { collection: 'output', index })) {
    return workflowInterfaceRejected('duplicate_name', nextName)
  }
  const nextOutputs = context.outputs.map((item, itemIndex) => (
    itemIndex === index ? { ...item, name: nextName } : item
  ))
  if (!replaceWorkflowOutputs(nextOutputs)) return workflowInterfaceRejected('unavailable')
  emitInterfaceChanged()
  return { status: 'changed' }
}

function updateNodeParameter(
  nodeId: string,
  key: string,
  value: unknown,
): boolean {
  if (isLocked.value) return false
  const node = getNodes.value.find((candidate: any) => candidate.id === nodeId)
  if (!node?.data) return false
  const presentationStatus = canvasStatusProjection
    .statusForNode(nodeId)
    ?.presentationStatus
  node.data.parameters = {
    ...(node.data.parameters ?? {}),
    [key]: value,
  }
  canvasStatusProjection.stageCurrentSemanticStatuses()
  canvasStatusProjection.stageSemanticStatus(nodeId, {
    node_id: nodeId,
    status: 'unexecuted',
    cached: false,
  }, presentationStatus)
  emitGraphChanged({ statusesAlreadyStaged: true })
  return true
}

function stageGraphValidation(): void {
  canvasStatusProjection.stageCurrentSemanticStatuses()
}

function emitGraphChanged(options: GraphChangeOptions = {}) {
  const state = options.state ?? currentVueFlowState()
  const authoritativeGraph = options.authoritativeGraph
    ? rememberAuthoritativeGraph(options.authoritativeGraph)
    : null
  const exposedState = authoritativeGraph
    ? {
        ...state,
        edges: authoritativeGraph.edges.map(edge => vueFlowEdgeFromGraphEdge(edge)),
      }
    : state
  const historyState = canvasHistoryState(exposedState)
  undoRedo.push(historyState)
  if (!options.statusesAlreadyStaged) stageGraphValidation()
  if (isNestedWorkflowEditor && props.nestedWorkflowSessionId) {
    if (authoritativeGraph) {
      syncGraphState(authoritativeGraph)
    } else {
      syncGraph(state as any)
    }
    const graph = authoritativeGraph ?? rememberAuthoritativeGraph(
      serializeGraph(state) as GraphState,
    )
    nestedWorkflowSessionsStore.updateDraft(props.nestedWorkflowSessionId, graph)
    refreshInterfaceContextOnNodes()
    uiStore.markCanvasDirty(canvasId)
    emit('graph-changed', exposedState)
    return
  }
  markDirtyAndAutoSave(state, authoritativeGraph ?? undefined)
  emit('graph-changed', exposedState)
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
  createSelectedNestedWorkflow,
  openNestedWorkflow,
  applyNestedWorkflowDraft,
  saveNestedWorkflowSession,
  isValidConnection,
  clipboardData,
  projectedStatuses,
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
    :aria-busy="lifecycleOperation !== null || isInstallingAuthoritativeDraft"
  >
    <div
      v-if="lifecycleOperation"
      class="canvas-lifecycle-busy"
      role="status"
      aria-live="polite"
    >
      <i class="pi pi-spin pi-spinner" aria-hidden="true" />
      {{ lifecycleOperation === 'saving'
        ? 'Saving workflow…'
        : lifecycleOperation === 'discarding'
          ? 'Restoring saved workflow…'
          : 'Deleting workflow…' }}
    </div>
    <CanvasErrorBanner :validation-result="validationResult" />
    <CanvasPersistenceFeedback
      class="canvas-persistence-feedback-host"
      :state="canvasPersistenceFeedbackState"
      :issue="canvasPersistenceFeedbackIssue"
      :conflict-action-label="isNestedWorkflowEditor ? 'Keep my changes' : undefined"
      :conflict-secondary-action-label="isNestedWorkflowEditor ? 'Use latest snapshot' : null"
      :conflict-reopen-label="isNestedWorkflowEditor ? 'Resolve nested save conflict' : null"
      :conflict-actions-disabled="nestedConflictResolution !== null"
      @retry="retryCanvasPersistence"
      @resolve-conflict="resolveCanvasPersistenceConflict"
      @use-latest="useLatestNestedPersistenceSnapshot"
      @dismiss="dismissCanvasPersistenceIssue"
      @reopen-conflict="reopenCanvasPersistenceConflict"
    />
    <div
      v-if="shouldShowRemoteDraftConflict"
      class="workflow-draft-conflict"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      tabindex="0"
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
      :nodes-draggable="!isLocked"
      :edges-updatable="!isLocked"
      :fit-view-on-init="shouldFitViewOnInit"
      multi-selection-key-code="Shift"
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
      :can-open-nested-workflow="nodeContextMenu.canOpenNestedWorkflow"
      :has-workspace-source="nodeContextMenu.hasWorkspaceSource"
      @rename="renameContextNode"
      @enable-toggle="toggleContextNodeEnabled"
      @group-into-workflow="runContextNestedWorkflowAction"
      @open-workflow="runContextNestedWorkflowAction"
      @open-source-workflow="openContextSourceWorkflow"
      @update-from-source="updateContextWorkflowFromSource"
      @detach-source="detachContextWorkflowSource"
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

.canvas-lifecycle-busy {
  align-items: center;
  background: color-mix(in srgb, var(--bif-surface) 92%, transparent);
  border: 1px solid var(--bif-border-muted);
  border-radius: 0.375rem;
  display: flex;
  gap: 0.5rem;
  left: 50%;
  padding: 0.5rem 0.75rem;
  position: absolute;
  top: 0.75rem;
  transform: translateX(-50%);
  z-index: 20;
}

.canvas-persistence-feedback-host {
  bottom: 0.75rem;
  max-width: min(42rem, calc(100% - 1.5rem));
  position: absolute;
  right: 0.75rem;
  z-index: 20;
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
