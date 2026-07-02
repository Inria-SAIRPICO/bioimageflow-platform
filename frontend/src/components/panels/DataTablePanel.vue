<script setup lang="ts">
import { computed, effectScope, onBeforeUnmount, ref, watch, type EffectScope } from 'vue'
import Button from 'primevue/button'
import NodeDataTable from './NodeDataTable.vue'
import { useGraphSync } from '@/composables/useGraphSync'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useDataTableStore } from '@/stores/dataTable'
import { useWorkflowStore } from '@/stores/workflow'
import type { NodeState, PublishedOutput } from '@/api/types'

const uiStore = useUIStore()
const executionStore = useExecutionStore()
const dataTableStore = useDataTableStore()
const workflowStore = useWorkflowStore()
const { currentGraph } = useGraphSync()

const showAll = ref(false)

const graphNodes = computed(() => currentGraph.value.nodes)

const nodeById = computed<Record<string, NodeState>>(() => {
  const out: Record<string, NodeState> = {}
  for (const node of graphNodes.value) out[node.id] = node
  return out
})

const displayedNodeIds = computed(() => {
  if (uiStore.selectedNodeIds.length > 0) return uiStore.selectedNodeIds
  return []
})

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
}

interface ResolvedPublishedOutput {
  dataNodeId: string
  column: string
  toolName: string | null
}

function isSubWorkflowNode(node: NodeState | null | undefined): boolean {
  return node?.tool_name === '__sub_workflow__'
}

function findNode(graph: { nodes?: NodeState[] } | null | undefined, nodeId: string): NodeState | null {
  return graph?.nodes?.find((node) => node.id === nodeId) ?? null
}

function resolvePublishedOutput(
  parent: NodeState,
  published: PublishedOutput,
): ResolvedPublishedOutput {
  const scopedIds = [parent.id]
  let graph = parent.sub_workflow
  let current = published

  while (true) {
    scopedIds.push(current.internal_node_id)
    const target = findNode(graph, current.internal_node_id)
    const nestedOutput = target?.published_outputs?.find(
      (candidate) => candidate.name === current.internal_output,
    )
    if (!isSubWorkflowNode(target) || !nestedOutput) {
      return {
        dataNodeId: scopedIds.join('/'),
        column: current.internal_output,
        toolName: target?.tool_name ?? null,
      }
    }
    graph = target?.sub_workflow
    current = nestedOutput
  }
}

function entriesForSubWorkflow(node: NodeState): DataTableEntry[] {
  const byDataNode = new Map<string, DataTableEntry>()
  for (const published of node.published_outputs ?? []) {
    const resolved = resolvePublishedOutput(node, published)
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
    entry.columnAliases[published.name] = published.name
    entry.columnAliases[published.internal_output] = published.name
    entry.columnAliases[resolved.column] = published.name
    entry.columnFilter?.push(resolved.column)
    byDataNode.set(resolved.dataNodeId, entry)
  }
  return Array.from(byDataNode.values())
}

function entryForNode(nodeId: string): DataTableEntry[] {
  const node = nodeById.value[nodeId]
  if (!node) return []
  if (isSubWorkflowNode(node)) return entriesForSubWorkflow(node)
  return [{
    key: node.id,
    displayNodeId: node.id,
    dataNodeId: node.id,
    label: nodeLabel(node.id),
    subtitle: node.id,
    toolName: node.tool_name ?? null,
    disabled: node.enabled === false,
    columnAliases: {},
  }]
}

const displayedEntries = computed(() => displayedNodeIds.value.flatMap(entryForNode))

const visibleEntries = computed(() => {
  if (displayedEntries.value.length > 5 && !showAll.value) {
    return displayedEntries.value.slice(0, 5)
  }
  return displayedEntries.value
})

const allTerminalDisabled = computed(() =>
  displayedNodeIds.value.length > 0 &&
  displayedNodeIds.value.every((id) => nodeById.value[id]?.enabled === false),
)

const allDisplayedWithoutData = computed(() =>
  displayedNodeIds.value.length > 0 &&
  (
    displayedEntries.value.length === 0 ||
    displayedEntries.value.every((entry) =>
      !dataTableStore.getNodeData(entry.dataNodeId) &&
      !dataTableStore.isLoading(entry.dataNodeId) &&
      !dataTableStore.isPending(entry.dataNodeId) &&
      !dataTableStore.getError(entry.dataNodeId),
    )
  ),
)

function nodeLabel(nodeId: string): string {
  return nodeById.value[nodeId]?.name ?? nodeId
}

function fetchIfMissing(entry: DataTableEntry) {
  if (!dataTableStore.getNodeData(entry.dataNodeId) && !dataTableStore.isLoading(entry.dataNodeId)) {
    void dataTableStore.fetchNodeData(entry.dataNodeId, {
      toolName: entry.toolName,
      workflowName: workflowStore.currentName,
    })
  }
}

function refreshEntry(entry: DataTableEntry) {
  void dataTableStore.fetchNodeData(entry.dataNodeId, {
    toolName: entry.toolName,
    workflowName: workflowStore.currentName,
  })
}

let scope: EffectScope | null = null

watch(
  displayedEntries,
  (entries) => {
    scope?.stop()
    scope = effectScope()
    scope.run(() => {
      for (const entry of entries) {
        fetchIfMissing(entry)
        watch(
          () => executionStore.nodeStatuses[entry.dataNodeId]?.status,
          (next, prev) => {
            if (prev !== 'executed' && next === 'executed') {
              refreshEntry(entry)
            } else if (next === 'out_of_date' || next === 'unexecuted') {
              dataTableStore.clearCache(entry.dataNodeId)
            }
          },
        )
      }
    })
  },
  { immediate: true },
)

watch(
  () => executionStore.lastResult,
  (result) => {
    if (!result?.success) return
    const refreshed = new Set<string>()
    for (const entry of displayedEntries.value) {
      if (refreshed.has(entry.dataNodeId)) continue
      const status = result.node_statuses?.[entry.dataNodeId]
      if (status?.status === 'executed') {
        refreshed.add(entry.dataNodeId)
        refreshEntry(entry)
      }
    }
  },
)

onBeforeUnmount(() => scope?.stop())
</script>

<template>
  <div
    class="data-table-panel"
    data-testid="data-table-panel"
  >
    <div
      v-if="graphNodes.length === 0"
      class="data-table-panel__placeholder"
    >
      No nodes in the workflow.
    </div>
    <div
      v-else-if="displayedNodeIds.length === 0"
      class="data-table-panel__placeholder"
    >
      No node selected.
    </div>
    <div
      v-else-if="allTerminalDisabled"
      class="data-table-panel__placeholder"
    >
      All terminal nodes are disabled.
    </div>
    <div
      v-else-if="allDisplayedWithoutData"
      class="data-table-panel__placeholder"
    >
      No output data available. Execute the workflow to view results.
    </div>

    <template v-else>
      <div
        v-if="displayedEntries.length > 5"
        class="data-table-panel__limit"
      >
        <Button
          size="small"
          text
          :label="showAll ? 'Show first 5' : `Show all (${displayedEntries.length})`"
          @click="showAll = !showAll"
        />
      </div>

      <section
        v-for="entry in visibleEntries"
        :key="entry.key"
        class="data-table-panel__node"
      >
        <header class="data-table-panel__header">
          <h3>{{ entry.label }}</h3>
          <span class="data-table-panel__id">{{ entry.subtitle }}</span>
        </header>
        <div
          v-if="entry.disabled"
          class="data-table-panel__disabled"
        >
          This node is disabled.
        </div>
        <NodeDataTable
          :node-id="entry.dataNodeId"
          :tool-name="entry.toolName"
          :workflow-name="workflowStore.currentName"
          :disabled="entry.disabled"
          :column-aliases="entry.columnAliases"
          :column-filter="entry.columnFilter"
        />
      </section>
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
