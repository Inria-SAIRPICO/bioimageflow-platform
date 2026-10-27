<script setup lang="ts">
import { computed } from 'vue'
import { useTableColumnWidths } from '@/composables/useTableColumnWidths'
import NodeDataColumnResizer from './NodeDataColumnResizer.vue'
import './nodeDataTable.css'
import Button from 'primevue/button'
import VirtualDataTable from './VirtualDataTable.vue'
import ImageCell from './ImageCell.vue'
import NodeDataActiveFilters from './NodeDataActiveFilters.vue'
import NodeDataColumnHeader from './NodeDataColumnHeader.vue'
import NodeDataPaginator from './NodeDataPaginator.vue'
import { useDataTableStore } from '@/stores/dataTable'
import type { DataTableFilter } from '@/stores/dataTable'
import { isImagePath } from '@/utils/imagePaths'
import { useWorkflowStore } from '@/stores/workflow'

const props = defineProps<{
  workflowId?: string | null
}>()

const store = useDataTableStore()
const workflowStore = useWorkflowStore()
const data = computed(() => store.projection?.mode === 'merged' ? store.projection : null)
const pageState = computed(() => store.projectionPage)
const entries = computed(() => store.tableEntries())
const rowModels = computed(() => entries.value.slice(0, 50).map(entry => entry.row))
const continuous = computed(() => store.isContinuous())
const windowErrors = computed(() => store.continuousErrors())
const resetKey = computed(() => JSON.stringify([store.inspectionKey, store.browsingMode,
  pageState.value.page, pageState.value.sortBy, pageState.value.sortOrder, pageState.value.filters]))
function rowHeight(row: Record<string, unknown>): number {
  return (data.value?.columns ?? []).some(column => hasImageBehavior(column.type, row[column.id])) ? 110 : 40
}
function range(start: number, end: number): void { store.loadTableRange(start, end) }

function isTypedImage(type: string): boolean {
  return type === 'ImageFile' || type === 'ImageShared' || type === 'MaskPath'
}

function isPathType(type: string): boolean {
  return type === 'Path' || type === 'ImageFile' || type === 'MaskPath'
}

function hasImageBehavior(type: string, value: unknown): boolean {
  return isTypedImage(type) || (type === 'Path' && isImagePath(value))
}

function hasRetainedNapariViewer(column: { viewer_status?: string; viewer?: { napari?: unknown } | null }): boolean {
  return column.viewer_status === 'captured' && Boolean(column.viewer?.napari)
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
      <span class="merged-data-table__caption" :title="data.sources.map(source => source.label).join(' → ')">{{ data.sources.map((source) => source.label).join(' → ') }}</span>
      <div class="merged-data-table__toolbar-actions">
        <slot name="toolbar-actions" />
        <Button icon="pi pi-refresh" aria-label="Reset column widths" size="small" text title="Size columns to headers and loaded values" @click="autoSize()" />
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
    <div v-if="store.browsingMode === 'continuous' && !continuous" class="node-data-table__message">
      Continuous scrolling requires captured results. These outputs use pagination.
    </div>
    <div v-for="message in windowErrors" :key="message" class="node-data-table__message" role="alert">
      {{ message }} <Button label="Retry rows" text @click="store.retryContinuous()" />
    </div>
    <VirtualDataTable :columns="data.columns" :entries="entries"
      :total-rows="continuous ? data.total_rows : data.rows.length" :row-height="rowHeight"
      :estimated-row-height="data.columns.some(column => isTypedImage(column.type)) ? 110 : 40"
      :column-style="columnStyle" :table-style="tableStyle" :reset-key="resetKey" :loading="store.projectionLoading"
      class="merged-data-table__grid" @range="range">
      <template #header="{ column }">
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
            @nudge="delta => resize(column, width(column) + delta, true)"
            @cancel="cancelResize" @autosize="autoSize(column)" />

      </template>
      <template #body="{ row, column }">
          <ImageCell
            v-if="isTypedImage(column.type) || isPathType(column.type) || hasRetainedNapariViewer(column)"
            :node-id="column.source_node_id"
            :inspection-key="store.inspectionKey"
            :workflow-name="props.workflowId"
            :row="row.__sourceRows[column.source_node_id]"
            :col="column.source_column"
            :value="String(row[column.id] ?? '')"
            :show-path="isPathType(column.type)"
            :show-image-actions="hasImageBehavior(column.type, row[column.id])"
            :thumbnail-enabled="hasImageBehavior(column.type, row[column.id])"
            :explicit-napari-viewer="hasRetainedNapariViewer(column)"
            :result-identity="sourceIdentity(column.source_node_id)"
            :identity-generation="identityGeneration"
            :node-path="column.source_node_id.split('/')"
            :output-key="column.source_column"
            :output-name="column.label"
          />
          <span v-else class="node-data-cell-text" :title="String(row[column.id] ?? '')">{{ row[column.id] }}</span>

      </template>
    </VirtualDataTable>
    <div v-if="continuous" class="node-data-table__message" data-testid="continuous-row-count">{{ data.total_rows }} rows · Continuous scrolling</div>
    <NodeDataPaginator
      v-if="!continuous"
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
  padding-top: 0;
}

.merged-data-table__toolbar {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: space-between;
  color: var(--p-text-muted-color);
  margin-bottom: 0;
}

.merged-data-table__caption { flex: 1 1 0; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }

.merged-data-table__toolbar-actions {
  display: flex;
  flex-wrap: nowrap;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.5rem;
}

.merged-data-table__grid {
  flex: 1 1 auto;
  min-height: 89px;
  min-width: 0;
}

</style>
