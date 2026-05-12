<script setup lang="ts">
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
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
const selectedEntry = ref<ErrorEntry | null>(null)

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

function onShowDetails(entry: ErrorEntry) {
  selectedEntry.value = entry
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
            title="Close"
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
                title="Dismiss"
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
            <Button
              v-if="entry.fullDetail || entry.field || entry.status || entry.nodeId"
              data-testid="error-row-details"
              icon="pi pi-list"
              label="Details"
              severity="secondary"
              size="small"
              text
              class="error-row-details"
              @click="onShowDetails(entry)"
            />
          </div>
        </div>
      </aside>
      <Dialog
        :visible="selectedEntry !== null"
        modal
        header="Error details"
        :style="{ width: 'min(720px, 92vw)' }"
        @update:visible="selectedEntry = $event ? selectedEntry : null"
      >
        <dl v-if="selectedEntry" class="error-details" data-testid="error-details-body">
          <template v-if="selectedEntry.nodeId">
            <dt>Node</dt>
            <dd>{{ selectedEntry.nodeId }}</dd>
          </template>
          <template v-if="selectedEntry.status">
            <dt>Status</dt>
            <dd>{{ selectedEntry.status }}</dd>
          </template>
          <template v-if="selectedEntry.field">
            <dt>Field</dt>
            <dd>{{ selectedEntry.field }}</dd>
          </template>
          <dt>Detail</dt>
          <dd>
            <pre
              v-if="selectedEntry.fullDetail"
              class="error-details-traceback"
            >{{ selectedEntry.fullDetail }}</pre>
            <span v-else>{{ selectedEntry.detail }}</span>
          </dd>
        </dl>
        <template #footer>
          <Button label="Close" text @click="selectedEntry = null" />
        </template>
      </Dialog>
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
  background: var(--bif-surface, #fff);
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
  background: var(--bif-surface, #fff);
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

.error-row-details {
  align-self: flex-start;
}

.error-details {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.5rem 1rem;
  margin: 0;
}

.error-details dt {
  color: var(--p-text-muted-color, #6b7280);
  font-weight: 700;
}

.error-details dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.error-details-traceback {
  margin: 0;
  max-height: min(60vh, 32rem);
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.8125rem;
  line-height: 1.45;
  background: var(--bif-surface-muted, #f8fafc);
  border: 1px solid var(--p-surface-border, #e5e7eb);
  border-radius: 6px;
  padding: 0.75rem;
}
</style>
