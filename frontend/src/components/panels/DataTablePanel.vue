<script setup lang="ts">
import { computed, effectScope, onBeforeUnmount, ref, watch, type EffectScope } from 'vue'
import Button from 'primevue/button'
import NodeDataTable from './NodeDataTable.vue'
import { useGraphSync } from '@/composables/useGraphSync'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useDataTableStore } from '@/stores/dataTable'
import { useWorkflowStore } from '@/stores/workflow'
import type { NodeState } from '@/api/types'

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

const visibleNodeIds = computed(() => {
  if (displayedNodeIds.value.length > 5 && !showAll.value) {
    return displayedNodeIds.value.slice(0, 5)
  }
  return displayedNodeIds.value
})

const allTerminalDisabled = computed(() =>
  displayedNodeIds.value.length > 0 &&
  displayedNodeIds.value.every((id) => nodeById.value[id]?.enabled === false),
)

const allDisplayedWithoutData = computed(() =>
  displayedNodeIds.value.length > 0 &&
  displayedNodeIds.value.every((id) =>
    !dataTableStore.getNodeData(id) && !dataTableStore.isLoading(id),
  ),
)

function nodeLabel(nodeId: string): string {
  return nodeById.value[nodeId]?.name ?? nodeId
}

function toolName(nodeId: string): string | null {
  return nodeById.value[nodeId]?.tool_name ?? null
}

function fetchIfMissing(nodeId: string) {
  if (!dataTableStore.getNodeData(nodeId) && !dataTableStore.isLoading(nodeId)) {
    void dataTableStore.fetchNodeData(nodeId, {
      toolName: toolName(nodeId),
      workflowName: workflowStore.currentName,
    })
  }
}

let scope: EffectScope | null = null

watch(
  displayedNodeIds,
  (ids) => {
    scope?.stop()
    scope = effectScope()
    scope.run(() => {
      for (const nodeId of ids) {
        fetchIfMissing(nodeId)
        watch(
          () => executionStore.nodeStatuses[nodeId]?.status,
          (next, prev) => {
            if (prev !== 'executed' && next === 'executed') {
              void dataTableStore.fetchNodeData(nodeId, {
                toolName: toolName(nodeId),
                workflowName: workflowStore.currentName,
              })
            } else if (next === 'out_of_date' || next === 'unexecuted') {
              dataTableStore.clearCache(nodeId)
            }
          },
        )
      }
    })
  },
  { immediate: true },
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
        v-if="displayedNodeIds.length > 5"
        class="data-table-panel__limit"
      >
        <Button
          size="small"
          text
          :label="showAll ? 'Show first 5' : `Show all (${displayedNodeIds.length})`"
          @click="showAll = !showAll"
        />
      </div>

      <section
        v-for="nodeId in visibleNodeIds"
        :key="nodeId"
        class="data-table-panel__node"
      >
        <header class="data-table-panel__header">
          <h3>{{ nodeLabel(nodeId) }}</h3>
          <span class="data-table-panel__id">{{ nodeId }}</span>
        </header>
        <div
          v-if="nodeById[nodeId]?.enabled === false"
          class="data-table-panel__disabled"
        >
          This node is disabled.
        </div>
        <NodeDataTable
          :node-id="nodeId"
          :tool-name="toolName(nodeId)"
          :workflow-name="workflowStore.currentName"
          :disabled="nodeById[nodeId]?.enabled === false"
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
