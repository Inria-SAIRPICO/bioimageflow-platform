<script setup lang="ts">
import { ref, watch, markRaw, onMounted } from 'vue'
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
import { useGraphSync } from '@/composables/useGraphSync'
import type { ClipboardData } from '@/utils/clipboard'
import type { ToolMetadata } from '@/api/types'

const emit = defineEmits<{
  'graph-changed': [payload: { nodes: any[]; edges: any[] }]
  'node-selected': [nodeIds: string[]]
}>()

const nodeTypes = {
  tool: markRaw(ToolNode),
}

const edgeTypes = {
  column_ref: markRaw(ColumnRefEdge),
  positional: markRaw(PositionalEdge),
}

const toolRegistryStore = useToolRegistryStore()
const uiStore = useUIStore()

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
  onConnect,
  onNodesChange,
  onEdgeUpdate,
  onEdgeUpdateEnd,
  onNodeDragStart,
  onNodeDragStop,
  fitView,
} = useVueFlow()

const { syncGraph, flushNow, loadWorkflow } = useGraphSync()
const undoRedo = useUndoRedo<{ nodes: any[]; edges: any[] }>()

const clipboardData = ref<ClipboardData | null>(null)
const canvasRef = ref<HTMLDivElement | null>(null)
const dragStartPositions = ref<Record<string, { x: number; y: number }>>({})

// --- Restore persisted workflow on mount ---

onMounted(async () => {
  const saved = await loadWorkflow()
  if (saved && saved.nodes.length > 0) {
    setNodes(saved.nodes)
    setEdges(saved.edges)
    syncGraph({ nodes: saved.nodes, edges: saved.edges })
  }
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
  const targetHandle = connection.targetHandle ?? ''
  // Enforce one incoming edge per (non-positional) input. When users drag from
  // an already-connected input pin, Vue Flow issues a fresh connect rather than
  // an edge-update; this keeps the graph consistent either way.
  clearExistingIncomingEdge(connection.target, targetHandle)

  const isPositional = targetHandle.startsWith('__positional_')
  const newEdge = {
    id: `e-${connection.source}-${connection.sourceHandle}-${connection.target}-${targetHandle}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle,
    targetHandle,
    type: isPositional ? 'positional' : 'column_ref',
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

  // Enforce single incoming edge on the new target input
  clearExistingIncomingEdge(newTarget, newTargetHandle)

  // Rewrite the edge: remove the old one, add a rebuilt one with new endpoints
  removeEdges([edge.id])
  const isPositional = newTargetHandle.startsWith('__positional_')
  const replacement = {
    id: `e-${newSource}-${newSourceHandle}-${newTarget}-${newTargetHandle}`,
    source: newSource,
    target: newTarget,
    sourceHandle: newSourceHandle,
    targetHandle: newTargetHandle,
    type: isPositional ? 'positional' : 'column_ref',
  }
  addEdges([replacement])

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
  }

  emitGraphChanged()
})

// Edge disconnect: dragging a connected handle to empty space (no onEdgeUpdate
// fired for this gesture).
onEdgeUpdateEnd(({ edge }) => {
  if (updatedEdgeIds.delete(edge.id)) return
  removeEdges([edge.id])
  cleanupDisconnectedInput(edge.target, edge.targetHandle ?? '')
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

function isValidConnection(connection: {
  source: string
  target: string
  sourceHandle: string | null
  targetHandle: string | null
}): boolean {
  // 1. Type compatibility check
  const sourceNode = getNodes.value.find((n: any) => n.id === connection.source)
  const targetNode = getNodes.value.find((n: any) => n.id === connection.target)
  if (!sourceNode || !targetNode) return false

  const sourceTool: ToolMetadata | undefined = toolRegistryStore.getToolByName(
    sourceNode.data?.toolName,
  )
  const targetTool: ToolMetadata | undefined = toolRegistryStore.getToolByName(
    targetNode.data?.toolName,
  )
  if (!sourceTool || !targetTool) return false

  if (connection.sourceHandle && connection.targetHandle) {
    const sourceOutput = sourceTool.outputs[connection.sourceHandle]
    const targetInput = targetTool.inputs[connection.targetHandle]
    if (sourceOutput && targetInput && sourceOutput.type !== targetInput.type) {
      return false
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
    if (field.connectable) {
      const isPathType = ['Path', 'ImagePath', 'MaskPath'].includes(field.type)
      const isRequired = !field.optional
      pinnedInputs[key] = isPathType && isRequired
    }
  }

  // Build default output templates for path-typed outputs
  const output_templates: Record<string, string> = {}
  for (const [key, field] of Object.entries(tool.outputs)) {
    if (['Path', 'ImagePath', 'MaskPath'].includes(field.type)) {
      output_templates[key] = field.default || ''
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
  const selectedNodes = getNodes.value.filter((n: any) => n.selected)
  if (selectedNodes.length === 0) {
    // Delete selected edges
    const selectedEdges = getEdges.value.filter((e: any) => e.selected)
    if (selectedEdges.length === 0) return
    // Clean up connectedInputs for each removed edge
    for (const edge of selectedEdges) {
      cleanupDisconnectedInput(edge.target, edge.targetHandle ?? '')
    }
    removeEdges(selectedEdges.map((e: any) => e.id))
    emitGraphChanged()
    return
  }

  const selectedNodeIds = new Set(selectedNodes.map((n: any) => n.id))

  // Remove edges connected to deleted nodes
  const edgesToRemove = getEdges.value.filter(
    (e: any) => selectedNodeIds.has(e.source) || selectedNodeIds.has(e.target),
  )

  // Clean up connectedInputs on surviving target nodes
  for (const edge of edgesToRemove) {
    if (!selectedNodeIds.has(edge.target)) {
      cleanupDisconnectedInput(edge.target, edge.targetHandle ?? '')
    }
  }

  removeEdges(edgesToRemove.map((e: any) => e.id))
  removeNodes(selectedNodes.map((n: any) => n.id))
  emitGraphChanged()
}

function copySelected() {
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
        if (field.connectable) {
          const isPathType = ['Path', 'ImagePath', 'MaskPath'].includes(field.type)
          const isRequired = !field.optional
          pinnedInputs[key] = isPathType && isRequired
        }
      }
      for (const [key, field] of Object.entries(tool.outputs)) {
        if (['Path', 'ImagePath', 'MaskPath'].includes(field.type)) {
          output_templates[key] = field.default || ''
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

  if (event.key === 'Delete' || event.key === 'Backspace') {
    deleteSelected()
    return
  }

  if (meta && event.key === 'c') {
    copySelected()
    return
  }

  if (meta && event.key === 'v') {
    pasteFromClipboard()
    return
  }

  if (meta && event.key === 'a') {
    event.preventDefault()
    selectAll()
    return
  }

  if (meta && event.shiftKey && (event.key === 'z' || event.key === 'Z')) {
    const state = undoRedo.redo()
    if (state) {
      setNodes(state.nodes)
      setEdges(state.edges)
      syncGraph(state as any)
    }
    return
  }

  if (meta && event.key === 'z') {
    const state = undoRedo.undo()
    if (state) {
      setNodes(state.nodes)
      setEdges(state.edges)
      syncGraph(state as any)
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

function emitGraphChanged() {
  const state = {
    nodes: getNodes.value.map((n: any) => ({ ...n })),
    edges: getEdges.value.map((e: any) => ({ ...e })),
  }
  undoRedo.push(state)
  syncGraph(state as any)
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
      :selection-key-code="'Shift'"
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
