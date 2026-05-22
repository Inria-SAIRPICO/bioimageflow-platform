<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Tree from 'primevue/tree'
import { useWorkflowStore } from '@/stores/workflow'
import type { WorkflowInfo } from '@/api/types'
import type { WorkflowFolderDeletePolicy, WorkflowTreeNode } from '@/stores/workflow'
import type { TreeNode } from 'primevue/treenode'

const emit = defineEmits<{
  'new-workflow': [folderId: string | null]
  'save-workflow': []
  'duplicate-workflow': [name: string]
  'import-workflow': []
  'export-workflow': [name: string]
  'delete-workflow': [name: string]
  'open-workflow': [name: string]
  'select-workflow': [name: string]
}>()

type WorkflowPanelCommand =
  | 'new'
  | 'save'
  | 'duplicate'
  | 'import'
  | 'export'
  | 'delete'
  | 'open'

export type WorkflowNodeData =
  | { type: 'folder'; id: string; name: string; hasChildren: boolean }
  | { type: 'workflow'; id: string; workflow: WorkflowInfo }

export type WorkflowPrimeTreeNode = {
  key: string
  label: string
  data: WorkflowNodeData
  children?: WorkflowPrimeTreeNode[]
}

const workflowStore = useWorkflowStore()
const searchQuery = ref('')
const selectedName = ref<string | null>(workflowStore.currentName)
const selectedFolderId = ref<string | null>(null)
const selectedKeys = ref<Record<string, boolean>>({})
const expandedKeys = ref<Record<string, boolean>>({})

const folderDialogVisible = ref(false)
const folderDialogMode = ref<'create' | 'rename'>('create')
const folderDialogParentId = ref<string | null>(null)
const folderDialogEditId = ref<string | null>(null)
const folderNameInput = ref('')

const deleteDialogVisible = ref(false)
const deleteFolderTarget = ref<{ id: string; name: string; hasChildren: boolean } | null>(null)

function workflowId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

function testId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '_')
}

function nodeKey(value: string): string {
  return `workflow-tree-${testId(value)}`
}

function folderLeafName(path: string): string {
  const index = path.lastIndexOf('/')
  return index === -1 ? path : path.slice(index + 1)
}

function parentFolderPath(path: string): string | null {
  const index = path.lastIndexOf('/')
  return index === -1 ? null : path.slice(0, index)
}

function childFolderPath(parentId: string | null, name: string): string {
  const trimmed = name.trim().replace(/^\/+|\/+$/g, '')
  return parentId ? `${parentId}/${trimmed}` : trimmed
}

function remapFolderIdPrefix(id: string, oldPrefix: string, newPrefix: string | null): string | null {
  if (id === oldPrefix) return newPrefix
  if (!id.startsWith(`${oldPrefix}/`)) return id
  const suffix = id.slice(oldPrefix.length + 1)
  return newPrefix ? `${newPrefix}/${suffix}` : suffix
}

function dispatchWorkflowCommand(
  action: WorkflowPanelCommand,
  name?: string,
  folderId?: string | null,
): void {
  window.dispatchEvent(new CustomEvent('bioimageflow:workflow-command', {
    detail: { action, name, folderId },
  }))
}

async function runPanelAction(action: () => Promise<void>): Promise<void> {
  try {
    await action()
  } catch (error: unknown) {
    workflowStore.error = error instanceof Error ? error.message : String(error)
  }
}

function toPrimeTreeNodes(nodes: WorkflowTreeNode[]): WorkflowPrimeTreeNode[] {
  return nodes.map((node) => {
    if (node.type === 'workflow') {
      const id = workflowId(node.workflow)
      return {
        key: nodeKey(`workflow:${id}`),
        label: node.workflow.display_name,
        data: { type: 'workflow', id, workflow: node.workflow },
      }
    }
    const children = toPrimeTreeNodes(node.children)
    return {
      key: nodeKey(`folder:${node.id}`),
      label: node.name,
      data: {
        type: 'folder',
        id: node.id,
        name: node.name,
        hasChildren: children.length > 0,
      },
      children,
    }
  })
}

function workflowMatchesQuery(workflow: WorkflowInfo, query: string): boolean {
  return (
    workflow.display_name.toLowerCase().includes(query)
    || workflowId(workflow).toLowerCase().includes(query)
  )
}

const filteredWorkflows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const items = workflowStore.flattenedWorkflows
  if (!query) return items
  return items.filter((workflow) => workflowMatchesQuery(workflow, query))
})

const treeNodes = computed<WorkflowPrimeTreeNode[]>(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (query) {
    return filteredWorkflows.value.map((workflow) => {
      const id = workflowId(workflow)
      return {
        key: nodeKey(`workflow:${id}`),
        label: workflow.display_name,
        data: { type: 'workflow', id, workflow },
      }
    })
  }
  return toPrimeTreeNodes(workflowStore.workflowTree)
})

const selectedWorkflow = computed(() => {
  if (!selectedName.value) return null
  return workflowStore.flattenedWorkflows.find((workflow) => (
    workflowId(workflow) === selectedName.value
  )) ?? null
})

const selectedFolder = computed(() => {
  if (selectedName.value || !selectedFolderId.value) return null
  return workflowStore.workflowFolders.find((folder) => folder.id === selectedFolderId.value) ?? null
})

function folderHasChildren(id: string): boolean {
  return (
    workflowStore.workflowFolders.some((folder) => folder.parentId === id || folder.id.startsWith(`${id}/`))
    || Object.values(workflowStore.workflowFolderIds).some((folderId) => (
      folderId === id || Boolean(folderId?.startsWith(`${id}/`))
    ))
  )
}

watch(
  () => workflowStore.currentName,
  (name) => {
    if (name) selectedName.value = name
  },
)

watch(
  () => selectedName.value,
  (name) => {
    if (name) {
      selectedKeys.value = { [nodeKey(`workflow:${name}`)]: true }
    } else if (selectedFolderId.value) {
      selectedKeys.value = { [nodeKey(`folder:${selectedFolderId.value}`)]: true }
    } else {
      selectedKeys.value = {}
    }
  },
  { immediate: true },
)

watch(
  () => selectedFolderId.value,
  (folderId) => {
    if (!selectedName.value) {
      selectedKeys.value = folderId ? { [nodeKey(`folder:${folderId}`)]: true } : {}
    }
  },
)

watch(
  () => workflowStore.workflowFolders.map((folder) => folder.id),
  (folderIds) => {
    if (selectedFolderId.value && !folderIds.includes(selectedFolderId.value)) {
      selectedFolderId.value = null
    }
  },
)

watch(
  () => workflowStore.workflowTree,
  (nodes) => {
    const keys: Record<string, boolean> = {}
    function visit(items: WorkflowTreeNode[]): void {
      for (const item of items) {
        if (item.type === 'folder') {
          keys[nodeKey(`folder:${item.id}`)] = true
          visit(item.children)
        }
      }
    }
    visit(nodes)
    expandedKeys.value = keys
  },
  { immediate: true, deep: true },
)

watch(
  () => workflowStore.workflows,
  (workflows) => {
    if (selectedName.value && workflows.some((workflow) => workflowId(workflow) === selectedName.value)) {
      return
    }
    if (
      selectedFolderId.value
      && workflowStore.workflowFolders.some((folder) => folder.id === selectedFolderId.value)
    ) {
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
  const workflow = workflowStore.flattenedWorkflows.find((item) => workflowId(item) === name)
  selectedFolderId.value = (
    (workflow as (WorkflowInfo & { folder?: string }) | undefined)?.folder
    || null
  )
  emit('select-workflow', name)
}

function selectFolder(id: string): void {
  selectedName.value = null
  selectedFolderId.value = id
  selectedKeys.value = { [nodeKey(`folder:${id}`)]: true }
}

function createWorkflowInSelectedFolder(): void {
  emit('new-workflow', selectedFolderId.value)
  dispatchWorkflowCommand('new', undefined, selectedFolderId.value)
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

function deleteSelected(): void {
  if (selectedWorkflow.value) {
    emitSelected('delete-workflow')
    return
  }
  if (selectedFolder.value) {
    openDeleteFolderDialog(
      selectedFolder.value.id,
      selectedFolder.value.name,
      folderHasChildren(selectedFolder.value.id),
    )
    return
  }
  emitSelected('delete-workflow')
}

function onNodeSelect(node: TreeNode): void {
  const data = node.data as WorkflowNodeData | undefined
  if (data?.type === 'workflow') {
    selectWorkflow(data.id)
  } else if (data?.type === 'folder') {
    selectFolder(data.id)
  }
}

function openCreateFolderDialog(parentId: string | null = null): void {
  folderDialogMode.value = 'create'
  folderDialogParentId.value = parentId
  folderDialogEditId.value = null
  folderNameInput.value = ''
  folderDialogVisible.value = true
}

function openRenameFolderDialog(id: string, name: string): void {
  folderDialogMode.value = 'rename'
  folderDialogParentId.value = null
  folderDialogEditId.value = id
  folderNameInput.value = name
  folderDialogVisible.value = true
}

async function submitFolderDialog(): Promise<void> {
  const name = folderNameInput.value.trim()
  if (!name) return
  await runPanelAction(async () => {
    if (folderDialogMode.value === 'create') {
      const folder = await workflowStore.createWorkflowFolder(name, folderDialogParentId.value)
      selectedFolderId.value = folder.id
      selectedName.value = null
    } else if (folderDialogEditId.value) {
      const newId = childFolderPath(parentFolderPath(folderDialogEditId.value), name)
      const previousSelectedFolderId = selectedFolderId.value
      await workflowStore.renameWorkflowFolder(folderDialogEditId.value, name)
      if (previousSelectedFolderId) {
        selectedFolderId.value = remapFolderIdPrefix(
          previousSelectedFolderId,
          folderDialogEditId.value,
          newId,
        )
        selectedName.value = null
      }
    }
    folderDialogVisible.value = false
  })
}

function openDeleteFolderDialog(id: string, name: string, hasChildren: boolean): void {
  deleteFolderTarget.value = { id, name, hasChildren }
  deleteDialogVisible.value = true
}

async function confirmDeleteFolder(policy: WorkflowFolderDeletePolicy): Promise<void> {
  const target = deleteFolderTarget.value
  if (!target) return
  await runPanelAction(async () => {
    const previousSelectedFolderId = selectedFolderId.value
    await workflowStore.deleteWorkflowFolder(target.id, policy)
    if (previousSelectedFolderId) {
      selectedFolderId.value = remapFolderIdPrefix(
        previousSelectedFolderId,
        target.id,
        policy === 'move_children_up' ? parentFolderPath(target.id) : null,
      )
      selectedName.value = null
    }
    deleteDialogVisible.value = false
    deleteFolderTarget.value = null
  })
}

function workflowNameFromDrop(event: DragEvent): string | null {
  return event.dataTransfer?.getData('application/bioimageflow-workflow') || null
}

function folderNameFromDrop(event: DragEvent): string | null {
  return event.dataTransfer?.getData('application/bioimageflow-folder') || null
}

function onWorkflowDragStart(event: DragEvent, workflow: WorkflowInfo): void {
  event.dataTransfer?.setData('application/bioimageflow-workflow', workflowId(workflow))
}

function onFolderDragStart(event: DragEvent, id: string): void {
  event.dataTransfer?.setData('application/bioimageflow-folder', id)
}

function onDragOver(event: DragEvent): void {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

async function dropOnFolder(event: DragEvent, targetFolderId: string): Promise<void> {
  event.preventDefault()
  event.stopPropagation()
  const workflowName = workflowNameFromDrop(event)
  const folderName = folderNameFromDrop(event)
  await runPanelAction(async () => {
    if (workflowName) await workflowStore.moveWorkflowToFolder(workflowName, targetFolderId)
    else if (folderName) {
      const newId = childFolderPath(targetFolderId, folderLeafName(folderName))
      const previousSelectedFolderId = selectedFolderId.value
      await workflowStore.moveWorkflowFolder(folderName, targetFolderId)
      if (previousSelectedFolderId) {
        selectedFolderId.value = remapFolderIdPrefix(previousSelectedFolderId, folderName, newId)
        selectedName.value = null
      }
    }
  })
}

async function dropOnRoot(event: DragEvent): Promise<void> {
  event.preventDefault()
  const workflowName = workflowNameFromDrop(event)
  const folderName = folderNameFromDrop(event)
  await runPanelAction(async () => {
    if (workflowName) await workflowStore.moveWorkflowToFolder(workflowName, null)
    else if (folderName) {
      const newId = folderLeafName(folderName)
      const previousSelectedFolderId = selectedFolderId.value
      await workflowStore.moveWorkflowFolder(folderName, null)
      if (previousSelectedFolderId) {
        selectedFolderId.value = remapFolderIdPrefix(previousSelectedFolderId, folderName, newId)
        selectedName.value = null
      }
    }
  })
}

async function dropWorkflowBefore(event: DragEvent, beforeName: string): Promise<void> {
  const name = workflowNameFromDrop(event)
  if (!name) return
  await runPanelAction(() => workflowStore.moveWorkflowBefore(name, beforeName))
}

defineExpose({
  filteredWorkflows,
  treeNodes,
  selectedWorkflow,
  selectedFolder,
  formatModifiedTime,
  selectWorkflow,
  selectFolder,
  openWorkflow,
  onWorkflowDragStart,
  onFolderDragStart,
  openCreateFolderDialog,
  openRenameFolderDialog,
  openDeleteFolderDialog,
  submitFolderDialog,
  confirmDeleteFolder,
  deleteSelected,
  dropOnFolder,
  dropOnRoot,
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
        @click="createWorkflowInSelectedFolder"
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
        @click="openCreateFolderDialog(selectedFolderId)"
      />
      <Button
        icon="pi pi-pencil"
        text
        size="small"
        aria-label="Rename folder"
        title="Rename folder"
        :disabled="!selectedFolder"
        data-testid="workflow-rename-folder-btn"
        @click="selectedFolder && openRenameFolderDialog(selectedFolder.id, selectedFolder.name)"
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
        aria-label="Delete selected item"
        title="Delete selected item"
        :disabled="!selectedWorkflow && !selectedFolder"
        data-testid="workflow-delete-btn"
        @click="deleteSelected"
      />
    </div>

    <InputText
      v-model="searchQuery"
      placeholder="Search workflows..."
      class="workflows-panel__search"
      data-testid="workflow-search"
    />

    <div
      class="workflows-panel__tree-shell"
      data-testid="workflow-list"
      @dragenter.prevent
      @dragover.prevent="onDragOver"
      @drop="dropOnRoot"
    >
      <Tree
        v-model:selectionKeys="selectedKeys"
        v-model:expandedKeys="expandedKeys"
        :value="treeNodes"
        selection-mode="single"
        class="workflow-tree"
        data-testid="workflow-tree"
        @node-select="onNodeSelect"
      >
        <template #default="{ node }">
          <div
            v-if="node.data.type === 'folder'"
            class="workflow-folder-row"
            draggable="true"
            :data-testid="`workflow-folder-${testId(node.data.id)}`"
            @dragstart.stop="onFolderDragStart($event, node.data.id)"
            @dragenter.prevent.stop
            @dragover.prevent.stop="onDragOver"
            @drop.prevent.stop="dropOnFolder($event, node.data.id)"
          >
            <span class="workflow-folder-row__name">
              <i class="pi pi-folder" aria-hidden="true" />
              {{ node.data.name }}
            </span>
          </div>
          <div
            v-else
            class="workflow-row"
            :class="{ 'workflow-row--selected': selectedName === node.data.id }"
            :data-testid="`workflow-row-${testId(node.data.id)}`"
            @dblclick="openWorkflow(node.data.id)"
            @dragenter.prevent.stop
            @dragover.prevent.stop="onDragOver"
            @drop.prevent.stop="dropWorkflowBefore($event, node.data.id)"
            @keydown.enter.prevent="openWorkflow(node.data.id)"
          >
            <span
              class="workflow-row__drag"
              draggable="true"
              aria-label="Drag workflow"
              title="Drag workflow"
              :data-testid="`workflow-drag-${testId(node.data.id)}`"
              @click.stop
              @dragstart.stop="onWorkflowDragStart($event, node.data.workflow)"
            >
              <i class="pi pi-bars" aria-hidden="true" />
            </span>
            <span class="workflow-row__name">{{ node.data.workflow.display_name }}</span>
            <span
              class="workflow-row__time"
              :data-testid="`workflow-row-time-${testId(node.data.id)}`"
            >
              {{ formatModifiedTime(node.data.workflow.last_modified) }}
            </span>
          </div>
        </template>
      </Tree>
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

    <Dialog
      v-model:visible="folderDialogVisible"
      modal
      :header="folderDialogMode === 'create' ? 'New folder' : 'Rename folder'"
      :style="{ width: '28rem' }"
      data-testid="workflow-folder-dialog"
    >
      <div class="folder-dialog-body">
        <label for="workflow-folder-name">Folder name</label>
        <InputText
          id="workflow-folder-name"
          v-model="folderNameInput"
          autofocus
          data-testid="workflow-folder-name-input"
          @keydown.enter.prevent="submitFolderDialog"
        />
      </div>
      <template #footer>
        <Button
          label="Cancel"
          severity="secondary"
          text
          data-testid="workflow-folder-dialog-cancel"
          @click="folderDialogVisible = false"
        />
        <Button
          label="Save"
          data-testid="workflow-folder-dialog-submit"
          @click="submitFolderDialog"
        />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="deleteDialogVisible"
      modal
      header="Delete folder"
      :style="{ width: '32rem' }"
      data-testid="workflow-folder-delete-dialog"
    >
      <p v-if="deleteFolderTarget?.hasChildren" class="delete-folder-copy">
        This folder contains workflows or folders. Choose how to handle its children.
      </p>
      <p v-else class="delete-folder-copy">
        Delete folder "{{ deleteFolderTarget?.name }}"?
      </p>
      <template #footer>
        <Button
          label="Cancel"
          severity="secondary"
          text
          data-testid="workflow-folder-delete-cancel"
          @click="deleteDialogVisible = false"
        />
        <Button
          v-if="deleteFolderTarget?.hasChildren"
          label="Move children up"
          severity="secondary"
          data-testid="workflow-folder-delete-move-up"
          @click="confirmDeleteFolder('move_children_up')"
        />
        <Button
          :label="deleteFolderTarget?.hasChildren ? 'Delete all' : 'Delete'"
          severity="danger"
          data-testid="workflow-folder-delete-confirm"
          @click="confirmDeleteFolder(deleteFolderTarget?.hasChildren ? 'delete_children' : 'empty')"
        />
      </template>
    </Dialog>
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

.workflows-panel__tree-shell {
  min-height: 0;
  overflow: auto;
}

.workflow-tree {
  background: transparent;
  border: 0;
  padding: 0;
}

.workflow-tree :deep(.p-tree-node-content),
.workflow-tree :deep(.p-treenode-content) {
  gap: 0.25rem;
  padding: 0.1rem 0.15rem;
}

.workflow-tree :deep(.p-tree-node-children),
.workflow-tree :deep(.p-treenode-children) {
  padding-left: 0.85rem;
}

.workflow-tree :deep(.p-tree-node-toggle-button),
.workflow-tree :deep(.p-tree-toggler) {
  flex: 0 0 1.25rem;
  height: 1.25rem;
  width: 1.25rem;
}

.workflow-row {
  align-items: center;
  color: var(--p-text-color);
  cursor: pointer;
  display: grid;
  gap: 0.45rem;
  grid-template-columns: 1.5rem minmax(0, 1fr) auto;
  min-height: 2.25rem;
  padding: 0.2rem 0.25rem;
  text-align: left;
  width: 100%;
}

.workflow-row:hover,
.workflow-row--selected {
  color: var(--p-primary-color);
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
  display: flex;
  gap: 0.25rem;
  min-height: 2.25rem;
  padding: 0.2rem 0.25rem;
  width: 100%;
}

.workflow-folder-row__name {
  align-items: center;
  cursor: grab;
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

.folder-dialog-body {
  display: grid;
  gap: 0.4rem;
}

.delete-folder-copy {
  margin: 0;
}
</style>
