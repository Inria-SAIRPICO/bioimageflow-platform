<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Tree from 'primevue/tree'
import { useWorkflowStore } from '@/stores/workflow'
import { api } from '@/api/client'
import type { WorkflowInfo } from '@/api/types'
import type { WorkflowFolderDeletePolicy, WorkflowTreeNode } from '@/stores/workflow'
import type { TreeNodeDropEvent } from 'primevue/tree'
import type { TreeNode } from 'primevue/treenode'

const emit = defineEmits<{
  'new-workflow': [folderId: string | null]
  'save-workflow': []
  'duplicate-workflow': [name: string]
  'import-workflow': []
  'export-workflow': [name: string]
  'delete-workflow': [name: string]
  'rename-workflow': [name: string]
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

export type WorkflowPrimeTreeNode = TreeNode & {
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
const renderedTreeNodes = ref<WorkflowPrimeTreeNode[]>([])

const folderDialogVisible = ref(false)
const folderDialogMode = ref<'create' | 'rename-folder' | 'rename-workflow'>('create')
const folderDialogParentId = ref<string | null>(null)
const folderDialogEditId = ref<string | null>(null)
const folderNameInput = ref('')

const deleteDialogVisible = ref(false)
const deleteFolderTarget = ref<{ id: string; name: string; hasChildren: boolean } | null>(null)
const descriptionDialogVisible = ref(false)
const descriptionInput = ref('')

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
        icon: 'pi pi-file',
        draggable: true,
        droppable: false,
        styleClass: 'workflow-tree-node--workflow',
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
      icon: 'pi pi-folder',
      draggable: true,
      droppable: true,
      styleClass: 'workflow-tree-node--folder',
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
        icon: 'pi pi-file',
        draggable: false,
        droppable: false,
      }
    })
  }
  return toPrimeTreeNodes(workflowStore.workflowTree)
})

const treeDragEnabled = computed(() => searchQuery.value.trim().length === 0)

const treePassThrough = {
  nodeContent: ({ context }: { context: { node: WorkflowPrimeTreeNode } }) => {
    const data = context.node.data as WorkflowNodeData | undefined
    if (data?.type !== 'workflow') return undefined
    return {
      'data-workflow-id': data.id,
      onDragstart: (event: DragEvent) => onWorkflowDragStart(event, data.workflow),
    }
  },
}

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
  treeNodes,
  (nodes) => {
    renderedTreeNodes.value = nodes
  },
  { immediate: true, deep: true },
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
  folderDialogMode.value = 'rename-folder'
  folderDialogParentId.value = null
  folderDialogEditId.value = id
  folderNameInput.value = name
  folderDialogVisible.value = true
}

function openRenameWorkflowDialog(id: string, name: string): void {
  folderDialogMode.value = 'rename-workflow'
  folderDialogParentId.value = null
  folderDialogEditId.value = id
  folderNameInput.value = name
  folderDialogVisible.value = true
}

function openRenameSelectedItem(): void {
  if (selectedFolder.value) {
    openRenameFolderDialog(selectedFolder.value.id, selectedFolder.value.name)
  } else if (selectedWorkflow.value) {
    const id = workflowId(selectedWorkflow.value)
    emit('rename-workflow', id)
    openRenameWorkflowDialog(id, selectedWorkflow.value.display_name)
  }
}

async function submitFolderDialog(): Promise<void> {
  const name = folderNameInput.value.trim()
  if (!name) return
  await runPanelAction(async () => {
    if (folderDialogMode.value === 'create') {
      const folder = await workflowStore.createWorkflowFolder(name, folderDialogParentId.value)
      selectedFolderId.value = folder.id
      selectedName.value = null
    } else if (folderDialogMode.value === 'rename-folder' && folderDialogEditId.value) {
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
    } else if (folderDialogMode.value === 'rename-workflow' && folderDialogEditId.value) {
      const previousName = folderDialogEditId.value
      const renamed = await workflowStore.patchWorkflow(previousName, {
        action: 'update',
        display_name: name,
      })
      selectedName.value = workflowId(renamed)
      selectedFolderId.value = null
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

function openDescriptionDialog(): void {
  if (!selectedWorkflow.value) return
  descriptionInput.value = selectedWorkflow.value.description ?? ''
  descriptionDialogVisible.value = true
}

async function submitDescriptionDialog(): Promise<void> {
  const workflow = selectedWorkflow.value
  if (!workflow) return
  const id = workflowId(workflow)
  await runPanelAction(async () => {
    const updated = await workflowStore.patchWorkflow(id, {
      action: 'update',
      description: descriptionInput.value.trim() || null,
    })
    selectedName.value = workflowId(updated)
    selectedFolderId.value = null
    descriptionDialogVisible.value = false
  })
}

function parentPath(path: string): string {
  const index = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'))
  return index === -1 ? path : path.slice(0, index)
}

async function revealSelectedWorkflowFolder(): Promise<void> {
  const path = selectedWorkflow.value?.path
  if (!path) return
  await runPanelAction(async () => {
    await api.post('/api/v1/fs/reveal', { path: parentPath(path) })
  })
}

function onWorkflowDragStart(event: DragEvent, workflow: WorkflowInfo): void {
  event.dataTransfer?.setData('application/bioimageflow-workflow', workflowId(workflow))
}

type NodePlacement = {
  node: WorkflowPrimeTreeNode
  parentId: string | null
  siblings: WorkflowPrimeTreeNode[]
  index: number
}

function findNodePlacement(
  nodes: WorkflowPrimeTreeNode[],
  key: string,
  parentId: string | null = null,
): NodePlacement | null {
  const index = nodes.findIndex((node) => node.key === key)
  if (index !== -1) {
    return { node: nodes[index], parentId, siblings: nodes, index }
  }
  for (const node of nodes) {
    const data = node.data as WorkflowNodeData | undefined
    const childParentId = data?.type === 'folder' ? data.id : parentId
    const placement = findNodePlacement(node.children ?? [], key, childParentId)
    if (placement) return placement
  }
  return null
}

function workflowIndexInPlacement(placement: NodePlacement): number {
  return placement.siblings
    .slice(0, placement.index)
    .filter((node) => (node.data as WorkflowNodeData | undefined)?.type === 'workflow')
    .length
}

async function onTreeNodeDrop(event: TreeNodeDropEvent): Promise<void> {
  const dragNode = event.dragNode as WorkflowPrimeTreeNode
  const dragData = dragNode.data as WorkflowNodeData | undefined
  if (!dragData) {
    renderedTreeNodes.value = treeNodes.value
    return
  }
  const placement = findNodePlacement(event.value as WorkflowPrimeTreeNode[], dragNode.key)
  if (!placement) {
    renderedTreeNodes.value = treeNodes.value
    return
  }
  await runPanelAction(async () => {
    if (dragData.type === 'folder') {
      const targetParentId = placement.parentId
      const newId = targetParentId
        ? childFolderPath(targetParentId, folderLeafName(dragData.id))
        : folderLeafName(dragData.id)
      const previousSelectedFolderId = selectedFolderId.value
      await workflowStore.moveWorkflowFolder(dragData.id, targetParentId)
      if (previousSelectedFolderId) {
        selectedFolderId.value = remapFolderIdPrefix(previousSelectedFolderId, dragData.id, newId)
        selectedName.value = null
      }
    } else {
      await workflowStore.moveWorkflowToFolder(
        dragData.id,
        placement.parentId,
        workflowIndexInPlacement(placement),
      )
    }
  })
  renderedTreeNodes.value = treeNodes.value
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
  openCreateFolderDialog,
  openRenameFolderDialog,
  openRenameWorkflowDialog,
  openRenameSelectedItem,
  openDeleteFolderDialog,
  submitFolderDialog,
  confirmDeleteFolder,
  openDescriptionDialog,
  submitDescriptionDialog,
  revealSelectedWorkflowFolder,
  deleteSelected,
  onTreeNodeDrop,
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
        aria-label="Rename selected item"
        title="Rename selected item"
        :disabled="!selectedWorkflow && !selectedFolder"
        data-testid="workflow-rename-selected-btn"
        @click="openRenameSelectedItem"
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
    >
      <Tree
        v-model:value="renderedTreeNodes"
        v-model:selectionKeys="selectedKeys"
        v-model:expandedKeys="expandedKeys"
        :draggable-nodes="treeDragEnabled"
        :droppable-nodes="treeDragEnabled"
        :pt="treePassThrough"
        draggable-scope="workflow-tree"
        droppable-scope="workflow-tree"
        selection-mode="single"
        class="workflow-tree"
        data-testid="workflow-tree"
        @node-drop="onTreeNodeDrop"
        @node-select="onNodeSelect"
      >
        <template #default="{ node }">
          <div
            v-if="node.data.type === 'folder'"
            class="workflow-folder-row"
            :data-testid="`workflow-folder-${testId(node.data.id)}`"
          >
            <span class="workflow-folder-row__name">{{ node.data.name }}</span>
          </div>
          <div
            v-else
            class="workflow-row"
            :class="{ 'workflow-row--selected': selectedName === node.data.id }"
            :data-testid="`workflow-row-${testId(node.data.id)}`"
            :data-workflow-id="node.data.id"
            @dragstart="onWorkflowDragStart($event, node.data.workflow)"
            @dblclick="openWorkflow(node.data.id)"
            @keydown.enter.prevent="openWorkflow(node.data.id)"
          >
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
        <div class="workflow-detail__actions">
          <Button
            icon="pi pi-folder-open"
            text
            size="small"
            aria-label="Open workflow"
            title="Open workflow"
            data-testid="workflow-open-btn"
            @click="openWorkflow()"
          />
          <Button
            icon="pi pi-external-link"
            text
            size="small"
            aria-label="Open workflow folder"
            title="Open workflow folder"
            data-testid="workflow-reveal-folder-btn"
            @click="revealSelectedWorkflowFolder"
          />
        </div>
      </div>
      <dl>
        <div>
          <dt class="workflow-detail__term-with-action">
            <span>Description</span>
            <Button
              icon="pi pi-pencil"
              text
              size="small"
              aria-label="Edit workflow description"
              title="Edit workflow description"
              data-testid="workflow-edit-description-btn"
              @click="openDescriptionDialog"
            />
          </dt>
          <dd data-testid="workflow-detail-description">
            {{ selectedWorkflow.description || 'No description.' }}
          </dd>
        </div>
        <div>
          <dt>API name</dt>
          <dd data-testid="workflow-detail-api-name">{{ workflowId(selectedWorkflow) }}</dd>
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
      :header="folderDialogMode === 'create' ? 'New folder' : folderDialogMode === 'rename-folder' ? 'Rename folder' : 'Rename workflow'"
      :style="{ width: '28rem' }"
      data-testid="workflow-folder-dialog"
    >
      <div class="folder-dialog-body">
        <label for="workflow-folder-name">
          {{ folderDialogMode === 'rename-workflow' ? 'Workflow name' : 'Folder name' }}
        </label>
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
      v-model:visible="descriptionDialogVisible"
      modal
      header="Edit workflow description"
      :style="{ width: '32rem' }"
      data-testid="workflow-description-dialog"
    >
      <div class="folder-dialog-body">
        <label for="workflow-description">Description</label>
        <Textarea
          id="workflow-description"
          v-model="descriptionInput"
          auto-resize
          rows="5"
          data-testid="workflow-description-edit-input"
        />
      </div>
      <template #footer>
        <Button
          label="Cancel"
          severity="secondary"
          text
          data-testid="workflow-description-dialog-cancel"
          @click="descriptionDialogVisible = false"
        />
        <Button
          label="Save"
          data-testid="workflow-description-dialog-submit"
          @click="submitDescriptionDialog"
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
  flex-wrap: wrap;
  gap: 0.25rem;
}

.workflows-panel__search {
  max-width: 100%;
  min-width: 0;
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

.workflow-tree :deep(.p-tree-node),
.workflow-tree :deep(.p-treenode) {
  position: relative;
}

.workflow-tree :deep(.p-tree-node-content),
.workflow-tree :deep(.p-treenode-content) {
  align-items: center;
  cursor: grab;
  gap: 0.35rem;
  min-height: 2.25rem;
  padding: 0.1rem 0.15rem;
}

.workflow-tree :deep(.p-tree-node-content[data-p-dragging="true"]),
.workflow-tree :deep(.p-treenode-content[data-p-dragging="true"]) {
  opacity: 0.55;
}

.workflow-tree :deep(.p-tree-node-content.p-tree-node-dragover),
.workflow-tree :deep(.p-treenode-content.p-treenode-dragover) {
  background: color-mix(in srgb, var(--p-primary-color) 12%, transparent);
  outline: 1px solid color-mix(in srgb, var(--p-primary-color) 45%, transparent);
}

.workflow-tree :deep(.p-tree-node-drop-point),
.workflow-tree :deep(.p-treenode-droppoint) {
  background: var(--p-primary-color);
  border-radius: 999px;
  height: 2px;
  left: 1.65rem;
  margin: 0;
  pointer-events: none;
  position: absolute;
  right: 0.25rem;
  top: 0;
  z-index: 2;
}

.workflow-tree :deep(.p-tree-node-content + .p-tree-node-drop-point),
.workflow-tree :deep(.p-treenode-content + .p-treenode-droppoint) {
  top: 2.25rem;
}

.workflow-tree :deep(.p-tree-node-icon),
.workflow-tree :deep(.p-treenode-icon) {
  color: var(--p-text-muted-color);
  flex: 0 0 1rem;
}

.workflow-tree :deep(.p-tree-node-label),
.workflow-tree :deep(.p-treenode-label) {
  flex: 1 1 auto;
  min-width: 0;
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
  display: grid;
  gap: 0.45rem;
  grid-template-columns: minmax(0, 1fr) auto;
  min-height: 2.25rem;
  padding: 0.2rem 0.25rem;
  text-align: left;
  width: 100%;
}

.workflow-row:hover,
.workflow-row--selected {
  color: var(--p-primary-color);
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
  overflow: auto;
  padding-top: 0.75rem;
}

.workflow-detail__header {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

.workflow-detail__actions {
  align-items: center;
  display: flex;
  flex: 0 0 auto;
  gap: 0.15rem;
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

.workflow-detail__term-with-action {
  align-items: center;
  display: flex;
  justify-content: space-between;
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
