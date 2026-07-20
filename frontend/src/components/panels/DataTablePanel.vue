<script setup lang="ts">
import { computed, effectScope, onBeforeUnmount, onMounted, ref, watch, type EffectScope } from 'vue'
import type { DockviewIDisposable, DockviewPanelApi } from 'dockview-core'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import MergedDataTable from './MergedDataTable.vue'
import NodeDataTable from './NodeDataTable.vue'
import { useGraphSync } from '@/composables/useGraphSync'
import {
  getCanvasStatusProjection,
  useCanvasStatusProjection,
  type CanvasStatusProjectionReader,
} from '@/composables/useCanvasStatusProjection'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useDataTableStore, type DataTableSourceRequest } from '@/stores/dataTable'
import type {
  ToolNodeState,
  WorkflowNodeState,
  WorkflowOutput,
} from '@/api/types'
import {
  maximumUpstreamDepth,
  resolveDataTableNodes,
  selectedAnchorsAreRelated,
} from '@/utils/dataTableSources'
import { canvasSessionRegistry, type CanvasId } from '@/sessions/canvasSessionRegistry'

type NodeState = ToolNodeState | WorkflowNodeState

const props = defineProps<{ params?: { api?: DockviewPanelApi } }>()
const uiStore = useUIStore()
const executionStore = useExecutionStore()
const activeStatusProjection = useCanvasStatusProjection()
const dataTableStore = useDataTableStore()
const { currentGraph } = useGraphSync()
const showAll = ref(false)

interface DataTableEntry {
  key: string
  displayNodeId: string
  dataNodeId: string
  label: string
  subtitle: string
  toolName: string | null
  disabled: boolean
  columnAliases: Record<string, string>
  columnFilter?: string[]
  role?: 'anchor' | 'context'
}

interface ResolvedWorkflowOutput {
  dataNodeId: string
  column: string
  toolName: string | null
}

interface DataTableTarget {
  canvasId: CanvasId | null
  workflowName: string | null
}

const graphNodes = computed(() => currentGraph.value.nodes)
const activeWorkflowId = computed(() => uiStore.activeWorkflowId)
const displayedNodeIds = computed(() => [...uiStore.selectedNodeIds])
const nodeById = computed<Record<string, NodeState>>(() => Object.fromEntries(
  graphNodes.value.map((node) => [node.id, node]),
))
const maximumDepth = computed(() => maximumUpstreamDepth(currentGraph.value, displayedNodeIds.value))
const upstreamDepth = computed({
  get: () => Math.min(dataTableStore.upstreamDepth, maximumDepth.value),
  set: (value: number | null) => dataTableStore.setUpstreamDepth(Math.min(value ?? 0, maximumDepth.value)),
})
const anchorsRelated = computed(() => selectedAnchorsAreRelated(
  currentGraph.value,
  displayedNodeIds.value,
))
const resolvedNodes = computed(() => resolveDataTableNodes(
  currentGraph.value,
  displayedNodeIds.value,
  upstreamDepth.value,
))

function isNestedWorkflowNode(
  node: NodeState | null | undefined,
): node is WorkflowNodeState {
  return node?.type === 'workflow'
}

function findNode(graph: { nodes?: NodeState[] } | null | undefined, nodeId: string): NodeState | null {
  return graph?.nodes?.find((node) => node.id === nodeId) ?? null
}

function nodeLabel(nodeId: string): string {
  return nodeById.value[nodeId]?.name ?? nodeId
}

function resolveWorkflowOutput(
  parent: WorkflowNodeState,
  exposed: WorkflowOutput,
): ResolvedWorkflowOutput {
  const scopedIds = [parent.id]
  let graph = parent.workflow
  let current = exposed
  while (true) {
    scopedIds.push(current.source.node)
    const target = findNode(graph, current.source.node)
    const nestedOutput = target?.type === 'workflow'
      ? target.workflow.interface.outputs.find(
          candidate => candidate.id === current.source.column,
        )
      : undefined
    if (!isNestedWorkflowNode(target) || !nestedOutput) {
      return {
        dataNodeId: scopedIds.join('/'),
        column: current.source.column,
        toolName: target?.type === 'tool' ? target.tool_name : null,
      }
    }
    graph = target?.workflow
    current = nestedOutput
  }
}

function entriesForNestedWorkflow(node: NodeState): DataTableEntry[] {
  const byDataNode = new Map<string, DataTableEntry>()
  if (node.type !== 'workflow') return []
  for (const exposed of node.workflow.interface.outputs) {
    const resolved = resolveWorkflowOutput(node, exposed)
    const entry = byDataNode.get(resolved.dataNodeId) ?? {
      key: `${node.id}:${resolved.dataNodeId}`,
      displayNodeId: node.id,
      dataNodeId: resolved.dataNodeId,
      label: nodeLabel(node.id),
      subtitle: resolved.dataNodeId,
      toolName: resolved.toolName,
      disabled: node.enabled === false,
      columnAliases: {},
      columnFilter: [],
    }
    entry.columnAliases[resolved.column] = exposed.name
    entry.columnFilter?.push(resolved.column)
    byDataNode.set(resolved.dataNodeId, entry)
  }
  return [...byDataNode.values()]
}

function entryForNode(nodeId: string): DataTableEntry[] {
  const node = nodeById.value[nodeId]
  if (!node) return []
  if (isNestedWorkflowNode(node)) return entriesForNestedWorkflow(node)
  return [{
    key: node.id,
    displayNodeId: node.id,
    dataNodeId: node.id,
    label: nodeLabel(node.id),
    subtitle: node.id,
    toolName: node.type === 'tool' ? node.tool_name : null,
    disabled: node.enabled === false,
    columnAliases: {},
  }]
}

const sourceEntries = computed(() => resolvedNodes.value.flatMap(({ nodeId, role }) =>
  entryForNode(nodeId).map((entry) => ({ ...entry, role })),
))
const projectionSources = computed<DataTableSourceRequest[]>(() => sourceEntries.value.map((entry) => ({
  node_id: entry.dataNodeId,
  role: entry.role ?? 'context',
  label: entry.label,
  tool_name: entry.toolName,
  columns: entry.columnFilter ?? null,
  column_aliases: entry.columnAliases,
})))
const projectionKey = computed(() => JSON.stringify({
  workflow_id: activeWorkflowId.value,
  sources: projectionSources.value,
}))
const localFallback = computed(() => displayedNodeIds.value.length > 1 && !anchorsRelated.value)
const isStacked = computed(() => localFallback.value || dataTableStore.projection?.mode === 'stacked')
const fallbackMessage = computed(() => localFallback.value
  ? 'The selected nodes are independent in this workflow, so their DataFrames are shown separately.'
  : dataTableStore.projection?.mode === 'stacked' ? dataTableStore.projection.message : null)
const stackedEntries = computed(() => isStacked.value ? sourceEntries.value : [])
const visibleStackedEntries = computed(() => showAll.value
  ? stackedEntries.value
  : stackedEntries.value.slice(0, 5))
const allSelectedDisabled = computed(() => displayedNodeIds.value.length > 0
  && displayedNodeIds.value.every((id) => nodeById.value[id]?.enabled === false))

function currentDataTableTarget(): DataTableTarget {
  return {
    canvasId: canvasSessionRegistry.activeCanvasId.value,
    workflowName: activeWorkflowId.value,
  }
}

function statusProjectionForTarget(target: DataTableTarget): CanvasStatusProjectionReader | null {
  return target.canvasId === null
    ? activeStatusProjection
    : getCanvasStatusProjection(target.canvasId)
}

function fetchEntry(entry: DataTableEntry): void {
  if (!dataTableStore.getNodeData(entry.dataNodeId) && !dataTableStore.isLoading(entry.dataNodeId)) {
    void dataTableStore.fetchNodeData(entry.dataNodeId, {
      toolName: entry.toolName,
      workflowName: activeWorkflowId.value,
    })
  }
}

function refreshProjection(): void {
  if (projectionSources.value.length === 0 || localFallback.value) {
    dataTableStore.clearProjection()
    return
  }
  void dataTableStore.fetchProjection({
    workflow_id: activeWorkflowId.value,
    sources: projectionSources.value,
  })
}

watch(maximumDepth, (maximum) => {
  if (dataTableStore.upstreamDepth > maximum) dataTableStore.setUpstreamDepth(maximum)
})
watch(projectionKey, refreshProjection, { immediate: true })
watch(stackedEntries, (entries) => entries.forEach(fetchEntry), { immediate: true })
watch(() => executionStore.lastResult, (result) => {
  if (result?.success) refreshProjection()
})

let scope: EffectScope | null = null
let activeChangeDisposable: DockviewIDisposable | null = null
watch(sourceEntries, (entries) => {
  const target = currentDataTableTarget()
  const statusProjection = statusProjectionForTarget(target)
  scope?.stop()
  scope = effectScope()
  scope.run(() => {
    for (const entry of entries) {
      if (statusProjection === null) continue
      watch(
        () => statusProjection.statusForNode(entry.dataNodeId)?.status,
        (next, previous) => {
          if (previous !== 'executed' && next === 'executed') refreshProjection()
          if (next === 'out_of_date' || next === 'unexecuted') {
            dataTableStore.clearCache(entry.dataNodeId)
            dataTableStore.clearProjection()
          }
        },
      )
    }
  })
}, { immediate: true })

onMounted(() => {
  activeChangeDisposable = props.params?.api?.onDidActiveChange(({ isActive }) => {
    if (isActive) refreshProjection()
  }) ?? null
})
onBeforeUnmount(() => {
  scope?.stop()
  activeChangeDisposable?.dispose()
})
</script>

<template>
  <div class="data-table-panel" data-testid="data-table-panel">
    <div v-if="graphNodes.length === 0" class="data-table-panel__placeholder">
      No nodes in the workflow.
    </div>
    <div v-else-if="displayedNodeIds.length === 0" class="data-table-panel__placeholder">
      No node selected.
    </div>
    <div v-else-if="allSelectedDisabled" class="data-table-panel__placeholder">
      All selected nodes are disabled.
    </div>
    <template v-else>
      <div
        v-if="dataTableStore.projectionError || (dataTableStore.projectionLoading && !dataTableStore.projection)"
        class="data-table-panel__controls data-table-panel__controls--standalone"
      >
        <label for="data-table-upstream-depth">Upstream levels</label>
        <InputNumber
          input-id="data-table-upstream-depth"
          v-model="upstreamDepth"
          :min="0"
          :max="maximumDepth"
          :step="1"
          show-buttons
          size="small"
          data-testid="upstream-depth"
        />
      </div>
      <div v-if="dataTableStore.projectionError" class="data-table-panel__error">
        {{ dataTableStore.projectionError }}
      </div>
      <div
        v-else-if="dataTableStore.projectionLoading && !dataTableStore.projection"
        class="data-table-panel__placeholder"
      >
        Loading consolidated data...
      </div>
      <MergedDataTable
        v-else-if="dataTableStore.projection?.mode === 'merged'"
        :workflow-id="activeWorkflowId"
      >
        <template #toolbar-actions>
          <div class="data-table-panel__controls">
            <label for="data-table-upstream-depth">Upstream levels</label>
            <InputNumber
              input-id="data-table-upstream-depth"
              v-model="upstreamDepth"
              :min="0"
              :max="maximumDepth"
              :step="1"
              show-buttons
              size="small"
              data-testid="upstream-depth"
            />
          </div>
        </template>
      </MergedDataTable>
      <template v-else-if="isStacked">
        <div class="data-table-panel__info" data-testid="data-table-fallback">
          {{ fallbackMessage }}
        </div>
        <div v-if="stackedEntries.length > 5" class="data-table-panel__limit">
          <Button
            size="small"
            text
            :label="showAll ? 'Show first 5' : `Show all (${stackedEntries.length})`"
            @click="showAll = !showAll"
          />
        </div>
        <section
          v-for="(entry, index) in visibleStackedEntries"
          :key="entry.key"
          class="data-table-panel__node"
        >
          <header class="data-table-panel__header">
            <h3>{{ entry.label }}</h3>
            <span class="data-table-panel__id">{{ entry.subtitle }}</span>
          </header>
          <div v-if="entry.disabled" class="data-table-panel__disabled">
            This node is disabled.
          </div>
          <NodeDataTable
            :node-id="entry.dataNodeId"
            :tool-name="entry.toolName"
            :workflow-name="activeWorkflowId"
            :disabled="entry.disabled"
            :column-aliases="entry.columnAliases"
            :column-filter="entry.columnFilter"
          >
            <template v-if="index === 0" #toolbar-actions>
              <div class="data-table-panel__controls">
                <label for="data-table-upstream-depth">Upstream levels</label>
                <InputNumber
                  input-id="data-table-upstream-depth"
                  v-model="upstreamDepth"
                  :min="0"
                  :max="maximumDepth"
                  :step="1"
                  show-buttons
                  size="small"
                  data-testid="upstream-depth"
                />
              </div>
            </template>
          </NodeDataTable>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.data-table-panel {
  height: 100%;
  overflow: auto;
  padding: 0.75rem;
}

.data-table-panel__placeholder {
  color: var(--p-text-muted-color);
  padding: 1.5rem;
}

.data-table-panel__controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.data-table-panel__controls--standalone {
  margin-bottom: 0.75rem;
}

.data-table-panel__controls :deep(.p-inputnumber-input) {
  width: 5rem;
}

.data-table-panel__info,
.data-table-panel__error {
  border: 1px solid var(--bif-border-strong);
  border-radius: 0.25rem;
  margin-bottom: 0.75rem;
  padding: 0.5rem 0.75rem;
}

.data-table-panel__info {
  background: var(--p-blue-50);
  color: var(--p-blue-800);
}

.data-table-panel__error {
  background: var(--p-red-50);
  color: var(--p-red-800);
}

.data-table-panel__limit {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.5rem;
}

.data-table-panel__node {
  margin-bottom: 1rem;
}

.data-table-panel__header {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.data-table-panel__header h3 {
  font-size: 1rem;
  margin: 0;
}

.data-table-panel__id {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
}

.data-table-panel__disabled {
  color: var(--p-orange-700);
  background: var(--p-orange-50);
  border: 1px solid var(--p-orange-200);
  padding: 0.375rem 0.5rem;
  margin: 0.5rem 0;
}
</style>
