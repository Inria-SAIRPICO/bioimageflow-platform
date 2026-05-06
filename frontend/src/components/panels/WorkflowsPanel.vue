<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { useWorkflowStore } from '@/stores/workflow'
import type { WorkflowInfo } from '@/api/types'

const emit = defineEmits<{
  'new-workflow': []
  'save-workflow': []
  'duplicate-workflow': [name: string]
  'import-workflow': []
  'export-workflow': [name: string]
  'delete-workflow': [name: string]
  'open-workflow': [name: string]
  'select-workflow': [name: string]
}>()

const workflowStore = useWorkflowStore()
const searchQuery = ref('')
const selectedName = ref<string | null>(workflowStore.currentName)
type WorkflowPanelCommand =
  | 'new'
  | 'save'
  | 'duplicate'
  | 'import'
  | 'export'
  | 'delete'
  | 'open'

const filteredWorkflows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const items = workflowStore.workflows
  if (!query) return items
  return items.filter((workflow) => (
    workflow.display_name.toLowerCase().includes(query)
    || workflow.name.toLowerCase().includes(query)
  ))
})

const selectedWorkflow = computed(() => {
  if (!selectedName.value) return null
  return workflowStore.workflows.find((workflow) => workflow.name === selectedName.value) ?? null
})

watch(
  () => workflowStore.currentName,
  (name) => {
    if (name) selectedName.value = name
  },
)

watch(
  () => workflowStore.workflows,
  (workflows) => {
    if (selectedName.value && workflows.some((workflow) => workflow.name === selectedName.value)) {
      return
    }
    selectedName.value = workflowStore.currentName ?? workflows[0]?.name ?? null
  },
  { immediate: true },
)

onMounted(() => {
  if (workflowStore.workflows.length === 0) {
    void workflowStore.fetchWorkflows()
  }
})

function formatModifiedTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

function selectWorkflow(name: string): void {
  selectedName.value = name
  emit('select-workflow', name)
}

function dispatchWorkflowCommand(action: WorkflowPanelCommand, name?: string): void {
  window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
    detail: { action, name },
  }))
}

function openWorkflow(name = selectedName.value): void {
  if (!name) return
  emit('open-workflow', name)
  dispatchWorkflowCommand('open', name)
}

function emitSelected(action: 'duplicate-workflow' | 'export-workflow' | 'delete-workflow'): void {
  if (!selectedName.value) return
  if (action === 'duplicate-workflow') {
    emit('duplicate-workflow', selectedName.value)
    dispatchWorkflowCommand('duplicate', selectedName.value)
  } else if (action === 'export-workflow') {
    emit('export-workflow', selectedName.value)
    dispatchWorkflowCommand('export', selectedName.value)
  } else {
    emit('delete-workflow', selectedName.value)
    dispatchWorkflowCommand('delete', selectedName.value)
  }
}

function onWorkflowDragStart(event: DragEvent, workflow: WorkflowInfo): void {
  event.dataTransfer?.setData('application/bioimageflow-workflow', workflow.name)
}

defineExpose({
  filteredWorkflows,
  selectedWorkflow,
  formatModifiedTime,
  selectWorkflow,
  openWorkflow,
  onWorkflowDragStart,
})
</script>

<template>
  <section class="workflows-panel" data-testid="workflows-panel" aria-label="Workflows">
    <div class="workflows-panel__toolbar" aria-label="Workflow actions">
      <Button
        icon="pi pi-plus"
        text
        size="small"
        aria-label="New workflow"
        title="New workflow"
        data-testid="workflow-new-btn"
        @click="emit('new-workflow'); dispatchWorkflowCommand('new')"
      />
      <Button
        icon="pi pi-save"
        text
        size="small"
        aria-label="Save workflow"
        title="Save workflow"
        data-testid="workflow-save-btn"
        @click="emit('save-workflow'); dispatchWorkflowCommand('save')"
      />
      <Button
        icon="pi pi-copy"
        text
        size="small"
        aria-label="Duplicate workflow"
        title="Duplicate workflow"
        :disabled="!selectedWorkflow"
        data-testid="workflow-duplicate-btn"
        @click="emitSelected('duplicate-workflow')"
      />
      <Button
        icon="pi pi-upload"
        text
        size="small"
        aria-label="Import workflow"
        title="Import workflow"
        data-testid="workflow-import-btn"
        @click="emit('import-workflow'); dispatchWorkflowCommand('import')"
      />
      <Button
        icon="pi pi-download"
        text
        size="small"
        aria-label="Export workflow"
        title="Export workflow"
        :disabled="!selectedWorkflow"
        data-testid="workflow-export-btn"
        @click="emitSelected('export-workflow')"
      />
      <Button
        icon="pi pi-trash"
        text
        size="small"
        severity="danger"
        aria-label="Delete workflow"
        title="Delete workflow"
        :disabled="!selectedWorkflow"
        data-testid="workflow-delete-btn"
        @click="emitSelected('delete-workflow')"
      />
    </div>

    <InputText
      v-model="searchQuery"
      placeholder="Search workflows..."
      class="workflows-panel__search"
      data-testid="workflow-search"
    />

    <div class="workflows-panel__list" data-testid="workflow-list">
      <button
        v-for="workflow in filteredWorkflows"
        :key="workflow.name"
        type="button"
        class="workflow-row"
        :class="{ 'workflow-row--selected': selectedName === workflow.name }"
        :data-testid="`workflow-row-${workflow.name}`"
        @click="selectWorkflow(workflow.name)"
        @dblclick="openWorkflow(workflow.name)"
        @keydown.enter.prevent="openWorkflow(workflow.name)"
      >
        <span
          class="workflow-row__drag"
          draggable="true"
          aria-label="Drag workflow"
          title="Drag workflow"
          :data-testid="`workflow-drag-${workflow.name}`"
          @click.stop
          @dragstart.stop="onWorkflowDragStart($event, workflow)"
        >
          <i class="pi pi-grip-vertical" aria-hidden="true" />
        </span>
        <span class="workflow-row__name">{{ workflow.display_name }}</span>
        <span
          class="workflow-row__time"
          :data-testid="`workflow-row-time-${workflow.name}`"
        >
          {{ formatModifiedTime(workflow.last_modified) }}
        </span>
      </button>
      <div v-if="filteredWorkflows.length === 0" class="workflows-panel__empty">
        No workflows found.
      </div>
    </div>

    <section
      v-if="selectedWorkflow"
      class="workflow-detail"
      data-testid="workflow-detail"
      aria-label="Selected workflow details"
    >
      <div class="workflow-detail__header">
        <h3>{{ selectedWorkflow.display_name }}</h3>
        <Button
          label="Open"
          icon="pi pi-folder-open"
          size="small"
          data-testid="workflow-open-btn"
          @click="openWorkflow()"
        />
      </div>
      <dl>
        <div>
          <dt>Description</dt>
          <dd data-testid="workflow-detail-description">
            {{ selectedWorkflow.description || 'No description.' }}
          </dd>
        </div>
        <div>
          <dt>API name</dt>
          <dd data-testid="workflow-detail-api-name">{{ selectedWorkflow.name }}</dd>
        </div>
        <div>
          <dt>Workflow file</dt>
          <dd data-testid="workflow-detail-path">{{ selectedWorkflow.path }}</dd>
        </div>
        <div>
          <dt>Storage path</dt>
          <dd data-testid="workflow-detail-storage-path">
            {{ selectedWorkflow.storage_path || 'Default workflow storage' }}
          </dd>
        </div>
      </dl>
    </section>
  </section>
</template>

<style scoped>
.workflows-panel {
  background: var(--p-surface-0);
  color: var(--p-text-color);
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  gap: 0.65rem;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  padding: 0.75rem;
}

.workflows-panel__toolbar {
  align-items: center;
  display: flex;
  gap: 0.25rem;
}

.workflows-panel__search {
  width: 100%;
}

.workflows-panel__list {
  display: grid;
  align-content: start;
  gap: 0.35rem;
  min-height: 0;
  overflow: auto;
}

.workflow-row {
  align-items: center;
  background: var(--p-surface-0);
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  color: var(--p-text-color);
  cursor: pointer;
  display: grid;
  gap: 0.45rem;
  grid-template-columns: 1.5rem minmax(0, 1fr) auto;
  min-height: 2.4rem;
  padding: 0.35rem 0.5rem 0.35rem 0.25rem;
  text-align: left;
  width: 100%;
}

.workflow-row:hover,
.workflow-row--selected {
  border-color: var(--p-primary-color);
}

.workflow-row--selected {
  background: color-mix(in srgb, var(--p-primary-color) 8%, var(--p-surface-0));
}

.workflow-row__drag {
  align-items: center;
  color: var(--p-text-muted-color);
  cursor: grab;
  display: inline-flex;
  height: 1.75rem;
  justify-content: center;
  width: 1.5rem;
}

.workflow-row__name {
  font-weight: 700;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-row__time {
  color: var(--p-text-muted-color);
  font-size: 0.78rem;
  white-space: nowrap;
}

.workflows-panel__empty {
  color: var(--p-text-muted-color);
  padding: 1rem 0.5rem;
  text-align: center;
}

.workflow-detail {
  border-top: 1px solid var(--p-content-border-color);
  display: grid;
  gap: 0.6rem;
  max-height: 45%;
  min-height: 10rem;
  overflow: auto;
  padding-top: 0.75rem;
}

.workflow-detail__header {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

.workflow-detail h3 {
  font-size: 0.95rem;
  margin: 0;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-detail dl {
  display: grid;
  gap: 0.55rem;
  margin: 0;
}

.workflow-detail dt {
  color: var(--p-text-muted-color);
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
}

.workflow-detail dd {
  font-size: 0.85rem;
  margin: 0.15rem 0 0;
  overflow-wrap: anywhere;
}
</style>
