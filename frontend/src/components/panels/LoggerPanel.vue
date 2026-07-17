<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import ToggleButton from 'primevue/togglebutton'
import { useLoggerStore, ALL_LEVELS, type LogEntry } from '@/stores/logger'
import { useUIStore } from '@/stores/ui'

interface NodeOption {
  label: string
  value: string | null
}

type ResizableLogColumn = 'timestamp' | 'level' | 'node'

interface ColumnResizeState {
  column: ResizableLogColumn
  pointerId: number
  startX: number
  startWidth: number
}

const MIN_COLUMN_WIDTHS: Record<ResizableLogColumn, number> = {
  timestamp: 88,
  level: 64,
  node: 80,
}
const MAX_COLUMN_WIDTH = 640

const logger = useLoggerStore()
const ui = useUIStore()

const listEl = ref<HTMLElement | null>(null)
const autoScope = ref(true)
const autoScopedNodeId = ref<string | null>(null)
const manualNodeFilter = ref(false)
const searchDraft = ref(logger.filter.searchText)
const columnWidths = ref<Record<ResizableLogColumn, number>>({
  timestamp: 120,
  level: 80,
  node: 192,
})
const columnResize = ref<ColumnResizeState | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const logGridStyle = computed(() => ({
  gridTemplateColumns: `${columnWidths.value.timestamp}px ${columnWidths.value.level}px ${columnWidths.value.node}px minmax(0, 1fr)`,
}))

const selectedNodeId = computed(() =>
  ui.selectedNodeIds.length === 1 ? ui.selectedNodeIds[0] : null,
)

const graphNodeLabels = computed(() => {
  const labels = new Map<string, string>()
  for (const node of ui.graphNodes) {
    if (node?.id) labels.set(node.id, node.data?.name ?? node.id)
  }
  return labels
})

const nodeOptions = computed<NodeOption[]>(() => {
  const options: NodeOption[] = [{ label: 'All nodes', value: null }]
  const graphOptions = ui.graphNodes
    .filter((node) => typeof node?.id === 'string')
    .map((node) => ({
      label: node.data?.name ?? node.id,
      value: node.id as string,
    }))
    .sort((a, b) => a.label.localeCompare(b.label))

  const graphIds = new Set(graphOptions.map((option) => option.value))
  const orphanOptions = Array.from(
    new Set(
      logger.entries
        .map((entry) => entry.nodeId)
        .filter((nodeId): nodeId is string => nodeId !== null && !graphIds.has(nodeId)),
    ),
  )
    .sort((a, b) => a.localeCompare(b))
    .map((nodeId) => ({ label: nodeId, value: nodeId }))

  return [...options, ...graphOptions, ...orphanOptions]
})

const visibleEntries = computed(() => logger.filteredEntries)

function applyNodeFilter(nodeId: string | null, source: 'manual' | 'auto') {
  logger.setFilter({ nodeId })
  if (source === 'manual') {
    manualNodeFilter.value = nodeId !== null
    autoScopedNodeId.value = null
  } else {
    autoScopedNodeId.value = nodeId
  }
}

function syncAutoScope() {
  if (!autoScope.value || manualNodeFilter.value) return
  const selected = selectedNodeId.value

  if (autoScopedNodeId.value !== null) {
    if (selected === autoScopedNodeId.value) return
    applyNodeFilter(selected, 'auto')
    return
  }

  if (selected !== null && logger.filter.nodeId === null) {
    applyNodeFilter(selected, 'auto')
  }
}

function onNodeFilterChange(nodeId: string | null) {
  applyNodeFilter(nodeId, 'manual')
  if (nodeId === null) syncAutoScope()
}

function toggleAutoScope() {
  autoScope.value = !autoScope.value
  if (!autoScope.value && autoScopedNodeId.value !== null) {
    applyNodeFilter(null, 'auto')
    autoScopedNodeId.value = null
  } else {
    syncAutoScope()
  }
}

function onSearchInput(value: string | undefined) {
  searchDraft.value = value ?? ''
  if (searchTimer !== null) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    logger.setFilter({ searchText: searchDraft.value })
  }, 300)
}

function clearSearch() {
  if (searchTimer !== null) clearTimeout(searchTimer)
  searchDraft.value = ''
  logger.setFilter({ searchText: '' })
}

function clearFilters() {
  logger.setFilter({
    levels: new Set(ALL_LEVELS),
    nodeId: null,
    searchText: '',
  })
  searchDraft.value = ''
  manualNodeFilter.value = false
  autoScopedNodeId.value = null
  syncAutoScope()
}

function formatTimestamp(seconds: number): string {
  return new Date(seconds * 1000).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  } as Intl.DateTimeFormatOptions)
}

function normalizedLevel(entry: LogEntry): string {
  return entry.level.toUpperCase()
}

function levelShort(level: string): string {
  return { DEBUG: 'DBG', INFO: 'INF', WARNING: 'WRN', ERROR: 'ERR' }[level] ?? level
}

function rowClass(entry: LogEntry): string {
  return `log-entry--${normalizedLevel(entry).toLowerCase()}`
}

function nodeLabel(entry: LogEntry): string {
  if (entry.nodeId === null) return ''
  if (entry.workflowId === null || entry.workflowId !== ui.activeWorkflowId) {
    return entry.nodeId
  }
  return graphNodeLabels.value.get(entry.nodeId) ?? entry.nodeId
}

function setColumnWidth(column: ResizableLogColumn, width: number) {
  columnWidths.value[column] = Math.min(
    MAX_COLUMN_WIDTH,
    Math.max(MIN_COLUMN_WIDTHS[column], Math.round(width)),
  )
}

function startColumnResize(event: PointerEvent, column: ResizableLogColumn) {
  event.preventDefault()
  const handle = event.currentTarget as HTMLElement
  handle.setPointerCapture?.(event.pointerId)
  columnResize.value = {
    column,
    pointerId: event.pointerId,
    startX: event.clientX,
    startWidth: columnWidths.value[column],
  }
}

function resizeColumn(event: PointerEvent) {
  const resize = columnResize.value
  if (resize === null || resize.pointerId !== event.pointerId) return
  setColumnWidth(resize.column, resize.startWidth + event.clientX - resize.startX)
}

function stopColumnResize(event: PointerEvent) {
  if (columnResize.value?.pointerId !== event.pointerId) return
  const handle = event.currentTarget as HTMLElement
  if (handle.hasPointerCapture?.(event.pointerId)) {
    handle.releasePointerCapture(event.pointerId)
  }
  columnResize.value = null
}

function resizeColumnWithKeyboard(event: KeyboardEvent, column: ResizableLogColumn) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  const direction = event.key === 'ArrowLeft' ? -1 : 1
  const step = event.shiftKey ? 32 : 8
  setColumnWidth(column, columnWidths.value[column] + direction * step)
}

function isAtBottom(el: HTMLElement): boolean {
  return el.scrollTop + el.clientHeight >= el.scrollHeight - 5
}

function onListScroll() {
  const el = listEl.value
  if (!el) return
  logger.setAutoScroll(isAtBottom(el))
}

async function scrollToBottom() {
  await nextTick()
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
}

watch([selectedNodeId, autoScope], syncAutoScope, { immediate: true })

watch(
  () => logger.filteredEntries.length,
  () => {
    if (logger.autoScroll) void scrollToBottom()
  },
)
</script>

<template>
  <section class="logger-panel" data-testid="panel-logger" aria-label="Logger">
    <header class="logger-panel__toolbar">
      <div class="logger-panel__levels" aria-label="Log levels">
        <ToggleButton
          v-for="level in ALL_LEVELS"
          :key="level"
          :model-value="logger.filter.levels.has(level)"
          :on-label="level"
          :off-label="level"
          size="small"
          :class="`logger-panel__level-toggle logger-panel__level-toggle--${level.toLowerCase()}`"
          :data-testid="`log-level-${level}`"
          @update:model-value="logger.toggleLevel(level)"
        />
      </div>

      <Select
        :model-value="logger.filter.nodeId"
        :options="nodeOptions"
        option-label="label"
        option-value="value"
        class="logger-panel__node-filter"
        data-testid="log-node-filter"
        @update:model-value="onNodeFilterChange($event as string | null)"
      />

      <Button
        :severity="autoScope ? undefined : 'secondary'"
        :outlined="!autoScope"
        :class="{
          'logger-panel__auto-scope--active': autoScope,
          'logger-panel__auto-scope--inactive': !autoScope,
        }"
        text
        aria-label="Auto-scope to selected node"
        title="Auto-scope to selected node"
        data-testid="log-auto-scope"
        @click="toggleAutoScope"
      >
        <template #icon>
          <span
            :class="[
              'pi',
              autoScope ? 'pi-filter' : 'pi-filter-slash',
              'logger-panel__auto-scope-icon',
              autoScope
                ? 'logger-panel__auto-scope-icon--active'
                : 'logger-panel__auto-scope-icon--inactive',
            ]"
            aria-hidden="true"
          />
        </template>
      </Button>

      <span class="logger-panel__search-wrap">
        <InputText
          :model-value="searchDraft"
          placeholder="Search logs..."
          class="logger-panel__search"
          data-testid="log-search"
          @update:model-value="(value) => onSearchInput(String(value ?? ''))"
        />
        <Button
          v-if="searchDraft"
          icon="pi pi-times"
          text
          aria-label="Clear search"
          title="Clear search"
          data-testid="log-search-clear"
          @click="clearSearch"
        />
      </span>

      <Button
        :icon="logger.autoScroll ? 'pi pi-arrow-down' : 'pi pi-pause'"
        :severity="logger.autoScroll ? undefined : 'secondary'"
        text
        aria-label="Auto-scroll"
        title="Auto-scroll"
        data-testid="log-auto-scroll"
        @click="logger.setAutoScroll(!logger.autoScroll)"
      />

      <Button
        icon="pi pi-filter-slash"
        aria-label="Clear filters"
        title="Clear filters"
        text
        data-testid="log-clear-filters"
        @click="clearFilters"
      />
      <Button
        icon="pi pi-trash"
        aria-label="Clear logs"
        title="Clear logs"
        text
        severity="danger"
        data-testid="log-clear"
        @click="logger.clearEntries()"
      />
    </header>

    <div
      ref="listEl"
      class="logger-panel__list"
      data-testid="log-list"
      role="table"
      aria-label="Log entries"
      @scroll="onListScroll"
    >
      <div
        class="logger-panel__header logger-panel__grid"
        data-testid="log-header"
        role="row"
        :style="logGridStyle"
      >
        <div class="logger-panel__column-header" role="columnheader">
          Timestamp
          <button
            type="button"
            class="logger-panel__resize-handle"
            :class="{ 'logger-panel__resize-handle--active': columnResize?.column === 'timestamp' }"
            role="separator"
            aria-label="Resize Timestamp column"
            aria-orientation="vertical"
            :aria-valuemin="MIN_COLUMN_WIDTHS.timestamp"
            :aria-valuemax="MAX_COLUMN_WIDTH"
            :aria-valuenow="columnWidths.timestamp"
            @pointerdown="startColumnResize($event, 'timestamp')"
            @pointermove="resizeColumn"
            @pointerup="stopColumnResize"
            @pointercancel="stopColumnResize"
            @keydown="resizeColumnWithKeyboard($event, 'timestamp')"
          />
        </div>
        <div class="logger-panel__column-header" role="columnheader">
          Level
          <button
            type="button"
            class="logger-panel__resize-handle"
            :class="{ 'logger-panel__resize-handle--active': columnResize?.column === 'level' }"
            role="separator"
            aria-label="Resize Level column"
            aria-orientation="vertical"
            :aria-valuemin="MIN_COLUMN_WIDTHS.level"
            :aria-valuemax="MAX_COLUMN_WIDTH"
            :aria-valuenow="columnWidths.level"
            @pointerdown="startColumnResize($event, 'level')"
            @pointermove="resizeColumn"
            @pointerup="stopColumnResize"
            @pointercancel="stopColumnResize"
            @keydown="resizeColumnWithKeyboard($event, 'level')"
          />
        </div>
        <div class="logger-panel__column-header" role="columnheader">
          Node
          <button
            type="button"
            class="logger-panel__resize-handle"
            :class="{ 'logger-panel__resize-handle--active': columnResize?.column === 'node' }"
            role="separator"
            aria-label="Resize Node column"
            aria-orientation="vertical"
            :aria-valuemin="MIN_COLUMN_WIDTHS.node"
            :aria-valuemax="MAX_COLUMN_WIDTH"
            :aria-valuenow="columnWidths.node"
            @pointerdown="startColumnResize($event, 'node')"
            @pointermove="resizeColumn"
            @pointerup="stopColumnResize"
            @pointercancel="stopColumnResize"
            @keydown="resizeColumnWithKeyboard($event, 'node')"
          />
        </div>
        <div class="logger-panel__column-header" role="columnheader">Message</div>
      </div>
      <div v-if="visibleEntries.length === 0" class="logger-panel__empty" data-testid="log-empty">
        No log messages
      </div>
      <div
        v-for="(entry, index) in visibleEntries"
        :key="`${entry.timestamp}-${index}`"
        :class="['logger-panel__row', 'logger-panel__grid', rowClass(entry)]"
        data-testid="log-entry"
        role="row"
        :style="logGridStyle"
      >
        <span class="logger-panel__time" data-testid="log-timestamp" role="cell">
          {{ formatTimestamp(entry.timestamp) }}
        </span>
        <span
          :class="['logger-panel__level-badge', `logger-panel__level-badge--${normalizedLevel(entry).toLowerCase()}`]"
          data-testid="log-level-badge"
          role="cell"
        >
          {{ levelShort(normalizedLevel(entry)) }}
        </span>
        <span
          v-if="entry.nodeId !== null"
          class="logger-panel__node"
          data-testid="log-node-name"
          role="cell"
        >
          {{ nodeLabel(entry) }}
        </span>
        <span v-else class="logger-panel__node" role="cell" />
        <span class="logger-panel__message" data-testid="log-message" role="cell">
          {{ entry.message }}
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.logger-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--bif-surface, #ffffff);
  color: var(--bif-text-strong, #111827);
}

.logger-panel__toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid var(--bif-border-muted, #e5e7eb);
  flex-wrap: wrap;
}

.logger-panel__levels {
  display: flex;
  gap: 0.25rem;
}

.logger-panel__node-filter {
  width: 12rem;
}

.logger-panel__auto-scope--active {
  color: var(--p-primary-color, #2563eb);
}

.logger-panel__auto-scope--inactive {
  color: var(--p-text-color, #111827);
  background: var(--bif-surface-hover, #f3f4f6);
  border: 1px solid var(--bif-border-strong, #d1d5db);
}

.logger-panel__auto-scope-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1rem;
  height: 1rem;
  color: currentColor;
  opacity: 1;
  font-size: 1rem;
  line-height: 1;
}

.logger-panel__auto-scope-icon--active {
  color: var(--p-primary-color, #2563eb);
}

.logger-panel__auto-scope-icon--inactive {
  color: var(--p-text-color, #111827);
}

.logger-panel__search-wrap {
  display: inline-flex;
  align-items: center;
  min-width: 12rem;
}

.logger-panel__search {
  width: 16rem;
  min-width: 10rem;
}

.logger-panel__list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8125rem;
}

.logger-panel__grid {
  display: grid;
  gap: 0.5rem;
  min-width: 34rem;
}

.logger-panel__header {
  position: sticky;
  top: 0;
  z-index: 1;
  align-items: center;
  padding: 0.375rem 0.5rem;
  border-bottom: 1px solid var(--bif-border-strong, #d1d5db);
  background: var(--bif-surface-muted, #f9fafb);
  color: var(--bif-text-subtle, #4b5563);
  font-family: var(--p-font-family, sans-serif);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.logger-panel__column-header {
  position: relative;
  min-width: 0;
}

.logger-panel__resize-handle {
  position: absolute;
  top: -0.375rem;
  right: -0.375rem;
  bottom: -0.375rem;
  width: 0.5rem;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: col-resize;
  touch-action: none;
}

.logger-panel__resize-handle::after {
  position: absolute;
  top: 0.25rem;
  right: 0.1875rem;
  bottom: 0.25rem;
  width: 1px;
  background: var(--bif-border-strong, #d1d5db);
  content: '';
}

.logger-panel__resize-handle:hover::after,
.logger-panel__resize-handle:focus-visible::after,
.logger-panel__resize-handle--active::after {
  width: 2px;
  background: var(--p-primary-color, #2563eb);
}

.logger-panel__resize-handle:focus-visible {
  outline: 2px solid var(--p-primary-color, #2563eb);
  outline-offset: -2px;
}

.logger-panel__row {
  align-items: start;
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid var(--bif-surface-hover, #f3f4f6);
}

.logger-panel__time,
.logger-panel__node {
  color: var(--bif-text-subtle, #6b7280);
}

.logger-panel__node {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logger-panel__level-badge {
  justify-self: start;
  border-radius: 4px;
  padding: 0 0.25rem;
  font-weight: 700;
  font-size: 0.72rem;
  line-height: 1.35rem;
}

.logger-panel__level-badge--debug {
  background: var(--bif-surface-active, #e5e7eb);
  color: var(--p-text-color, #374151);
}

.logger-panel__level-badge--info {
  background: var(--p-blue-100, #dbeafe);
  color: var(--p-blue-700, #1d4ed8);
}

.logger-panel__level-badge--warning {
  background: var(--p-yellow-100, #fef3c7);
  color: var(--p-yellow-800, #92400e);
}

.logger-panel__level-badge--error {
  background: var(--p-red-100, #fee2e2);
  color: var(--p-red-700, #b91c1c);
}

.log-entry--debug {
  color: var(--p-text-color, #374151);
}

.log-entry--warning {
  background: color-mix(in srgb, var(--p-yellow-300, #fde047) 12%, transparent);
}

.log-entry--error {
  background: color-mix(in srgb, var(--p-red-300, #fca5a5) 14%, transparent);
}

.logger-panel__message {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.logger-panel__empty {
  padding: 1rem;
  color: var(--bif-text-subtle, #6b7280);
}
</style>
