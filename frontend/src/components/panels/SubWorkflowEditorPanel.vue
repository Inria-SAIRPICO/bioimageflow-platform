<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import CanvasView from '@/components/canvas/CanvasView.vue'
import { useSubWorkflowSessionsStore } from '@/stores/subWorkflowSessions'

const props = defineProps<{
  params?: {
    sessionId?: string
  }
}>()

const sessionsStore = useSubWorkflowSessionsStore()

const sessionId = computed(() => props.params?.sessionId ?? '')
const session = computed(() => sessionsStore.sessionById(sessionId.value))
const isDirty = computed(() => (
  sessionId.value !== '' && sessionsStore.isDirty(sessionId.value)
))

function save() {
  const current = session.value
  if (!current) return
  const saved = sessionsStore.saveSession(current.id)
  window.dispatchEvent(new CustomEvent('bioimageflow:apply-sub-workflow-session', {
    detail: {
      sessionId: current.id,
      parentNodeId: current.parentNodeId,
      graph: saved.graph,
      published_inputs: saved.published_inputs,
      published_outputs: saved.published_outputs,
    },
  }))
}

function close() {
  const current = session.value
  if (!current) return
  if (
    sessionsStore.isDirty(current.id) &&
    !window.confirm(`Discard unsaved changes to sub-workflow '${current.parentNodeName}'?`)
  ) {
    return
  }
  window.dispatchEvent(new CustomEvent('bioimageflow:close-sub-workflow-session', {
    detail: {
      sessionId: current.id,
      discardConfirmed: true,
    },
  }))
}

defineExpose({ save, close })
</script>

<template>
  <div class="sub-workflow-editor">
    <header class="sub-workflow-editor__toolbar">
      <div class="sub-workflow-editor__title">
        <strong>{{ session?.parentNodeName ?? 'Sub-workflow' }}</strong>
        <span
          v-if="isDirty"
          class="sub-workflow-editor__dirty"
        >
          Unsaved
        </span>
      </div>
      <div class="sub-workflow-editor__actions">
        <Button
          icon="pi pi-save"
          label="Apply"
          size="small"
          :disabled="!session"
          @click="save"
        />
        <Button
          icon="pi pi-times"
          label="Close"
          size="small"
          severity="secondary"
          text
          :disabled="!session"
          @click="close"
        />
      </div>
    </header>
    <CanvasView
      v-if="sessionId"
      :sub-workflow-session-id="sessionId"
    />
  </div>
</template>

<style scoped>
.sub-workflow-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.sub-workflow-editor__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-surface-0);
}

.sub-workflow-editor__title,
.sub-workflow-editor__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.sub-workflow-editor__title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub-workflow-editor__dirty {
  color: var(--p-orange-700);
  font-size: 0.75rem;
}

.sub-workflow-editor :deep(.canvas-view) {
  flex: 1;
  min-height: 0;
}
</style>
