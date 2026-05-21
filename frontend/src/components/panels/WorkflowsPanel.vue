<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { useWorkflowStore } from '@/stores/workflow'
import type { WorkflowInfo } from '@/api/types'
import type { WorkflowTreeNode } from '@/stores/workflow'

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
type WorkflowPanelRow =
  | { type: 'folder'; id: string; name: string; depth: number }
  | { type: 'workflow'; workflow: WorkflowInfo; depth: number }
type WorkflowPanelCommand =
  | 'new'
  | 'save'
  | 'duplicate'
  | 'import'
  | 'export'
  | 'delete'
  | 'open'

function workflowId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

function testId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '_')
}

function flattenRows(nodes: WorkflowTreeNode[]): WorkflowPanelRow[] {
  return nodes.flatMap((node): WorkflowPanelRow[] => {
    if (node.type === 'workflow') {
      return [{ type: 'workflow', workflow: node.workflow, depth: node.depth }]
    }
    return [
      { type: 'folder', id: node.id, name: node.name, depth: node.depth },
      ...flattenRows(node.children),
    ]
  })
}

const filteredWorkflows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const items = workflowStore.flattenedWorkflows
  if (!query) return items
  return items.filter((workflow) => (
    workflow.display_name.toLowerCase().includes(query)
    || workflowId(workflow).toLowerCase().includes(query)
  ))
})

const filteredRows = computed<WorkflowPanelRow[]>(() => {
  const query = searchQuery.value.trim()
  if (query) {
    return filteredWorkflows.value.map((workflow) => ({
      type: 'workflow',
      workflow,
      depth: 0,
    }))
  }
  return flattenRows(workflowStore.workflowTree)
})

const selectedWorkflow = computed(() => {
  if (!selectedName.value) return null
  return workflowStore.flattenedWorkflows.find((workflow) => workflowId(workflow) === selectedName.value) ?? null
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
    if (selectedName.value && workflows.some((workflow) => workflowId(workflow) === selectedName.value)) {
      return
    }
    selectedName.value = workflowStore.currentName ?? (
      workflowStore.flattenedWorkflows[0] ? workflowId(workflowStore.flattenedWorkflows[0]) : null
    )
  },
  { immediate: true },
)

onMounted(() => {
  if (workflowStore.workflows.length === 0) {
    void workflowStore.fetchWorkflowTree().catch(() => workflowStore.fetchWorkflows())
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
  event.dataTransfer?.setData('application/bioimageflow-workflow', workflowId(workflow))
}

function workflowNameFromDrop(event: DragEvent): string | null {
  return event.dataTransfer?.getData('application/bioimageflow-workflow') || null
}

async function createFolder(): Promise<void> {
  const name = window.prompt('Folder name')
  if (name === null) return
  await workflowStore.createWorkflowFolder(name)
}

async function renameFolder(id: string, currentName: string): Promise<void> {
  const name = window.prompt('Folder name', currentName)
  if (name === null) return
  await workflowStore.renameWorkflowFolder(id, name)
}

async function deleteFolder(id: string): Promise<void> {
  if (!window.confirm('Delete this folder? Workflows inside it will move up one level.')) {
    return
  }
  await workflowStore.deleteWorkflowFolder(id)
}

async function dropWorkflowOnFolder(event: DragEvent, folderId: string): Promise<void> {
  const name = workflowNameFromDrop(event)
  if (!name) return
  await workflowStore.moveWorkflowToFolder(name, folderId)
}

async function dropWorkflowOnRoot(event: DragEvent): Promise<void> {
  const name = workflowNameFromDrop(event)
  if (!name) return
  await workflowStore.moveWorkflowToFolder(name, null)
}

async function dropWorkflowBefore(event: DragEvent, beforeName: string): Promise<void> {
  const name = workflowNameFromDrop(event)
  if (!name) return
  await workflowStore.moveWorkflowBefore(name, beforeName)
}

defineExpose({
  filteredWorkflows,
  filteredRows,
  selectedWorkflow,
  formatModifiedTime,
  selectWorkflow,
  openWorkflow,
  onWorkflowDragStart,
  createFolder,
  renameFolder,
  deleteFolder,
  dropWorkflowOnFolder,
  dropWorkflowOnRoot,
  dropWorkflowBefore,
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
        icon="pi pi-folder-plus"
        text
        size="small"
        aria-label="New folder"
        title="New folder"
        data-testid="workflow-new-folder-btn"
        @click="createFolder"
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

    <div
      class="workflows-panel__list"
      data-testid="workflow-list"
      @dragover.prevent
      @drop="dropWorkflowOnRoot"
    >
      <template v-for="row in filteredRows" :key="row.type === 'folder' ? row.id : workflowId(row.workflow)">
        <div
          v-if="row.type === 'folder'"
          class="workflow-folder-row"
          :style="{ paddingLeft: `${row.depth * 1.1 + 0.45}rem` }"
          :data-testid="`workflow-folder-${testId(row.id)}`"
          @dragover.prevent
          @drop.stop="dropWorkflowOnFolder($event, row.id)"
        >
          <span class="workflow-folder-row__name">
            <i class="pi pi-folder" aria-hidden="true" />
            {{ row.name }}
          </span>
          <Button
            icon="pi pi-pencil"
            text
            size="small"
            aria-label="Rename folder"
            title="Rename folder"
            :data-testid="`workflow-folder-rename-${testId(row.id)}`"
            @click="renameFolder(row.id, row.name)"
          />
          <Button
            icon="pi pi-trash"
            text
            size="small"
            severity="danger"
            aria-label="Delete folder"
            title="Delete folder"
            :data-testid="`workflow-folder-delete-${testId(row.id)}`"
            @click="deleteFolder(row.id)"
          />
        </div>
        <button
          v-else
          type="button"
          class="workflow-row"
          :class="{ 'workflow-row--selected': selectedName === workflowId(row.workflow) }"
          :style="{ paddingLeft: `${row.depth * 1.1 + 0.25}rem` }"
          :data-testid="`workflow-row-${testId(workflowId(row.workflow))}`"
          @click="selectWorkflow(workflowId(row.workflow))"
          @dblclick="openWorkflow(workflowId(row.workflow))"
          @dragover.prevent
          @drop.stop="dropWorkflowBefore($event, workflowId(row.workflow))"
          @keydown.enter.prevent="openWorkflow(workflowId(row.workflow))"
        >
          <span
            class="workflow-row__drag"
            draggable="true"
            aria-label="Drag workflow"
            title="Drag workflow"
            :data-testid="`workflow-drag-${testId(workflowId(row.workflow))}`"
            @click.stop
            @dragstart.stop="onWorkflowDragStart($event, row.workflow)"
          >
            <i class="pi pi-bars" aria-hidden="true" />
          </span>
          <span class="workflow-row__name">{{ row.workflow.display_name }}</span>
          <span
            class="workflow-row__time"
            :data-testid="`workflow-row-time-${testId(workflowId(row.workflow))}`"
          >
            {{ formatModifiedTime(row.workflow.last_modified) }}
          </span>
        </button>
      </template>
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
          <dd data-testid="workflow-detail-api-name">{{ workflowId(selectedWorkflow) }}</dd>
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
  background: var(--bif-surface);
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
  background: var(--bif-surface);
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
  background: color-mix(in srgb, var(--p-primary-color) 8%, var(--bif-surface));
}

.workflow-row__drag {
  align-items: center;
  color: color-mix(in srgb, var(--p-text-color) 72%, transparent);
  cursor: grab;
  display: inline-flex;
  height: 1.75rem;
  justify-content: center;
  width: 1.5rem;
}

.workflow-row__drag:hover {
  color: var(--p-text-color);
}

.workflow-row__drag .pi {
  color: currentColor;
  font-size: 1rem;
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

.workflow-folder-row {
  align-items: center;
  background: color-mix(in srgb, var(--p-content-background, var(--bif-surface)) 86%, var(--p-primary-color));
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  display: grid;
  gap: 0.25rem;
  grid-template-columns: minmax(0, 1fr) auto auto;
  min-height: 2.35rem;
  padding: 0.25rem 0.35rem;
}

.workflow-folder-row:hover {
  border-color: var(--p-primary-color);
}

.workflow-folder-row__name {
  align-items: center;
  display: inline-flex;
  font-weight: 700;
  gap: 0.45rem;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
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
