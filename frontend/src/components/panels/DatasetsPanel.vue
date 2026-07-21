<template>
  <section class="datasets-panel">
    <input ref="fileInput" class="sr-only" type="file" multiple @change="onFilesChosen">
    <Button label="Upload files" icon="pi pi-upload" :disabled="locked" @click="fileInput?.click()" />

    <div v-if="store.uploads.length" class="upload-status" aria-live="polite">
      <div class="upload-progress-row">
        <ProgressBar :value="store.progress" />
        <div class="upload-progress-actions">
          <Button
            v-if="store.hasActiveUploads"
            data-testid="upload-cancel-all"
            label="Cancel uploads"
            icon="pi pi-times"
            size="small"
            text
            @click="store.cancelUploads"
          />
          <Button
            v-if="store.hasCompletedUploads"
            data-testid="upload-clear-completed"
            label="Clear completed"
            icon="pi pi-check"
            size="small"
            text
            @click="store.clearCompletedUploads"
          />
        </div>
      </div>
      <div class="upload-messages">
        <div v-for="upload in store.uploads" :key="upload.id" class="upload-message" :class="upload.status">
          <span>{{ upload.file.name }} — {{ uploadLabel(upload) }}</span>
          <div class="upload-message-actions">
            <Button
              v-if="upload.status === 'queued' || upload.status === 'uploading'"
              :data-testid="`upload-cancel-${upload.id}`"
              label="Cancel"
              text
              size="small"
              @click="store.cancelUpload(upload)"
            />
            <Button
              v-if="upload.status === 'error' || upload.status === 'cancelled'"
              :data-testid="`upload-retry-${upload.id}`"
              label="Retry"
              text
              size="small"
              @click="store.retryUpload(upload, uploadFolderId)"
            />
            <Button
              v-if="upload.status === 'error'"
              :data-testid="`upload-dismiss-${upload.id}`"
              label="Dismiss"
              text
              size="small"
              @click="store.dismissUpload(upload)"
            />
          </div>
        </div>
      </div>
    </div>

    <InputText v-model="query" class="dataset-search" placeholder="Search files and folders" />

    <div class="dataset-toolbar" aria-label="Dataset editing actions">
      <Button
        data-testid="dataset-add-folder"
        icon="pi pi-folder-plus"
        text
        size="small"
        aria-label="Add folder"
        title="Add folder"
        :disabled="locked"
        @click="openAddFolder"
      />
      <Button
        data-testid="dataset-rename"
        icon="pi pi-pencil"
        text
        size="small"
        aria-label="Rename"
        title="Rename"
        :disabled="locked || selectedRootNodes.length !== 1"
        @click="openRename"
      />
      <Button
        data-testid="dataset-delete"
        icon="pi pi-trash"
        text
        size="small"
        severity="danger"
        aria-label="Delete"
        title="Delete"
        :disabled="locked || selectedNodes.length === 0"
        @click="confirmDelete"
      />
    </div>
    <div class="dataset-selection-actions" aria-label="Dataset selection actions">
      <Button
        data-testid="dataset-clear-selection"
        label="Unselect all"
        size="small"
        text
        :disabled="selectedNodes.length === 0"
        @click="clearSelection"
      />
    </div>
    <small v-if="treeActionError" class="action-error" aria-live="polite">
      {{ treeActionError }}
    </small>

    <div class="dataset-tree-wrap" @dragstart.capture="onTreeDragStart">
      <Tree
        v-model:expandedKeys="expandedKeys"
        :value="visibleNodes"
        draggable-nodes
        droppable-nodes
        validate-drop
        :pt="treePassThrough"
        class="dataset-tree"
        @node-drop="onNodeDrop"
      >
        <template #default="slotProps">
          <span class="dataset-node" @click.stop>
            <Checkbox
              :model-value="nodeSelectionState(slotProps.node) === 'all'"
              :indeterminate="nodeSelectionState(slotProps.node) === 'partial'"
              binary
              :disabled="locked || (Boolean(store.picker) && slotProps.node.data.kind === 'folder')"
              :data-testid="`dataset-checkbox-${slotProps.node.data.record.id}`"
              :aria-label="`Select ${slotProps.node.label}`"
              @click.stop
              @update:model-value="setNodeSelected(slotProps.node, $event)"
            />
            <i :class="slotProps.node.data.kind === 'folder' ? 'pi pi-folder' : 'pi pi-file'" aria-hidden="true" />
            <span
              class="dataset-node-label"
              :data-dataset-id="slotProps.node.data.record.id"
              :title="nodeTitle(slotProps.node)"
            >{{ slotProps.node.label }}</span>
          </span>
        </template>
        <template #empty>No datasets found.</template>
      </Tree>
    </div>

    <div class="dataset-footer">
      <span data-testid="dataset-selection-summary" :data-selected-ids="selectedNodeIds.join(',')">{{ selectionSummary }}</span>
      <template v-if="store.picker">
        <Button label="Cancel" text @click="store.finishPicker(null)" />
        <Button label="Use file" :disabled="!store.pickerSelectionId" @click="finishPicker" />
      </template>
      <Button
        v-else
        data-testid="dataset-create-files-node"
        label="Create Files node"
        icon="pi pi-plus"
        :disabled="locked || selectedNodes.length === 0"
        @click="createFilesNode"
      />
      <Button
        v-if="!store.picker && selectedFilesNode"
        data-testid="dataset-set-files-node"
        :label="`Set files on “${selectedFilesNode.name}”`"
        icon="pi pi-check"
        :disabled="locked || selectedNodes.length === 0"
        @click="setSelectedFilesNode"
      />
    </div>

    <Dialog v-model:visible="editorVisible" modal :header="editorMode === 'add' ? 'Add folder' : 'Rename'">
      <label class="dialog-field">
        <span>Name</span>
        <InputText v-model="editorName" autofocus @keyup.enter="saveEditor" />
      </label>
      <small v-if="actionError" class="action-error">{{ actionError }}</small>
      <template #footer>
        <Button label="Cancel" text @click="editorVisible = false" />
        <Button label="Save" :disabled="!editorName.trim() || actionBusy" @click="saveEditor" />
      </template>
    </Dialog>

    <Dialog v-model:visible="deleteVisible" modal header="Delete selected datasets">
      <p v-if="deletePreview">
        Delete {{ deletePreview.dataset_count }} file(s) and {{ deletePreview.folder_count }} folder(s)?
        Folder contents are included.
      </p>
      <p v-else>Calculating the affected files and folders…</p>
      <small v-if="actionError" class="action-error">{{ actionError }}</small>
      <template #footer>
        <Button label="Cancel" text @click="deleteVisible = false" />
        <Button label="Delete" severity="danger" :disabled="!deletePreview || actionBusy" @click="deleteConfirmed" />
      </template>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import ProgressBar from 'primevue/progressbar'
import Tree from 'primevue/tree'
import type { TreeNodeDropEvent } from 'primevue/tree'
import type { TreeNode } from 'primevue/treenode'
import {
  createDatasetFolder,
  deleteDatasetSelection,
  previewDatasetDelete,
  resolveDatasetSelection,
  updateDataset,
  updateDatasetFolder,
  type DatasetFolderRecord,
  type DatasetRecord,
} from '@/api/datasets'
import { useCanvasCommands } from '@/composables/useCanvasCommands'
import { useExecutionLock } from '@/composables/useExecutionLock'
import { useDatasetsStore, type UploadEntry } from '@/stores/datasets'
import { useUIStore } from '@/stores/ui'
import {
  DATASET_TREE_DRAG_MIME,
  encodeDatasetTreeDrag,
} from '@/utils/datasetDrag'

type NodeData =
  | { kind: 'dataset'; record: DatasetRecord }
  | { kind: 'folder'; record: DatasetFolderRecord }

type DatasetTreeNode = Omit<TreeNode, 'key' | 'data' | 'children'> & {
  key: string
  data: NodeData
  children?: DatasetTreeNode[]
}
type DatasetSelectionState = 'none' | 'partial' | 'all'

const store = useDatasetsStore()
const uiStore = useUIStore()
const commands = useCanvasCommands()
const { isLocked: locked } = useExecutionLock()
const query = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const editorVisible = ref(false)
const editorMode = ref<'add' | 'rename'>('add')
const editorName = ref('')
const actionBusy = ref(false)
const actionError = ref('')
const treeActionError = ref('')
const deleteVisible = ref(false)
const deletePreview = ref<Awaited<ReturnType<typeof previewDatasetDelete>> | null>(null)
const expandedKeys = ref<Record<string, boolean>>({})

const nodeMap = computed(() => {
  const map = new Map<string, DatasetTreeNode>()
  for (const folder of store.folders) {
    map.set(folder.id, { key: folder.id, label: folder.name, data: { kind: 'folder', record: folder }, children: [] })
  }
  for (const dataset of store.datasets) {
    map.set(dataset.id, { key: dataset.id, label: dataset.display_name, leaf: true, data: { kind: 'dataset', record: dataset } })
  }
  return map
})

const allNodes = computed(() => {
  const roots: DatasetTreeNode[] = []
  for (const folder of store.folders) {
    const node = nodeMap.value.get(folder.id)!
    const parent = folder.parent_id ? nodeMap.value.get(folder.parent_id) : undefined
    if (parent?.data.kind === 'folder') parent.children!.push(node)
    else roots.push(node)
  }
  for (const dataset of store.datasets) {
    const node = nodeMap.value.get(dataset.id)!
    const parent = dataset.folder_id ? nodeMap.value.get(dataset.folder_id) : undefined
    if (parent?.data.kind === 'folder') parent.children!.push(node)
    else roots.push(node)
  }
  const sortNodes = (nodes: DatasetTreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.data.kind !== b.data.kind) return a.data.kind === 'folder' ? -1 : 1
      return String(a.label).localeCompare(String(b.label), undefined, { sensitivity: 'base' })
    })
    nodes.forEach(node => node.children && sortNodes(node.children))
  }
  sortNodes(roots)
  return roots
})

const visibleNodes = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase()
  const filter = (nodes: DatasetTreeNode[]): DatasetTreeNode[] => nodes.flatMap(node => {
    const children = filter(node.children ?? [])
    const haystack = node.data.kind === 'dataset'
      ? `${node.data.record.display_name} ${node.data.record.original_filename} ${folderPath(node.data.record.folder_id)}`
      : folderPath(node.data.record.id)
    const searchMatches = !needle || haystack.toLocaleLowerCase().includes(needle)
    const pickerMatches = node.data.kind === 'folder' || matchesPickerTypes(node.data.record)
    if ((!searchMatches || !pickerMatches) && children.length === 0) return []
    return [{ ...node, children }]
  })
  return filter(allNodes.value)
})

const selectedNodes = computed(() => Object.entries(store.selectionKeys)
  .filter(([, selected]) => selected)
  .map(([id]) => nodeMap.value.get(id))
  .filter((node): node is DatasetTreeNode => Boolean(node)))

const selectedRootNodes = computed(() => {
  const selectedIds = new Set(selectedNodes.value.map(node => node.key))
  return selectedNodes.value.filter(node => !hasSelectedFolderAncestor(node, selectedIds))
})

const selectedNodeIds = computed(() => selectedNodes.value.map(node => node.key))

const selectedFilesNode = computed(() => {
  if (!uiStore.isSingleSelection) return null
  const nodeId = uiStore.selectedNodeIds[0]
  const node = uiStore.graphNodes.find(item => item.id === nodeId)
  if (String(node?.data?.toolName ?? '').toLocaleLowerCase() !== 'files') return null
  return { id: nodeId, name: String(node.data?.name ?? nodeId) }
})

const selectionSummary = computed(() => {
  if (store.picker) return store.pickerSelectionId ? '1 file selected' : 'Select one file'
  const count = selectedNodes.value.length
  return `${count} item${count === 1 ? '' : 's'} selected`
})

const uploadFolderId = computed(() => {
  if (selectedRootNodes.value.length !== 1) return null
  const node = selectedRootNodes.value[0]
  if (node.data.kind === 'folder') return node.data.record.id
  return node.data.record.folder_id
})

const treePassThrough = {
  nodeContent: ({ context }: { context: { node: DatasetTreeNode } }) => ({
    'data-dataset-tree-id': context.node.key,
  }),
}

onMounted(() => { void store.refresh() })

watch(
  () => [query.value, visibleNodes.value] as const,
  ([search, nodes]) => {
    if (!search.trim()) return
    const next = { ...expandedKeys.value }
    const expandParents = (items: DatasetTreeNode[]) => {
      for (const node of items) {
        if (node.data.kind === 'folder' && (node.children?.length ?? 0) > 0) {
          next[node.key] = true
          expandParents(node.children ?? [])
        }
      }
    }
    expandParents(nodes)
    expandedKeys.value = next
  },
)

function message(error: unknown): string {
  if (typeof error === 'object' && error && 'response' in error) {
    const detail = (error as { response?: { data?: { detail?: string | { detail?: string } } } }).response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail?.detail) return detail.detail
  }
  return error instanceof Error ? error.message : 'The operation failed'
}

function uploadLabel(upload: UploadEntry): string {
  if (upload.status === 'queued') return 'Queued'
  if (upload.status === 'uploading') return `${Math.round((upload.loaded / Math.max(upload.total, 1)) * 100)}%`
  return upload.message ?? upload.status
}

function folderPath(folderId: string | null): string {
  const parts: string[] = []
  const visited = new Set<string>()
  while (folderId && !visited.has(folderId)) {
    visited.add(folderId)
    const folder = store.folders.find(item => item.id === folderId)
    if (!folder) break
    parts.unshift(folder.name)
    folderId = folder.parent_id
  }
  return parts.join('/')
}

function matchesPickerTypes(dataset: DatasetRecord): boolean {
  const patterns = store.picker?.fileTypes ?? []
  if (!patterns.length) return true
  const name = dataset.original_filename.toLocaleLowerCase()
  return patterns.some(pattern => {
    const normalized = pattern.toLocaleLowerCase().replace(/^\*+/, '')
    return !normalized || name.endsWith(normalized)
  })
}

function onFilesChosen(event: Event) {
  const input = event.target as HTMLInputElement
  store.queueUploads(Array.from(input.files ?? []), uploadFolderId.value)
  input.value = ''
}

function parentFolderId(node: DatasetTreeNode): string | null {
  return node.data.kind === 'folder'
    ? node.data.record.parent_id
    : node.data.record.folder_id
}

function hasSelectedFolderAncestor(
  node: DatasetTreeNode,
  selectedIds: Set<string>,
): boolean {
  const visited = new Set<string>()
  let folderId = parentFolderId(node)
  while (folderId && !visited.has(folderId)) {
    if (selectedIds.has(folderId)) return true
    visited.add(folderId)
    const folder = store.folders.find(item => item.id === folderId)
    folderId = folder?.parent_id ?? null
  }
  return false
}

function canonicalNode(treeNode: TreeNode): DatasetTreeNode {
  void allNodes.value
  const node = treeNode as DatasetTreeNode
  return nodeMap.value.get(node.key) ?? node
}

function subtreeKeys(treeNode: TreeNode): string[] {
  const keys: string[] = []
  const visit = (node: DatasetTreeNode) => {
    keys.push(node.key)
    node.children?.forEach(visit)
  }
  visit(canonicalNode(treeNode))
  return keys
}

function nodeSelectionState(treeNode: TreeNode): DatasetSelectionState {
  const keys = subtreeKeys(treeNode)
  const selectedCount = keys.filter(key => store.selectionKeys[key] === true).length
  if (selectedCount === 0) return 'none'
  return selectedCount === keys.length ? 'all' : 'partial'
}

function ancestorFolderIds(node: DatasetTreeNode): string[] {
  const ids: string[] = []
  const visited = new Set<string>()
  let folderId = parentFolderId(node)
  while (folderId && !visited.has(folderId)) {
    ids.push(folderId)
    visited.add(folderId)
    const folder = store.folders.find(item => item.id === folderId)
    folderId = folder?.parent_id ?? null
  }
  return ids
}

function setNodeSelected(treeNode: TreeNode, selected: boolean) {
  if (locked.value) return
  const node = canonicalNode(treeNode)
  if (store.picker) {
    if (node.data.kind === 'folder') return
    store.pickerSelectionId = selected ? node.key : null
    store.selectionKeys = selected ? { [node.key]: true } : {}
    return
  }
  const next = { ...store.selectionKeys }
  for (const key of subtreeKeys(node)) {
    if (selected) next[key] = true
    else delete next[key]
  }
  if (!selected) {
    for (const folderId of ancestorFolderIds(node)) delete next[folderId]
  }
  store.selectionKeys = next
}

function dragNodes(treeNode: TreeNode): DatasetTreeNode[] {
  const node = canonicalNode(treeNode)
  return store.selectionKeys[node.key] === true
    ? selectedRootNodes.value
    : [node]
}

function pathsForNodes(nodes: DatasetTreeNode[]): string[] {
  const selectedIds = new Set(nodes.map(node => node.key))
  const paths: string[] = []
  const visit = (node: DatasetTreeNode, ancestorSelected = false) => {
    const selected = ancestorSelected || selectedIds.has(node.key)
    if (node.data.kind === 'dataset' && selected) paths.push(node.data.record.path)
    node.children?.forEach(child => visit(child, selected))
  }
  allNodes.value.forEach(node => visit(node))
  return paths
}

function onDatasetDragStart(event: DragEvent, treeNode: TreeNode): void {
  const paths = pathsForNodes(dragNodes(treeNode))
  if (paths.length === 0) return
  event.dataTransfer?.setData(
    DATASET_TREE_DRAG_MIME,
    encodeDatasetTreeDrag(paths),
  )
}

function onTreeDragStart(event: DragEvent): void {
  const target = event.target
  if (!(target instanceof Element)) return
  const content = target.closest<HTMLElement>('[data-dataset-tree-id]')
  if (!content) return
  const node = nodeMap.value.get(content.dataset.datasetTreeId ?? '')
  if (node) onDatasetDragStart(event, node)
}

function clearSelection() {
  store.selectionKeys = {}
  store.pickerSelectionId = null
}

function finishPicker() {
  const dataset = store.datasets.find(item => item.id === store.pickerSelectionId)
  store.finishPicker(dataset?.path ?? null)
}

function openAddFolder() {
  editorMode.value = 'add'
  editorName.value = ''
  actionError.value = ''
  editorVisible.value = true
}

function openRename() {
  const node = selectedRootNodes.value[0]
  if (!node) return
  editorMode.value = 'rename'
  editorName.value = String(node.label)
  actionError.value = ''
  editorVisible.value = true
}

function newFolderParent(): string | null {
  if (selectedRootNodes.value.length !== 1) return null
  const node = selectedRootNodes.value[0]
  return node.data.kind === 'folder' ? node.data.record.id : node.data.record.folder_id
}

async function saveEditor() {
  const name = editorName.value.trim()
  if (!name) return
  actionBusy.value = true
  actionError.value = ''
  try {
    if (editorMode.value === 'add') {
      await createDatasetFolder(name, newFolderParent())
    } else {
      const node = selectedRootNodes.value[0]
      if (!node) return
      if (node.data.kind === 'folder') await updateDatasetFolder(node.key, { name })
      else await updateDataset(node.key, { display_name: name })
    }
    await store.refresh()
    editorVisible.value = false
  } catch (error) {
    actionError.value = message(error)
  } finally {
    actionBusy.value = false
  }
}

async function confirmDelete() {
  actionError.value = ''
  deletePreview.value = null
  deleteVisible.value = true
  try {
    deletePreview.value = await previewDatasetDelete(store.selectedIds())
  } catch (error) {
    actionError.value = message(error)
  }
}

async function deleteConfirmed() {
  if (!deletePreview.value) return
  actionBusy.value = true
  actionError.value = ''
  try {
    const result = await deleteDatasetSelection(store.selectedIds(), deletePreview.value.revision)
    if (result.errors.length) actionError.value = result.errors.map(item => item.detail).join('; ')
    clearSelection()
    await store.refresh()
    if (!result.errors.length) deleteVisible.value = false
  } catch (error) {
    actionError.value = message(error)
  } finally {
    actionBusy.value = false
  }
}

function folderIsWithin(folderId: string | null, ancestorId: string): boolean {
  const visited = new Set<string>()
  while (folderId && !visited.has(folderId)) {
    if (folderId === ancestorId) return true
    visited.add(folderId)
    const folder = store.folders.find(item => item.id === folderId)
    folderId = folder?.parent_id ?? null
  }
  return false
}

function isDropInsideNode(event: DragEvent): boolean {
  const target = event.target
  if (!(target instanceof Element)) return true
  const content = target.closest('.p-tree-node-content, .p-treenode-content')
  if (!(content instanceof HTMLElement)) return true
  const rect = content.getBoundingClientRect()
  if (rect.height <= 0) return true
  const offset = event.clientY - rect.top
  return offset >= rect.height * 0.25 && offset <= rect.height * 0.75
}

function dropFolderId(event: TreeNodeDropEvent): string | null {
  const dropNode = event.dropNode as DatasetTreeNode | null | undefined
  if (!dropNode) return null
  if (
    dropNode.data.kind === 'folder'
    && isDropInsideNode(event.originalEvent as DragEvent)
  ) {
    return dropNode.key
  }
  return parentFolderId(dropNode)
}

async function moveNodes(nodes: DatasetTreeNode[], folderId: string | null) {
  for (const node of nodes) {
    if (node.data.kind === 'folder' && folderIsWithin(folderId, node.key)) {
      throw new Error(`Cannot move “${node.label}” into itself or one of its subfolders.`)
    }
  }
  const changed = nodes.filter(node => parentFolderId(node) !== folderId)
  if (changed.length === 0) return
  try {
    await Promise.all(changed.map(node => (
      node.data.kind === 'folder'
        ? updateDatasetFolder(node.key, { parent_id: folderId })
        : updateDataset(node.key, { folder_id: folderId })
    )))
  } finally {
    await store.refresh()
  }
}

function onNodeDrop(event: TreeNodeDropEvent) {
  const dragNode = event.dragNode as DatasetTreeNode
  if (locked.value || !dragNode) return
  treeActionError.value = ''
  const nodes = dragNodes(dragNode)
  void moveNodes(nodes, dropFolderId(event)).catch(error => {
    treeActionError.value = message(error)
  })
}

async function resolvedSelectedPaths(): Promise<string[]> {
  const datasets = await resolveDatasetSelection(store.selectedIds())
  return datasets.map(dataset => dataset.path)
}

async function createFilesNode() {
  actionError.value = ''
  try {
    commands.addToolNode('Files', { files: await resolvedSelectedPaths() })
  } catch (error) {
    actionError.value = message(error)
  }
}

async function setSelectedFilesNode() {
  const node = selectedFilesNode.value
  if (!node) return
  actionError.value = ''
  try {
    const files = await resolvedSelectedPaths()
    commands.updateParameter(node.id, 'path', null)
    commands.updateParameter(node.id, 'files', files)
  } catch (error) {
    actionError.value = message(error)
  }
}

function nodeTitle(treeNode: TreeNode): string {
  const node = treeNode as DatasetTreeNode
  if (node.data.kind === 'folder') return node.data.record.name
  return node.data.record.original_filename === node.data.record.display_name
    ? node.data.record.path
    : `${node.data.record.original_filename}\n${node.data.record.path}`
}
</script>

<style scoped>
.datasets-panel { display: flex; flex-direction: column; gap: .75rem; height: 100%; padding: .75rem; overflow: hidden; }
.sr-only { position: absolute; width: 1px; height: 1px; clip: rect(0, 0, 0, 0); overflow: hidden; }
.upload-status { display: grid; gap: .35rem; }
.upload-progress-row { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
.upload-progress-row :deep(.p-progressbar) { flex: 1; min-width: 4rem; }
.upload-progress-actions, .upload-message-actions { display: flex; align-items: center; gap: .15rem; }
.upload-messages { display: grid; gap: .35rem; max-height: 10rem; overflow: auto; }
.upload-message { display: flex; align-items: center; justify-content: space-between; font-size: .8rem; }
.upload-message > span { min-width: 0; overflow-wrap: anywhere; }
.upload-message-actions { flex-shrink: 0; }
.upload-message.error, .action-error { color: var(--p-red-500); }
.upload-message.success { color: var(--p-green-500); }
.upload-message.cancelled { color: var(--p-text-muted-color); }
.dataset-search { width: 100%; }
.dataset-toolbar, .dataset-selection-actions, .dataset-footer { display: flex; align-items: center; flex-wrap: wrap; }
.dataset-toolbar { gap: .25rem; }
.dataset-selection-actions { justify-content: flex-start; }
.dataset-tree-wrap { flex: 1; min-height: 0; overflow: auto; }
.dataset-tree { padding: 0; }
.dataset-tree :deep(.p-tree-node-content),
.dataset-tree :deep(.p-treenode-content) { padding: .1rem .15rem; }
.dataset-node { display: inline-flex; align-items: center; gap: .45rem; min-width: 0; }
.dataset-node-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dataset-footer { justify-content: flex-end; }
.dataset-footer > span { margin-right: auto; color: var(--p-text-muted-color); font-size: .8rem; }
.dialog-field { display: grid; gap: .4rem; min-width: 20rem; }
</style>
