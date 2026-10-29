<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import type { ResultArtifactIdentity } from '@/api/types'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{
  nodeId: string
  toolName?: string | null
  workflowName?: string | null
  disabled?: boolean
  columnAliases?: Record<string, string>
  columnFilter?: string[]
  resultIdentity?: ResultArtifactIdentity | null
}>()

const store = useDataTableStore()
const workflowStore = useWorkflowStore()
const settings = useSettingsStore()

const data = computed(() => store.getNodeData(props.nodeId))
const loading = computed(() => store.isLoading(props.nodeId))
const pending = computed(() => store.isPending(props.nodeId))
const error = computed(() => store.getError(props.nodeId))
const pageState = computed(() => store.getPageState(props.nodeId))

const entries = computed(() => store.tableEntries(props.nodeId))
const rowModels = computed(() => entries.value.slice(0, 50).map(entry => entry.row))
const continuous = computed(() => store.isContinuous(props.nodeId))
const windowErrors = computed(() => store.continuousErrors(props.nodeId))
const resetKey = computed(() => JSON.stringify([store.inspectionKey, props.nodeId, store.browsingMode,
  pageState.value.page, pageState.value.sortBy, pageState.value.sortOrder, pageState.value.filters]))
function rowHeight(row: Record<string, unknown>): number {
  return visibleColumns.value.some(column => hasImageBehavior(column, row[column])) ? 110 : 40
}
function range(start: number, end: number): void { store.loadTableRange(start, end, props.nodeId) }
const visible = ref(false)
let observer: IntersectionObserver | null = null
function loadVisible(force = false): void {
  if (visible.value && (force || !data.value) && (force || (!loading.value && !error.value))) {
    void store.fetchNodeData(props.nodeId, { workflowName: props.workflowName, toolName: props.toolName,
      resultIdentity: props.resultIdentity ?? data.value?.source_identity, page: 0, pageSize: settings.settings?.node_data_page_size ?? 250 })
  }
}
watch(visible, () => loadVisible())
watch([() => props.nodeId, () => props.workflowName, () => props.resultIdentity], () => loadVisible(true))
watch(() => store.inspectionKey, () => {
  const needsWindow = store.isContinuous(props.nodeId) && (data.value?.total_rows ?? 0) > 0
    && store.tableEntries(props.nodeId).length === 0
  loadVisible(needsWindow || Boolean(data.value && !data.value.source_identity))
})
watch(() => store.browsingMode, () => loadVisible(true))
watch(() => settings.settings?.node_data_page_size, () => { if (store.browsingMode === 'paginated') loadVisible(true) })
onMounted(() => {
  if (!root.value) return
  if (typeof IntersectionObserver === 'undefined') visible.value = true
  else {
    observer = new IntersectionObserver(items => { visible.value = items.some(item => item.isIntersecting) })
    observer.observe(root.value)
  }
})
onBeforeUnmount(() => observer?.disconnect())

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
  return isImageColumn(col)
    || (data.value?.column_types[col] === 'Path' && isImagePath(value))
}

function hasRetainedNapariViewer(col: string): boolean {
  return data.value?.identity_status === 'captured'
    && Boolean(data.value.column_viewers?.[col]?.napari)
}

const identityGeneration = computed(() => props.workflowName
  ? workflowStore.workflowServerIdentityGeneration(props.workflowName)
  : null)

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
      <Button icon="pi pi-refresh" aria-label="Reset column widths" size="small" text title="Size columns to headers and loaded values" @click="autoSize()" />
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
      <div v-if="store.browsingMode === 'continuous' && !continuous && !data.source_identity" class="node-data-table__message">
        Continuous scrolling requires a captured result. This output uses pagination.
      </div>
      <div v-for="message in windowErrors" :key="message" class="node-data-table__message" role="alert">
        {{ message }} <Button label="Retry rows" text @click="store.retryContinuous(nodeId)" />
      </div>
      <VirtualDataTable :columns="sizingColumns" :entries="entries"
        :total-rows="continuous ? data.total_rows : data.rows.length" :row-height="rowHeight"
        :estimated-row-height="sizingColumns.some(column => isImageColumn(column.id)) ? 110 : 40"
        :column-style="columnStyle" :table-style="tableStyle" :reset-key="resetKey" :loading="loading"
        class="node-data-table__grid" @range="range">
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
            <div
              v-if="isImageColumn(column.id) || isPathColumn(column.id) || hasRetainedNapariViewer(column.id)"
              class="node-data-table__image-path"
            >
              <ImageCell
                :node-id="nodeId"
                :inspection-key="store.inspectionKey"
                :workflow-name="workflowName"
                :row="row.__absoluteRow"
                :col="column.id"
                :value="String(row[column.id] ?? '')"
                :show-path="isPathColumn(column.id)"
                :show-image-actions="hasImageBehavior(column.id, row[column.id])"
                :thumbnail-enabled="isImageColumn(column.id) || (data.column_types[column.id] === 'Path' && isImagePath(row[column.id]))"
                :explicit-napari-viewer="hasRetainedNapariViewer(column.id)"
                :result-identity="data.source_identity"
                :identity-generation="identityGeneration"
                :node-path="nodeId.split('/')"
                :output-key="column.id"
                :output-name="displayColumnName(column.id)"
              />
            </div>
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
  padding-top: 0;
}

.node-data-table--disabled {
  opacity: 0.55;
}

.node-data-table__toolbar {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-bottom: 0;
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
  min-height: 89px;
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
