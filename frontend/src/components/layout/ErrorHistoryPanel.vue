<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import {
  ERROR_KIND_LABELS,
  useErrorStore,
  type ErrorEntry,
} from '@/stores/errors'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  navigate: [nodeId: string]
}>()

const errorStore = useErrorStore()

const sortedErrors = computed<ErrorEntry[]>(() =>
  [...errorStore.errors].sort((a, b) => b.timestamp - a.timestamp),
)

const isEmpty = computed(() => errorStore.errors.length === 0)

function formatTimestamp(ts: number): string {
  return new Date(ts).toLocaleTimeString()
}

function onDismiss(id: string) {
  errorStore.dismiss(id)
}

function onClearAll() {
  errorStore.clear()
}

function onDismissAll() {
  errorStore.dismissAll()
}

function onNavigate(nodeId: string) {
  emit('navigate', nodeId)
}

function onClose() {
  emit('update:visible', false)
}

function onMaskClick() {
  emit('update:visible', false)
}

// Suppress unused-prop warning when consumers omit @update:visible.
void props
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="error-history-mask"
      data-testid="error-history-mask"
      @click.self="onMaskClick"
    >
      <aside
        class="error-history-panel"
        role="dialog"
        aria-label="Error history"
      >
        <header class="error-history-header">
          <span class="error-history-title">Error history</span>
          <Button
            v-if="!isEmpty"
            data-testid="error-history-dismiss-all"
            severity="secondary"
            size="small"
            text
            label="Dismiss all"
            @click="onDismissAll"
          />
          <Button
            v-if="!isEmpty"
            data-testid="error-history-clear"
            severity="danger"
            size="small"
            text
            label="Clear all"
            @click="onClearAll"
          />
          <Button
            data-testid="error-history-close"
            icon="pi pi-times"
            severity="secondary"
            size="small"
            text
            aria-label="Close"
            @click="onClose"
          />
        </header>

        <div v-if="isEmpty" data-testid="error-history-empty" class="empty-state">
          No errors recorded.
        </div>

        <div v-else class="error-rows">
          <div
            v-for="entry in sortedErrors"
            :key="entry.id"
            :class="['error-row', { dismissed: entry.dismissed }]"
            data-testid="error-row"
          >
            <div class="error-row-meta">
              <span data-testid="error-row-timestamp" class="error-row-timestamp">
                {{ formatTimestamp(entry.timestamp) }}
              </span>
              <span class="error-row-kind">{{ ERROR_KIND_LABELS[entry.kind] }}</span>
              <Button
                data-testid="error-row-dismiss"
                icon="pi pi-times"
                severity="secondary"
                size="small"
                text
                rounded
                aria-label="Dismiss"
                class="error-row-dismiss"
                @click="onDismiss(entry.id)"
              />
            </div>
            <div data-testid="error-row-detail" class="error-row-detail">
              {{ entry.detail }}
            </div>
            <button
              v-if="entry.nodeId"
              data-testid="error-row-navigate"
              type="button"
              class="error-row-navigate"
              @click="onNavigate(entry.nodeId)"
            >
              Go to node
            </button>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.error-history-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
}

.error-history-panel {
  width: min(420px, 100%);
  height: 100%;
  background: var(--p-surface-0, #fff);
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.error-history-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--p-surface-border, #e5e7eb);
}

.error-history-title {
  font-weight: 600;
  margin-right: auto;
}

.empty-state {
  padding: 2rem 1.5rem;
  text-align: center;
  color: var(--p-text-muted-color, #6b7280);
}

.error-rows {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  overflow-y: auto;
}

.error-row {
  border: 1px solid var(--p-surface-border, #e5e7eb);
  border-left: 4px solid var(--p-red-500, #dc2626);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  background: var(--p-surface-0, #fff);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.error-row.dismissed {
  opacity: 0.55;
  border-left-color: var(--p-surface-400, #9ca3af);
}

.error-row-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #6b7280);
}

.error-row-kind {
  font-weight: 600;
  color: var(--p-text-color, #111827);
}

.error-row-dismiss {
  margin-left: auto;
}

.error-row-detail {
  font-size: 0.9rem;
  color: var(--p-text-color, #111827);
  white-space: pre-wrap;
}

.error-row-navigate {
  align-self: flex-start;
  margin-top: 0.25rem;
  background: none;
  border: none;
  padding: 0;
  color: var(--p-primary-color, #2563eb);
  cursor: pointer;
  font-size: 0.85rem;
  text-decoration: underline;
}
</style>
