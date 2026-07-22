<script setup lang="ts">
import { computed, ref } from 'vue'
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
const widthMode = ref<'auto' | 'fit'>('auto')
const tableRenderKey = ref(0)

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
const tableStateKey = computed(() => {
  const signature = visibleColumns.value
    .map(column => `${column}:${data.value?.column_types[column] ?? 'str'}`)
    .join('|')
  return `bif-node-data-widths-v1:${props.nodeId}:${signature}`
})

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

function defaultColumnWidth(column: string): string {
  const type = data.value?.column_types[column] ?? 'str'
  if (/^(bool|boolean)$/i.test(type)) return '96px'
  if (/^(u?int|float|double|number|decimal)/i.test(type)) return '120px'
  if (isImageColumn(column) || isPathColumn(column)) return '320px'
  return '180px'
}

function resetColumnWidths(): void {
  window.localStorage.removeItem(tableStateKey.value)
  widthMode.value = 'auto'
  tableRenderKey.value += 1
}

function autoSizeColumns(): void {
  window.localStorage.removeItem(tableStateKey.value)
  widthMode.value = 'auto'
  tableRenderKey.value += 1
}

function fitColumns(): void {
  widthMode.value = 'fit'
}
</script>

<template>
  <section
    class="node-data-table"
    :class="{ 'node-data-table--disabled': disabled }"
    :data-testid="`node-data-table-${nodeId}`"
  >
    <div class="node-data-table__toolbar">
      <slot name="toolbar-actions" />
      <Button icon="pi pi-arrows-h" label="Fit" size="small" text title="Fit columns to panel" @click="fitColumns" />
      <Button icon="pi pi-sparkles" label="Auto" size="small" text title="Use compact automatic widths" @click="autoSizeColumns" />
      <Button icon="pi pi-refresh" label="Reset" size="small" text title="Reset saved column widths" @click="resetColumnWidths" />
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
        :key="`${tableStateKey}:${tableRenderKey}`"
        :value="rowModels"
        data-key="__absoluteRow"
        size="small"
        scrollable
        scroll-height="flex"
        :loading="loading"
        resizable-columns
        :column-resize-mode="widthMode === 'fit' ? 'fit' : 'expand'"
        state-storage="local"
        :state-key="tableStateKey"
        class="node-data-table__grid"
        :class="{ 'node-data-table__grid--fit': widthMode === 'fit' }"
      >
        <Column
          v-for="col in visibleColumns"
          :key="col"
          :field="col"
          :style="{ width: defaultColumnWidth(col), minWidth: '72px', maxWidth: '480px' }"
        >
          <template #header>
            <NodeDataColumnHeader
              :column="col"
              :label="displayColumnName(col)"
              :type="data.column_types[col] ?? 'str'"
              :page-state="pageState"
              @sort="setSort"
              @filters="setFilters"
            />
          </template>
          <template #body="slotProps">
            <div
              v-if="isImageColumn(col) || isPathColumn(col)"
              class="node-data-table__image-path"
            >
              <ImageCell
                :node-id="nodeId"
                :workflow-name="workflowName"
                :row="slotProps.data.__absoluteRow"
                :col="col"
                :value="String(slotProps.data[col] ?? '')"
                :show-path="isPathColumn(col)"
                :show-image-actions="hasImageBehavior(col, slotProps.data[col])"
                :thumbnail-enabled="hasImageBehavior(col, slotProps.data[col])"
              />
            </div>
            <span v-else>{{ slotProps.data[col] }}</span>
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

.node-data-table__grid {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
}

.node-data-table__grid :deep(.p-datatable-table) {
  width: max-content;
  min-width: 0;
}

.node-data-table__grid--fit :deep(.p-datatable-table) {
  width: 100%;
  table-layout: fixed;
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
