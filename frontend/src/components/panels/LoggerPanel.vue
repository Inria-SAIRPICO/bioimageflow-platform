<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import ToggleButton from 'primevue/togglebutton'
import { useLoggerStore, ALL_LEVELS } from '@/stores/logger'
import { useUIStore } from '@/stores/ui'
import { useWebSocket } from '@/composables/useWebSocket'

const logger = useLoggerStore()
const ui = useUIStore()
const ws = useWebSocket()

const listEl = ref<HTMLElement | null>(null)
const selectedOnly = ref(false)

const selectedNodeId = computed(() =>
  ui.selectedNodeIds.length === 1 ? ui.selectedNodeIds[0] : null,
)

const hasEntries = computed(() => logger.entries.length > 0)
const visibleEntries = computed(() => logger.filteredEntries)

function setNodeFilter(nodeId: string | null) {
  logger.setFilter({ nodeId })
}

function clearFilters() {
  logger.setFilter({
    levels: new Set(ALL_LEVELS),
    nodeId: null,
    searchText: '',
  })
  selectedOnly.value = false
}

function formatTimestamp(seconds: number): string {
  if (!seconds) return ''
  return new Date(seconds * 1000).toLocaleTimeString()
}

function levelClass(level: string): string {
  return `logger-panel__level--${level.toLowerCase()}`
}

async function scrollToBottom() {
  await nextTick()
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  () => selectedOnly.value,
  (enabled) => {
    setNodeFilter(enabled ? selectedNodeId.value : null)
  },
)

watch(selectedNodeId, (nodeId) => {
  if (selectedOnly.value) setNodeFilter(nodeId)
})

watch(
  () => [logger.filter.nodeId, logger.minimumActiveLevel] as const,
  ([nodeId, level]) => {
    if (ws.connectionState.value !== 'connected') return
    void ws.sendSubscribeLogs({ nodeId: nodeId ?? undefined, level: level ?? undefined })
  },
)

watch(
  () => logger.filteredEntries.length,
  () => {
    if (logger.autoScroll) void scrollToBottom()
  },
)
</script>

<template>
  <section class="logger-panel" data-testid="logger-panel" aria-label="Logger">
    <header class="logger-panel__toolbar">
      <div class="logger-panel__levels" aria-label="Log levels">
        <Button
          v-for="level in ALL_LEVELS"
          :key="level"
          :label="level"
          size="small"
          :severity="logger.filter.levels.has(level) ? undefined : 'secondary'"
          :outlined="!logger.filter.levels.has(level)"
          :data-testid="`logger-level-${level}`"
          @click="logger.toggleLevel(level)"
        />
      </div>

      <InputText
        :model-value="logger.filter.searchText"
        placeholder="Search logs"
        class="logger-panel__search"
        data-testid="logger-search"
        @update:model-value="(value) => logger.setFilter({ searchText: String(value ?? '') })"
      />

      <ToggleButton
        v-model="selectedOnly"
        on-label="Selected"
        off-label="All nodes"
        :disabled="selectedNodeId === null"
        data-testid="logger-selected-toggle"
      />

      <label class="logger-panel__checkbox">
        <Checkbox
          :binary="true"
          :model-value="logger.autoScroll"
          data-testid="logger-autoscroll"
          @update:model-value="(value) => logger.setAutoScroll(Boolean(value))"
        />
        <span>Auto-scroll</span>
      </label>

      <Button
        icon="pi pi-filter-slash"
        aria-label="Clear filters"
        text
        data-testid="logger-clear-filters"
        @click="clearFilters"
      />
      <Button
        icon="pi pi-trash"
        aria-label="Clear logs"
        text
        severity="danger"
        data-testid="logger-clear"
        @click="logger.clearEntries()"
      />
    </header>

    <div ref="listEl" class="logger-panel__list" data-testid="logger-list">
      <div v-if="!hasEntries" class="logger-panel__empty" data-testid="logger-empty">
        No logs
      </div>
      <div
        v-for="(entry, index) in visibleEntries"
        :key="`${entry.timestamp}-${index}`"
        class="logger-panel__row"
        data-testid="logger-entry"
      >
        <span class="logger-panel__time">{{ formatTimestamp(entry.timestamp) }}</span>
        <span :class="['logger-panel__level', levelClass(entry.level)]">
          {{ entry.level }}
        </span>
        <span class="logger-panel__node">{{ entry.nodeId ?? 'system' }}</span>
        <span class="logger-panel__message">{{ entry.message }}</span>
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
  background: var(--p-surface-0, #ffffff);
  color: var(--p-surface-900, #111827);
}

.logger-panel__toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.logger-panel__levels {
  display: flex;
  gap: 0.25rem;
}

.logger-panel__search {
  width: 16rem;
  min-width: 10rem;
}

.logger-panel__checkbox {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
  font-size: 0.875rem;
}

.logger-panel__list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8125rem;
}

.logger-panel__row {
  display: grid;
  grid-template-columns: 5.75rem 4.5rem minmax(7rem, 12rem) minmax(0, 1fr);
  gap: 0.5rem;
  align-items: start;
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-100, #f3f4f6);
}

.logger-panel__time,
.logger-panel__node {
  color: var(--p-surface-500, #6b7280);
}

.logger-panel__level {
  font-weight: 700;
}

.logger-panel__level--debug {
  color: var(--p-surface-500, #6b7280);
}

.logger-panel__level--info {
  color: var(--p-blue-600, #2563eb);
}

.logger-panel__level--warning {
  color: var(--p-yellow-700, #a16207);
}

.logger-panel__level--error {
  color: var(--p-red-600, #dc2626);
}

.logger-panel__message {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.logger-panel__empty {
  padding: 1rem;
  color: var(--p-surface-500, #6b7280);
}
</style>
