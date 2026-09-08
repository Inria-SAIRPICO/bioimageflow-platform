<script setup lang="ts">
import { computed } from 'vue'
import { useTableColumnWidths } from '@/composables/useTableColumnWidths'
import NodeDataColumnResizer from './NodeDataColumnResizer.vue'
import './nodeDataTable.css'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ImageCell from './ImageCell.vue'
import NodeDataActiveFilters from './NodeDataActiveFilters.vue'
import NodeDataColumnHeader from './NodeDataColumnHeader.vue'
import NodeDataPaginator from './NodeDataPaginator.vue'
import { useDataTableStore } from '@/stores/dataTable'
import type { DataTableFilter } from '@/stores/dataTable'
import { isImagePath } from '@/utils/imagePaths'

const props = defineProps<{
  nodeId: string
  toolName?: string | null
  workflowName?: string | null
  disabled?: boolean
  columnAliases?: Record<string, string>
  columnFilter?: string[]
}>()

const store = useDataTableStore()

const data = computed(() => store.getNodeData(props.nodeId))
const loading = computed(() => store.isLoading(props.nodeId))
const pending = computed(() => store.isPending(props.nodeId))
const error = computed(() => store.getError(props.nodeId))
const pageState = computed(() => store.getPageState(props.nodeId))

const rowModels = computed(() => {
  const response = data.value
  if (!response) return []
  return response.rows.map((row, i) => ({
    ...row,
    __absoluteRow: response.absolute_rows[i],
  }))
})

const visibleColumns = computed(() => {
  const response = data.value
  if (!response) return []
  if (!props.columnFilter || props.columnFilter.length === 0) return response.columns
  const allowed = new Set(props.columnFilter)
  return response.columns.filter((column) => allowed.has(column))
})

function isImageColumn(col: string): boolean {
  const type = data.value?.column_types[col]
  return type === 'ImageFile' || type === 'ImageShared' || type === 'MaskPath'
}

function isPathColumn(col: string): boolean {
  const type = data.value?.column_types[col]
  return type === 'Path' || type === 'ImageFile' || type === 'MaskPath'
}

function hasImageBehavior(col: string, value: unknown): boolean {
  return isImageColumn(col) || (data.value?.column_types[col] === 'Path' && isImagePath(value))
}

const columnLabels = computed(() => Object.fromEntries(
  visibleColumns.value.map(column => [column, displayColumnName(column)]),
))
const sizingColumns = computed(() => visibleColumns.value.map(id => ({
  id, label: displayColumnName(id), type: data.value?.column_types[id] ?? 'str',
})))
const sizingScope = computed(() => JSON.stringify([props.workflowName, 'node', props.nodeId]))
const { root, width, tableStyle, columnStyle, resize, autoSize, cancelResize } = useTableColumnWidths(sizingScope, sizingColumns, rowModels)

function setSort(column: string | null, order: 'asc' | 'desc') {
  void store.setSort(props.nodeId, column, order, {
    toolName: props.toolName,
    workflowName: props.workflowName,
  })
}

function setFilters(filters: DataTableFilter[]): void {
  void store.setFilters(props.nodeId, filters, {
    toolName: props.toolName,
    workflowName: props.workflowName,
  })
}

function displayColumnName(col: string): string {
  return props.columnAliases?.[col] ?? col
}

function downloadCsv() {
  void store.downloadCsv(props.nodeId, props.workflowName, props.columnFilter)
}

function onPageSize(pageSize: number): void {
  void store.setPageSize(props.nodeId, pageSize, {
    toolName: props.toolName,
    workflowName: props.workflowName,
  })
}

function onPage(page: number): void {
  void store.setPage(props.nodeId, page, {
    toolName: props.toolName,
    workflowName: props.workflowName,
  })
}

</script>

<template>
  <section
    ref="root"
    class="node-data-table"
    :class="{ 'node-data-table--disabled': disabled }"
    :data-testid="`node-data-table-${nodeId}`"
  >
    <div class="node-data-table__toolbar">
      <slot name="toolbar-actions" />
      <Button icon="pi pi-refresh" label="Reset column widths" size="small" text title="Size columns to headers and loaded values" @click="autoSize()" />
      <Button
        icon="pi pi-download"
        label="CSV"
        size="small"
        :data-testid="`download-csv-${nodeId}`"
        @click="downloadCsv"
      />
    </div>

    <div
      v-if="error && !data"
      class="node-data-table__message"
      :class="{ 'node-data-table__message--info': error.startsWith('No output data for node ') }"
    >
      {{ error }}
    </div>
    <div
      v-else-if="pending && !data"
      class="node-data-table__message"
    >
      Preparing output data...
    </div>
    <div
      v-else-if="loading && !data"
      class="node-data-table__message"
    >
      Loading output data...
    </div>
    <div
      v-else-if="!data"
      class="node-data-table__message"
    >
      No output data available.
    </div>
    <template v-else>
      <NodeDataActiveFilters
        :filters="pageState.filters"
        :labels="columnLabels"
        @change="setFilters"
      />
      <DataTable
        :value="rowModels"
        data-key="__absoluteRow"
        size="small"
        scrollable
        scroll-height="flex"
        :loading="loading"
        :table-style="tableStyle"
        class="node-data-table__grid node-data-sized-grid"
      >
        <Column
          v-for="column in sizingColumns"
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
            <div
              v-if="isImageColumn(column.id) || isPathColumn(column.id)"
              class="node-data-table__image-path"
            >
              <ImageCell
                :node-id="nodeId"
                :workflow-name="workflowName"
                :row="slotProps.data.__absoluteRow"
                :col="column.id"
                :value="String(slotProps.data[column.id] ?? '')"
                :show-path="isPathColumn(column.id)"
                :show-image-actions="hasImageBehavior(column.id, slotProps.data[column.id])"
                :thumbnail-enabled="hasImageBehavior(column.id, slotProps.data[column.id])"
              />
            </div>
            <span v-else class="node-data-cell-text" :title="String(slotProps.data[column.id] ?? '')">{{ slotProps.data[column.id] }}</span>
          </template>
        </Column>
      </DataTable>
      <NodeDataPaginator
        :page="pageState.page"
        :page-size="pageState.pageSize"
        :total-rows="data.total_rows"
        :unfiltered-total-rows="data.unfiltered_total_rows"
        @page="onPage"
        @page-size="onPageSize"
      />
    </template>
  </section>
</template>

<style scoped>
.node-data-table {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--bif-border-muted);
  padding-top: 0.5rem;
}

.node-data-table--disabled {
  opacity: 0.55;
}

.node-data-table__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-bottom: 0.25rem;
}

.node-data-table__message {
  color: var(--p-text-muted-color);
  padding: 1rem 0.5rem;
}

.node-data-table__message--info {
  background: var(--p-blue-50);
  color: var(--p-blue-800);
}

.node-data-table__grid {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
}

.node-data-table__image-path {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.node-data-table__image-path > * {
  min-width: 0;
}
</style>
