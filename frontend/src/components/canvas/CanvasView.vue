<script setup lang="ts">
import { ref, markRaw, toRef } from 'vue'
import { VueFlow, useVueFlow, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import ToolNode from './ToolNode.vue'
import ColumnRefEdge from './ColumnRefEdge.vue'
import PositionalEdge from './PositionalEdge.vue'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { generateNodeId, generateNodeName } from '@/utils/nodeIdGenerator'
import { serializeSelection, deserializeSelection } from '@/utils/clipboard'
import { useUndoRedo } from '@/composables/useUndoRedo'
import { useGraphSync } from '@/composables/useGraphSync'
import type { ClipboardData } from '@/utils/clipboard'
import type { ToolMetadata } from '@/api/types'

const props = defineProps<{
  nodes: any[]
  edges: any[]
}>()

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

const {
  project,
  addNodes,
  addEdges,
  removeNodes,
  removeEdges,
  getNodes,
  getEdges,
  onConnect,
  onNodesChange,
  fitView,
} = useVueFlow()

const { syncGraph, flushNow } = useGraphSync()
const undoRedo = useUndoRedo<{ nodes: any[]; edges: any[] }>()

const clipboardData = ref<ClipboardData | null>(null)
const canvasRef = ref<HTMLDivElement | null>(null)

// --- Connection handling ---

onConnect((connection) => {
  const newEdge = {
    id: `e-${connection.source}-${connection.sourceHandle}-${connection.target}-${connection.targetHandle}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle,
    targetHandle: connection.targetHandle,
    type: 'column_ref',
  }
  addEdges([newEdge])
  emitGraphChanged()
})

onNodesChange((changes) => {
  const hasSelectionChange = changes.some((c: any) => c.type === 'select')
  if (hasSelectionChange) {
    const selectedIds = getNodes.value
      .filter((n: any) => n.selected)
      .map((n: any) => n.id)
    emit('node-selected', selectedIds)
  }
})

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
    removeEdges(selectedEdges.map((e: any) => e.id))
    emitGraphChanged()
    return
  }

  const selectedNodeIds = new Set(selectedNodes.map((n: any) => n.id))

  // Remove edges connected to deleted nodes
  const edgesToRemove = getEdges.value.filter(
    (e: any) => selectedNodeIds.has(e.source) || selectedNodeIds.has(e.target),
  )
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
      emit('graph-changed', state)
    }
    return
  }

  if (meta && event.key === 'z') {
    const state = undoRedo.undo()
    if (state) {
      emit('graph-changed', state)
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
      :nodes="props.nodes"
      :edges="props.edges"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :is-valid-connection="isValidConnection"
      :selection-key-code="'Shift'"
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
