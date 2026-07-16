<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import Button from 'primevue/button'
import { useCanvasStatusProjection } from '@/composables/useCanvasStatusProjection'

const props = withDefaults(defineProps<{
  nodeId: string
  active?: boolean
}>(), {
  active: true,
})
const statusProjection = useCanvasStatusProjection()

const status = computed(() => (
  props.active ? statusProjection.statusForNode(props.nodeId) : null
))
const isFailed = computed(() => status.value?.status === 'failed')
const error = computed(() => status.value?.error ?? null)
const traceback = computed(() => status.value?.traceback ?? null)

const expanded = ref(false)
const copied = ref(false)
let copyResetTimer: ReturnType<typeof setTimeout> | null = null

const rowInfo = computed(() => {
  if (!props.active) return null
  const p = statusProjection.progressForNode(props.nodeId)
  if (!p) return null
  return { row: p.row, total: p.total_rows }
})

async function copyTraceback() {
  if (!traceback.value) return
  try {
    await navigator.clipboard.writeText(traceback.value)
    copied.value = true
    if (copyResetTimer !== null) clearTimeout(copyResetTimer)
    copyResetTimer = setTimeout(() => {
      copied.value = false
      copyResetTimer = null
    }, 2000)
  } catch {
    // Clipboard permissions denied; swallow.
  }
}

function toggleTraceback() {
  expanded.value = !expanded.value
}

onBeforeUnmount(() => {
  if (copyResetTimer !== null) {
    clearTimeout(copyResetTimer)
    copyResetTimer = null
  }
})
</script>

<template>
  <div v-if="isFailed" class="error-block">
    <div class="error-header">
      <i class="pi pi-times-circle" />
      <span class="error-title">Node failed</span>
    </div>
    <div class="error-message">
      {{ error ?? 'Node failed (no error message provided)' }}
    </div>
    <div
      v-if="rowInfo"
      data-testid="failed-row-line"
      class="failed-row-line"
    >
      Node failed on row {{ rowInfo.row }} of {{ rowInfo.total }}.
      All results for this node were discarded. Fix the issue and re-run.
    </div>
    <div v-else class="failed-row-line">
      All results for this node were discarded. Fix the issue and re-run.
    </div>
    <div v-if="traceback" class="traceback-actions">
      <Button
        data-testid="traceback-toggle"
        size="small"
        text
        :label="expanded ? 'Hide traceback' : 'Show traceback'"
        @click="toggleTraceback"
      />
      <Button
        data-testid="copy-traceback"
        size="small"
        text
        icon="pi pi-copy"
        label="Copy traceback"
        @click="copyTraceback"
      />
      <span v-if="copied" data-testid="copy-confirm" class="copy-confirm">
        Copied
      </span>
    </div>
    <pre
      v-if="expanded && traceback"
      data-testid="traceback-pre"
      class="traceback-pre"
    >{{ traceback }}</pre>
  </div>
</template>

<style scoped>
.error-block {
  background: color-mix(
    in srgb,
    var(--p-red-500, #dc2626) 8%,
    var(--p-surface-0, #fff)
  );
  border: 1px solid var(--p-red-500, #dc2626);
  border-left: 4px solid var(--p-red-500, #dc2626);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.error-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--p-red-700, #b91c1c);
  font-weight: 600;
}

.error-message {
  font-size: 0.95rem;
  color: var(--p-text-color, #111827);
  white-space: pre-wrap;
}

.failed-row-line {
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #6b7280);
}

.traceback-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.copy-confirm {
  font-size: 0.85rem;
  color: var(--p-green-600, #16a34a);
  margin-left: 0.5rem;
}

.traceback-pre {
  margin: 0;
  padding: 0.5rem;
  background: var(--bif-surface-hover, #f3f4f6);
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  overflow-x: auto;
  max-height: 240px;
  overflow-y: auto;
  white-space: pre;
}
</style>
