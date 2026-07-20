<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Paginator from 'primevue/paginator'
import ImageCell from './ImageCell.vue'
import { useDataTableStore } from '@/stores/dataTable'
import { isImagePath } from '@/utils/imagePaths'

const props = defineProps<{
  workflowId?: string | null
}>()

const store = useDataTableStore()
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

function toggleSort(columnId: string): void {
  const current = pageState.value
  const order = current.sortBy === columnId && current.sortOrder === 'asc' ? 'desc' : 'asc'
  void store.setProjectionSort(columnId, order)
}

function onPage(event: { page: number; rows: number }): void {
  void store.setProjectionPage(event.page, event.rows === pageState.value.pageSize ? undefined : event.rows)
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
        <Button
          icon="pi pi-download"
          label="CSV"
          size="small"
          data-testid="download-merged-csv"
          @click="store.downloadProjectionCsv()"
        />
      </div>
    </div>
    <DataTable
      :value="rowModels"
      size="small"
      scrollable
      scroll-height="360px"
      :loading="store.projectionLoading"
    >
      <Column
        v-for="column in data.columns"
        :key="column.id"
        :field="column.id"
      >
        <template #header>
          <button
            class="merged-data-table__sort"
            type="button"
            @click="toggleSort(column.id)"
          >
            <span>{{ column.label }}</span>
            <span class="merged-data-table__type">{{ column.type }}</span>
          </button>
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
    <Paginator
      :first="pageState.page * pageState.pageSize"
      :rows="pageState.pageSize"
      :total-records="data.total_rows"
      :rows-per-page-options="[25, 50, 100, 250]"
      @page="onPage"
    />
  </section>
</template>

<style scoped>
.merged-data-table {
  border-top: 1px solid var(--bif-border-muted);
  padding-top: 0.5rem;
}

.merged-data-table__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--p-text-muted-color);
  margin-bottom: 0.5rem;
}

.merged-data-table__toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.merged-data-table__sort {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
  font: inherit;
}

.merged-data-table__type {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
}
</style>
