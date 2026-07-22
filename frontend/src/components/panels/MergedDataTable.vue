<script setup lang="ts">
import { computed, ref } from 'vue'
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

const props = defineProps<{
  workflowId?: string | null
}>()

const store = useDataTableStore()
const data = computed(() => store.projection?.mode === 'merged' ? store.projection : null)
const pageState = computed(() => store.projectionPage)
const widthMode = ref<'auto' | 'fit'>('auto')
const tableRenderKey = ref(0)
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

const columnLabels = computed(() => Object.fromEntries(
  (data.value?.columns ?? []).map(column => [column.id, column.label]),
))
const tableStateKey = computed(() => {
  const signature = (data.value?.columns ?? [])
    .map(column => `${column.id}:${column.type}`)
    .join('|')
  return `bif-node-data-widths-v1:merged:${signature}`
})

function setSort(columnId: string | null, order: 'asc' | 'desc'): void {
  void store.setProjectionSort(columnId, order)
}

function setFilters(filters: DataTableFilter[]): void {
  void store.setProjectionFilters(filters)
}

function defaultColumnWidth(type: string): string {
  if (/^(bool|boolean)$/i.test(type)) return '96px'
  if (/^(u?int|float|double|number|decimal)/i.test(type)) return '120px'
  if (isTypedImage(type) || isPathType(type)) return '320px'
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
</script>

<template>
  <section
    v-if="data"
    class="merged-data-table"
    data-testid="merged-data-table"
  >
    <div class="merged-data-table__toolbar">
      <span>{{ data.sources.map((source) => source.label).join(' → ') }}</span>
      <div class="merged-data-table__toolbar-actions">
        <slot name="toolbar-actions" />
        <Button icon="pi pi-arrows-h" label="Fit" size="small" text title="Fit columns to panel" @click="widthMode = 'fit'" />
        <Button icon="pi pi-sparkles" label="Auto" size="small" text title="Use compact automatic widths" @click="autoSizeColumns" />
        <Button icon="pi pi-refresh" label="Reset" size="small" text title="Reset saved column widths" @click="resetColumnWidths" />
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
      :key="`${tableStateKey}:${tableRenderKey}`"
      :value="rowModels"
      data-key="__index"
      size="small"
      scrollable
      scroll-height="flex"
      :loading="store.projectionLoading"
      resizable-columns
      :column-resize-mode="widthMode === 'fit' ? 'fit' : 'expand'"
      state-storage="local"
      :state-key="tableStateKey"
      class="merged-data-table__grid"
      :class="{ 'merged-data-table__grid--fit': widthMode === 'fit' }"
    >
      <Column
        v-for="column in data.columns"
        :key="column.id"
        :field="column.id"
        :style="{ width: defaultColumnWidth(column.type), minWidth: '72px', maxWidth: '480px' }"
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
            :show-image-actions="hasImageBehavior(column.type, slotProps.data[column.id])"
            :thumbnail-enabled="hasImageBehavior(column.type, slotProps.data[column.id])"
          />
          <span v-else>{{ slotProps.data[column.id] }}</span>
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

.merged-data-table__grid :deep(.p-datatable-table) {
  width: max-content;
  min-width: 0;
}

.merged-data-table__grid--fit :deep(.p-datatable-table) {
  width: 100%;
  table-layout: fixed;
}
</style>
