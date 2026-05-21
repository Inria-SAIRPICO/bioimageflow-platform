<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import type { WorkflowInfo } from '@/api/types'

const props = defineProps<{
  visible: boolean
  workflows: WorkflowInfo[]
  currentName?: string | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  open: [name: string]
}>()

const query = ref('')
const selectedName = ref<string | null>(null)

function workflowId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

const filteredWorkflows = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.workflows
  return props.workflows.filter((workflow) => (
    workflowId(workflow).toLowerCase().includes(q)
    || workflow.display_name.toLowerCase().includes(q)
    || (workflow.description ?? '').toLowerCase().includes(q)
  ))
})

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    query.value = ''
    selectedName.value = props.currentName ?? (
      props.workflows[0] ? workflowId(props.workflows[0]) : null
    )
  },
)

function onOpen() {
  if (selectedName.value) {
    emit('open', selectedName.value)
  }
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :style="{ width: '620px' }"
    class="open-workflow-dialog"
    data-testid="open-workflow-dialog"
    @update:visible="emit('update:visible', $event)"
  >
    <template #header>
      <div class="dialog-title">
        <span class="dialog-kicker">Library</span>
        <h2>Open workflow</h2>
        <p>Choose a saved workflow. Unsaved auto-save recovery is applied before server state.</p>
      </div>
    </template>

    <InputText
      v-model="query"
      placeholder="Search workflows..."
      class="search"
      data-testid="workflow-open-search"
    />

    <div class="workflow-list" data-testid="workflow-open-list">
      <button
        v-for="workflow in filteredWorkflows"
        :key="workflowId(workflow)"
        type="button"
        class="workflow-card"
        :class="{ selected: selectedName === workflowId(workflow) }"
        :data-testid="`workflow-open-option-${workflowId(workflow).replace(/[^a-zA-Z0-9_-]/g, '_')}`"
        @click="selectedName = workflowId(workflow)"
        @dblclick="emit('open', workflowId(workflow))"
      >
        <span class="workflow-card__name">{{ workflow.display_name }}</span>
        <span class="workflow-card__path">{{ workflowId(workflow) }}</span>
        <span v-if="workflow.description" class="workflow-card__description">
          {{ workflow.description }}
        </span>
      </button>
      <div v-if="filteredWorkflows.length === 0" class="empty">
        No workflows match this search.
      </div>
    </div>

    <template #footer>
      <Button label="Cancel" text @click="emit('update:visible', false)" />
      <Button
        label="Open"
        icon="pi pi-folder-open"
        :disabled="!selectedName"
        data-testid="workflow-open-submit"
        @click="onOpen"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.dialog-kicker {
  color: var(--p-primary-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.dialog-title h2 {
  margin: 0.2rem 0;
}
.dialog-title p {
  color: var(--p-text-muted-color);
  margin: 0;
}
.search {
  margin-bottom: 1rem;
  width: 100%;
}
.workflow-list {
  display: grid;
  gap: 0.6rem;
  max-height: 360px;
  overflow: auto;
}
.workflow-card {
  background: linear-gradient(135deg, var(--p-surface-0), var(--p-surface-50));
  border: 1px solid var(--p-content-border-color);
  border-radius: 12px;
  color: var(--p-text-color);
  cursor: pointer;
  display: grid;
  gap: 0.2rem;
  padding: 0.85rem 1rem;
  text-align: left;
}
.workflow-card.selected {
  border-color: var(--p-primary-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--p-primary-color) 18%, transparent);
}
.workflow-card__name {
  font-size: 1rem;
  font-weight: 800;
}
.workflow-card__path,
.workflow-card__description {
  color: var(--p-text-muted-color);
  font-size: 0.82rem;
}
.empty {
  color: var(--p-text-muted-color);
  padding: 1rem;
  text-align: center;
}
</style>
