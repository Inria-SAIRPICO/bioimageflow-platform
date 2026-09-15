<script setup lang="ts">
import { computed } from 'vue'
import { useTableColumnWidths } from '@/composables/useTableColumnWidths'
import NodeDataColumnResizer from './NodeDataColumnResizer.vue'
import './nodeDataTable.css'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import ImageCell from './ImageCell.vue'
import NodeDataActiveFilters from './NodeDataActiveFilters.vue'
import NodeDataColumnHeader from './NodeDataColumnHeader.vue'
import NodeDataPaginator from './NodeDataPaginator.vue'
import { useDataTableStore } from '@/stores/dataTable'
import type { DataTableFilter } from '@/stores/dataTable'
import { isImagePath } from '@/utils/imagePaths'
import { useResolvedOutputsStore } from '@/stores/resolvedOutputs'
import { useWorkflowStore } from '@/stores/workflow'

const props = defineProps<{
  workflowId?: string | null
}>()

const store = useDataTableStore()
const resolvedOutputs = useResolvedOutputsStore()
const workflowStore = useWorkflowStore()
const data = computed(() => store.projection?.mode === 'merged' ? store.projection : null)
const pageState = computed(() => store.projectionPage)
const rowModels = computed(() => (data.value?.rows ?? []).map((row) => ({
  ...row.values,
  __index: row.index,
  __sourceRows: row.source_rows,
})))

function isTypedImage(type: string): boolean {
  return type === 'ImageFile' || type === 'ImageShared' || type === 'MaskPath'
}

function isPathType(type: string): boolean {
  return type === 'Path' || type === 'ImageFile' || type === 'MaskPath'
}

function hasImageBehavior(type: string, value: unknown): boolean {
  return isTypedImage(type) || (type === 'Path' && isImagePath(value))
}

function hasExplicitNapariViewer(nodeId: string, column: string): boolean {
  const field = resolvedOutputs.resolvedOutputsByNodeId[nodeId]?.columns[column]
  return Boolean(
    field
    && typeof field === 'object'
    && 'viewer' in field
    && (field as { viewer?: { napari?: unknown } | null }).viewer?.napari,
  )
}

function sourceIdentity(nodeId: string) {
  return data.value?.sources.find(source => source.node_id === nodeId)?.result_identity ?? null
}

const identityGeneration = computed(() => props.workflowId
  ? workflowStore.workflowServerIdentityGeneration(props.workflowId)
  : null)

const columnLabels = computed(() => Object.fromEntries(
  (data.value?.columns ?? []).map(column => [column.id, column.label]),
))
const sizingColumns = computed(() => data.value?.columns ?? [])
const sizingScope = computed(() => JSON.stringify([props.workflowId, 'merged', (data.value?.sources ?? []).map(source => source.node_id).sort()]))
const { root, width, tableStyle, columnStyle, resize, autoSize, cancelResize } = useTableColumnWidths(sizingScope, sizingColumns, rowModels)

function setSort(columnId: string | null, order: 'asc' | 'desc'): void {
  void store.setProjectionSort(columnId, order)
}

function setFilters(filters: DataTableFilter[]): void {
  void store.setProjectionFilters(filters)
}

</script>

<template>
  <section
    ref="root"
    v-if="data"
    class="merged-data-table"
    data-testid="merged-data-table"
  >
    <div class="merged-data-table__toolbar">
      <span>{{ data.sources.map((source) => source.label).join(' → ') }}</span>
      <div class="merged-data-table__toolbar-actions">
        <slot name="toolbar-actions" />
        <Button icon="pi pi-refresh" label="Reset column widths" size="small" text title="Size columns to headers and loaded values" @click="autoSize()" />
        <Button
          icon="pi pi-download"
          label="CSV"
          size="small"
          data-testid="download-merged-csv"
          @click="store.downloadProjectionCsv()"
        />
      </div>
    </div>
    <NodeDataActiveFilters
      :filters="pageState.filters"
      :labels="columnLabels"
      @change="setFilters"
    />
    <DataTable
      :value="rowModels"
      data-key="__index"
      size="small"
      scrollable
      scroll-height="flex"
      :loading="store.projectionLoading"
      :table-style="tableStyle"
      class="merged-data-table__grid node-data-sized-grid"
    >
      <Column
        v-for="column in data.columns"
        :key="column.id"
        :field="column.id"
        :style="columnStyle(column)"
      >
        <template #header>
          <NodeDataColumnHeader
            :column="column.id"
            :label="column.label"
            :type="column.type"
            :page-state="pageState"
            @sort="setSort"
            @filters="setFilters"
          />
          <NodeDataColumnResizer :label="column.label" :get-width="() => width(column)"
            @resize="(value, commit) => resize(column, value, commit)"
            @cancel="cancelResize" @autosize="autoSize(column)" />
        </template>
        <template #body="slotProps">
          <ImageCell
            v-if="isTypedImage(column.type) || isPathType(column.type)"
            :node-id="column.source_node_id"
            :workflow-name="props.workflowId"
            :row="slotProps.data.__sourceRows[column.source_node_id]"
            :col="column.source_column"
            :value="String(slotProps.data[column.id] ?? '')"
            :show-path="isPathType(column.type)"
            :show-image-actions="hasImageBehavior(column.type, slotProps.data[column.id]) || hasExplicitNapariViewer(column.source_node_id, column.source_column)"
            :thumbnail-enabled="hasImageBehavior(column.type, slotProps.data[column.id])"
            :explicit-napari-viewer="hasExplicitNapariViewer(column.source_node_id, column.source_column)"
            :result-identity="sourceIdentity(column.source_node_id)"
            :identity-generation="identityGeneration"
            :node-path="column.source_node_id.split('/')"
            :output-key="column.source_column"
            :output-name="column.label"
          />
          <span v-else class="node-data-cell-text" :title="String(slotProps.data[column.id] ?? '')">{{ slotProps.data[column.id] }}</span>
        </template>
      </Column>
    </DataTable>
    <NodeDataPaginator
      :page="pageState.page"
      :page-size="pageState.pageSize"
      :total-rows="data.total_rows"
      :unfiltered-total-rows="data.unfiltered_total_rows"
      @page="store.setProjectionPage"
      @page-size="pageSize => store.setProjectionPage(0, pageSize)"
    />
  </section>
</template>

<style scoped>
.merged-data-table {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--bif-border-muted);
  padding-top: 0.5rem;
}

.merged-data-table__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  color: var(--p-text-muted-color);
  margin-bottom: 0.5rem;
}

.merged-data-table__toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.merged-data-table__grid {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
}

</style>
