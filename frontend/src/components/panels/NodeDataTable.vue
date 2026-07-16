<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Paginator from 'primevue/paginator'
import ImageCell from './ImageCell.vue'
import { useDataTableStore } from '@/stores/dataTable'

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

function toggleSort(col: string) {
  const current = pageState.value
  const order = current.sortBy === col && current.sortOrder === 'asc' ? 'desc' : 'asc'
  void store.setSort(props.nodeId, col, order, {
    toolName: props.toolName,
    workflowName: props.workflowName,
  })
}

function displayColumnName(col: string): string {
  return props.columnAliases?.[col] ?? col
}

function downloadCsv() {
  store.downloadCsv(props.nodeId, props.workflowName, props.columnFilter)
}

function onPage(event: { page: number; rows: number }) {
  if (event.rows !== pageState.value.pageSize) {
    void store.setPageSize(props.nodeId, event.rows, {
      toolName: props.toolName,
      workflowName: props.workflowName,
    })
    return
  }
  void store.setPage(props.nodeId, event.page, {
    toolName: props.toolName,
    workflowName: props.workflowName,
  })
}
</script>

<template>
  <section
    class="node-data-table"
    :class="{ 'node-data-table--disabled': disabled }"
    :data-testid="`node-data-table-${nodeId}`"
  >
    <div class="node-data-table__toolbar">
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
      <DataTable
        :value="rowModels"
        size="small"
        scrollable
        scroll-height="260px"
        :loading="loading"
      >
        <Column
          v-for="col in visibleColumns"
          :key="col"
          :field="col"
        >
          <template #header>
            <button
              class="node-data-table__sort"
              type="button"
              @click="toggleSort(col)"
            >
              <span>{{ displayColumnName(col) }}</span>
              <span class="node-data-table__type">{{ data.column_types[col] ?? 'str' }}</span>
            </button>
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
                :show-image-actions="isImageColumn(col)"
                :hide-thumbnail-fallback="!isImageColumn(col)"
              />
            </div>
            <span v-else>{{ slotProps.data[col] }}</span>
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
    </template>
  </section>
</template>

<style scoped>
.node-data-table {
  border-top: 1px solid var(--bif-border-muted);
  padding-top: 0.5rem;
}

.node-data-table--disabled {
  opacity: 0.55;
}

.node-data-table__toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.25rem;
}

.node-data-table__message {
  color: var(--p-text-muted-color);
  padding: 1rem 0.5rem;
}

.node-data-table__sort {
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

.node-data-table__type {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
}

.node-data-table__image-path {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
</style>
