<script setup lang="ts">
import { ref, watch, markRaw, nextTick, onMounted, onBeforeUnmount, provide } from 'vue'
import { VueFlow, useVueFlow, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import ToolNode from './ToolNode.vue'
import ColumnRefEdge from './ColumnRefEdge.vue'
import PositionalEdge from './PositionalEdge.vue'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useUIStore } from '@/stores/ui'
import { generateNodeId, generateNodeName } from '@/utils/nodeIdGenerator'
import { serializeSelection, deserializeSelection } from '@/utils/clipboard'
import { useUndoRedo } from '@/composables/useUndoRedo'
import { serializeGraph, useGraphSync } from '@/composables/useGraphSync'
import { useAutoSave } from '@/composables/useAutoSave'
import { useExecutionLock } from '@/composables/useExecutionLock'
import { useStatusReconciliation, type NodeStateMessage } from '@/composables/useStatusReconciliation'
import { useExecutionStore } from '@/stores/execution'
import { useResolvedOutputsStore } from '@/stores/resolvedOutputs'
import { useWorkflowStore } from '@/stores/workflow'
import { graphStateToVueFlow } from '@/utils/workflowGraph'
import type { GraphState, MissingTool, NodeState } from '@/api/types'
import type { ClipboardData } from '@/utils/clipboard'
import type { ToolMetadata } from '@/api/types'

const emit = defineEmits<{
  'graph-changed': [payload: { nodes: any[]; edges: any[] }]
  'node-selected': [nodeIds: string[]]
}>()

// Vue Flow's NodeTypesObject/EdgeTypesObject uses very strict component
// constraints that Vue's SFC-inferred types don't satisfy. The runtime
// contract (`key -> component`) is what VueFlow actually uses.
const nodeTypes = {
  tool: markRaw(ToolNode),
} as unknown as Record<string, object>

const edgeTypes = {
  column_ref: markRaw(ColumnRefEdge),
  positional: markRaw(PositionalEdge),
} as unknown as Record<string, object>

const toolRegistryStore = useToolRegistryStore()
const uiStore = useUIStore()
const workflowStore = useWorkflowStore()
const autoSave = useAutoSave()
const resolvedOutputsStore = useResolvedOutputsStore()

// Provide the resolved-outputs map so ToolNode can read it via inject.
provide('bioimageflow:resolvedOutputs', resolvedOutputsStore.resolvedOutputsByNodeId)

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
} = useVueFlow()

const { syncGraph, flushNow, patchParameters, validationResult, syncState } = useGraphSync()
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
})

// Live per-node status from the execution store — takes precedence over the
// validation-result status while an execution is running so nodes turn green
// (executed) or pulse blue (running) in real time as events arrive.
watch(
  () => executionStore.nodeStatuses,
  (statuses) => {
    if (!statuses) return
    for (const node of getNodes.value) {
      const s = statuses[node.id]
      if (s && node.data && node.data.status !== s.status) {
        node.data.status = s.status
      }
    }
  },
  { deep: true },
)

const clipboardData = ref<ClipboardData | null>(null)
const canvasRef = ref<HTMLDivElement | null>(null)
const dragStartPositions = ref<Record<string, { x: number; y: number }>>({})

// --- Workflow startup / graph application ---

async function applyGraphState(
  graph: GraphState,
  missingTools: MissingTool[] = [],
  dirty = false,
) {
  const vueFlowGraph = graphStateToVueFlow(
    graph,
    toolRegistryStore.getToolByName,
    missingTools,
  )
  setNodes([])
  setEdges([])
  await nextTick()
  setNodes(vueFlowGraph.nodes)
  // Wait for node components (and their <Handle> DOM elements) to mount
  // before setting edges — Vue Flow resolves edge endpoints against live
  // handle elements, so edges added in the same tick as nodes render with
  // no visible path.
  await nextTick()
  setEdges(vueFlowGraph.edges)
  syncGraph(vueFlowGraph)
  if (dirty) {
    workflowStore.markDirty()
  } else {
    workflowStore.markClean()
  }
}

async function ensureDefaultWorkflow(): Promise<GraphState> {
  const base = 'Untitled'
  const names = new Set(workflowStore.workflows.map((workflow) => workflow.name))
  let name = base
  let suffix = 2
  while (names.has(name)) {
    name = `${base}_${suffix}`
    suffix += 1
  }
  await workflowStore.createWorkflow({ name, display_name: name })
  return { nodes: [], edges: [] }
}

async function recoverStartupWorkflow() {
  await workflowStore.fetchWorkflows()
  const autoSaved = await autoSave.loadMostRecentAutoSave()
  const lastOpened = await autoSave.getLastOpenedWorkflow()
  const targetName = autoSaved?.name ?? lastOpened
  const exists = targetName
    ? workflowStore.workflows.some((workflow) => workflow.name === targetName)
    : false

  if (targetName && exists) {
    const serverGraph = await workflowStore.loadWorkflow(targetName)
    return {
      graph: autoSaved?.name === targetName ? autoSaved.graph : serverGraph,
      dirty: autoSaved?.name === targetName,
    }
  }

  return {
    graph: await ensureDefaultWorkflow(),
    dirty: false,
  }
}

async function handleApplyGraphEvent(event: Event) {
  const detail = (event as CustomEvent<{
    graph: GraphState
    missingTools?: MissingTool[]
    dirty?: boolean
  }>).detail
  if (!detail?.graph) return
  await applyGraphState(detail.graph, detail.missingTools ?? [], detail.dirty ?? false)
}

onMounted(async () => {
  window.addEventListener('bioimageflow:apply-graph', handleApplyGraphEvent)
  if (toolRegistryStore.tools.length === 0) {
    await toolRegistryStore.fetchTools()
  }
  const recovered = await recoverStartupWorkflow()
  await applyGraphState(
    recovered.graph,
    workflowStore.missingTools,
    recovered.dirty,
  )
})

onBeforeUnmount(() => {
  window.removeEventListener('bioimageflow:apply-graph', handleApplyGraphEvent)
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
    uiStore.setSelectedNodes(selectedIds)
    emit('node-selected', selectedIds)
  }
})

// Sync graph nodes to UI store for NodePanel
watch(getNodes, (nodes) => {
  uiStore.setGraphNodes(nodes)
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
  })),
  () => {
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
    if (!tools || tools.length === 0) return
    const byName = new Map(tools.map((t) => [t.name, t]))
    for (const n of getNodes.value as any[]) {
      const toolName = n.data?.toolName
      if (!toolName) continue
      const fresh = byName.get(toolName)
      if (!fresh) continue
      const prev = n.data.tool
      if (prev && prev.package_version === fresh.package_version) continue
      n.data.tool = fresh
      // Only invalidate executed nodes — leave unexecuted/failed/disabled
      // alone so the version switch doesn't visually thrash the canvas.
      if (n.data.status === 'executed') {
        n.data.status = 'out_of_date'
      }
    }
    emitGraphChanged()
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
  resolvedOutputsStore.refreshResolvedOutputs(nodeId, getGraph, getToolForNode)
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
  const sourceTool: ToolMetadata | undefined =
    (sourceNode.data?.tool as ToolMetadata | undefined) ??
    toolRegistryStore.getToolByName(sourceNode.data?.toolName)
  const targetTool: ToolMetadata | undefined =
    (targetNode.data?.tool as ToolMetadata | undefined) ??
    toolRegistryStore.getToolByName(targetNode.data?.toolName)
  if (!sourceTool || !targetTool) return false

  // 1b. Reject positional edges into source DataFrameTools
  const th = connection.targetHandle ?? ''
  if (th.startsWith('__positional_') && targetTool.accepts_upstream === false) {
    return false
  }

  if (connection.sourceHandle && connection.targetHandle) {
    // Skip type checks for header-to-header connections (DataFrame-level)
    if (!sourceIsHeader) {
      const sourceOutput = sourceTool.outputs[connection.sourceHandle] as
        | { type?: string }
        | undefined

      // Also check resolved outputs for dynamic-output tools.
      let sourceType = sourceOutput?.type
      if (!sourceType && sourceTool.dynamic_outputs) {
        const resolved = resolvedOutputsStore.resolvedOutputsByNodeId[connection.source]
        if (resolved?.resolved && resolved.columns) {
          const col = (resolved.columns as Record<string, any>)[connection.sourceHandle!]
          sourceType = col?.type
        }
      }

      const targetInput = targetTool.inputs[connection.targetHandle]
      if (sourceType && targetInput?.type) {
        // "any" type is compatible with any consumer input type.
        if (sourceType === 'any') {
          // Accept — skip type-mismatch rejection.
        } else {
          // Path-family types (Path / ImagePath / MaskPath) all share the same
          // runtime carrier (a filesystem path); the distinction is metadata
          // (image_spec semantics, formats, layouts). Treat them as mutually
          // compatible at the frontend pre-flight; the bioimageflow library
          // performs the authoritative semantic check on graph validate.
          const PATH_FAMILY = new Set(['Path', 'ImagePath', 'MaskPath'])
          const same = sourceType === targetInput.type
          const bothPath = PATH_FAMILY.has(sourceType) && PATH_FAMILY.has(targetInput.type)
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
      const isPathType = ['Path', 'ImagePath', 'MaskPath'].includes(field.type)
      pinnedInputs[key] = isPathType && field.required
    }
  }

  // Build default output templates for path-typed outputs.
  // ProcessingTool only — DataFrameTool Outputs are column declarations,
  // not file paths, and must not get an output_templates entry.
  const output_templates: Record<string, string> = {}
  if (tool.tool_type !== 'DataFrameTool') {
    for (const [key, rawField] of Object.entries(tool.outputs)) {
      const field = rawField as { type?: string; default?: string } | undefined
      if (field && ['Path', 'ImagePath', 'MaskPath'].includes(field.type ?? '')) {
        output_templates[key] = field.default || ''
      }
    }
  }

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

  addNodes([newNode])
  emitGraphChanged()
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

  const nodesForClip = getNodes.value
    .filter((n: any) => selectedIds.has(n.id))
    .map((n: any) => ({
      id: n.id,
      name: n.data?.name ?? '',
      tool_name: n.data?.toolName ?? '',
      position: [n.position?.x ?? 0, n.position?.y ?? 0] as [number, number],
      parameters: n.data?.parameters ?? {},
    }))

  const edgesForClip = getEdges.value
    .filter((e: any) => selectedIds.has(e.source) && selectedIds.has(e.target))
    .map((e: any) => ({
      id: e.id,
      source_node: e.source,
      target_node: e.target,
      source_output: e.sourceHandle ?? '',
      target_input: e.targetHandle ?? '',
    }))

  clipboardData.value = serializeSelection(nodesForClip, edgesForClip, selectedIds)
}

function pasteFromClipboard() {
  if (isLocked.value) return
  if (!clipboardData.value) return

  const existingIds = getNodes.value.map((n: any) => n.id)
  const existingNames = getNodes.value.map((n: any) => n.data?.name ?? '')

  const deserialized = deserializeSelection(
    clipboardData.value,
    existingIds,
    existingNames,
  )

  // Create Vue Flow nodes from deserialized data
  const newNodes = deserialized.nodes.map((n) => {
    const tool = toolRegistryStore.getToolByName(n.tool_name)
    const pinnedInputs: Record<string, boolean> = {}
    const output_templates: Record<string, string> = {}
    if (tool) {
      for (const [key, field] of Object.entries(tool.inputs)) {
        if (field.connectable !== 'never') {
          const isPathType = ['Path', 'ImagePath', 'MaskPath'].includes(field.type)
          pinnedInputs[key] = isPathType && field.required
        }
      }
      // ProcessingTool only — see comment in createNodeForTool.
      if (tool.tool_type !== 'DataFrameTool') {
        for (const [key, rawField] of Object.entries(tool.outputs)) {
          const field = rawField as { type?: string; default?: string } | undefined
          if (field && ['Path', 'ImagePath', 'MaskPath'].includes(field.type ?? '')) {
            output_templates[key] = field.default || ''
          }
        }
      }
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
        collapsed: false,
        enabled: true,
        connectedInputs: {},
        pinnedInputs,
        output_templates,
      },
    }
  })

  const newEdges = deserialized.edges.map((e) => ({
    id: e.id,
    source: e.source_node,
    target: e.target_node,
    sourceHandle: e.source_output,
    targetHandle: e.target_input,
    type: 'column_ref',
  }))

  addNodes(newNodes)
  addEdges(newEdges)
  emitGraphChanged()
}

function selectAll() {
  for (const node of getNodes.value) {
    node.selected = true
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
    if (locked) {
      event.preventDefault()
    }
    return
  }

  if (meta && event.shiftKey && (event.key === 'z' || event.key === 'Z')) {
    if (locked) return
    const state = undoRedo.redo()
    if (state) {
      setNodes(state.nodes)
      setEdges(state.edges)
      syncGraph(state as any)
      markDirtyAndAutoSave(state)
    }
    return
  }

  if (meta && event.key === 'z') {
    if (locked) return
    const state = undoRedo.undo()
    if (state) {
      setNodes(state.nodes)
      setEdges(state.edges)
      syncGraph(state as any)
      markDirtyAndAutoSave(state)
    }
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
  const name = workflowStore.currentName
  if (!name) return
  workflowStore.markDirty()
  autoSave.scheduleAutoSave(name, serializeGraph(state))
}

function emitGraphChanged() {
  const state = {
    nodes: getNodes.value.map((n: any) => ({ ...n })),
    edges: getEdges.value.map((e: any) => ({ ...e })),
  }
  undoRedo.push(state)
  // Update the reconciliation node list to match the current graph.
  reconciliationNodes.value = state.nodes.map((n: any) => ({
    id: n.id,
    name: n.data?.name ?? n.id,
    tool_name: n.data?.toolName ?? '',
    position: [n.position?.x ?? 0, n.position?.y ?? 0],
    parameters: n.data?.parameters ?? {},
  })) as NodeState[]
  // Mark all nodes provisional during the debounce window so the UI can
  // render a desaturated status indicator until the server response lands.
  for (const n of state.nodes) {
    markProvisional(n.id, 'unexecuted')
  }
  syncGraph(state as any)
  markDirtyAndAutoSave(state)
  emit('graph-changed', state)
}

// Expose for testing
defineExpose({
  onAddNode,
  deleteSelected,
  copySelected,
  pasteFromClipboard,
  selectAll,
  isValidConnection,
  clipboardData,
  patchParameters,
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
    <VueFlow
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :is-valid-connection="isValidConnection"
      :edges-updatable="true"
      fit-view-on-init
    >
      <Background :variant="'dots'" :gap="16" :size="1" />
      <Controls />
    </VueFlow>
  </div>
</template>

<style scoped>
.canvas-view {
  width: 100%;
  height: 100%;
  outline: none;
}
</style>
