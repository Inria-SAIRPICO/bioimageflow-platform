<template>
  <section class="datasets-panel">
    <input ref="fileInput" class="sr-only" type="file" multiple @change="onFilesChosen">
    <Button label="Upload files" icon="pi pi-upload" :disabled="locked" @click="fileInput?.click()" />

    <div v-if="store.uploads.length" class="upload-status" aria-live="polite">
      <ProgressBar :value="store.progress" />
      <div v-for="upload in store.uploads" :key="upload.id" class="upload-message" :class="upload.status">
        <span>{{ upload.file.name }} — {{ uploadLabel(upload) }}</span>
        <Button
          v-if="upload.status === 'error'"
          label="Retry"
          text
          size="small"
          @click="store.retryUpload(upload, uploadFolderId)"
        />
      </div>
    </div>

    <InputText v-model="query" class="dataset-search" placeholder="Search files and folders" />

    <div class="dataset-toolbar">
      <Button data-testid="dataset-add-folder" label="Add folder" icon="pi pi-folder-plus" :disabled="locked" @click="openAddFolder" />
      <Button data-testid="dataset-rename" label="Rename" icon="pi pi-pencil" :disabled="locked || selectedNodes.length !== 1" @click="openRename" />
      <Button data-testid="dataset-delete" label="Delete" icon="pi pi-trash" severity="danger" :disabled="locked || selectedNodes.length === 0" @click="confirmDelete" />
    </div>

    <div class="root-drop-zone" @dragover.prevent @drop="dropAtRoot">Move to top level</div>
    <Tree
      v-model:selectionKeys="store.selectionKeys"
      :value="visibleNodes"
      selection-mode="multiple"
      :meta-key-selection="false"
      draggable-nodes
      droppable-nodes
      class="dataset-tree"
      @dragstart.capture="rememberTreeDrag"
      @node-select="onNodeSelect"
      @node-unselect="onNodeUnselect"
      @node-drop="onNodeDrop"
    >
      <template #default="slotProps">
        <span
          class="dataset-node-label"
          :data-dataset-id="slotProps.node.data.record.id"
          :title="nodeTitle(slotProps.node)"
        >{{ slotProps.node.label }}</span>
      </template>
      <template #empty>No datasets found.</template>
    </Tree>

    <div class="dataset-footer">
      <span data-testid="dataset-selection-summary" :data-selected-ids="Object.keys(store.selectionKeys).join(',')">{{ selectionSummary }}</span>
      <template v-if="store.picker">
        <Button label="Cancel" text @click="store.finishPicker(null)" />
        <Button label="Use file" :disabled="!store.pickerSelectionId" @click="finishPicker" />
      </template>
      <Button
        v-else
        data-testid="dataset-create-files-node"
        label="Create Files node from selection"
        icon="pi pi-plus"
        :disabled="locked || selectedNodes.length === 0"
        @click="createFilesNode"
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
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
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

type NodeData =
  | { kind: 'dataset'; record: DatasetRecord }
  | { kind: 'folder'; record: DatasetFolderRecord }

type DatasetTreeNode = TreeNode & { key: string; data: NodeData; children?: DatasetTreeNode[] }

const store = useDatasetsStore()
const commands = useCanvasCommands()
const { isLocked: locked } = useExecutionLock()
const query = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const editorVisible = ref(false)
const editorMode = ref<'add' | 'rename'>('add')
const editorName = ref('')
const actionBusy = ref(false)
const actionError = ref('')
const deleteVisible = ref(false)
const deletePreview = ref<Awaited<ReturnType<typeof previewDatasetDelete>> | null>(null)

const nodeMap = computed(() => {
  const map = new Map<string, DatasetTreeNode>()
  for (const folder of store.folders) {
    map.set(folder.id, { key: folder.id, label: folder.name, icon: 'pi pi-folder', data: { kind: 'folder', record: folder }, children: [] })
  }
  for (const dataset of store.datasets) {
    map.set(dataset.id, { key: dataset.id, label: dataset.display_name, icon: 'pi pi-file', leaf: true, data: { kind: 'dataset', record: dataset } })
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
    const record = node.data.record
    const haystack = node.data.kind === 'dataset'
      ? `${record.display_name} ${record.original_filename} ${folderPath(record.folder_id)}`
      : folderPath(record.id)
    const searchMatches = !needle || haystack.toLocaleLowerCase().includes(needle)
    const pickerMatches = node.data.kind === 'folder' || matchesPickerTypes(record)
    if ((!searchMatches || !pickerMatches) && children.length === 0) return []
    return [{ ...node, children }]
  })
  return filter(allNodes.value)
})

const selectedNodes = computed(() => Object.entries(store.selectionKeys)
  .filter(([, selected]) => selected)
  .map(([id]) => nodeMap.value.get(id))
  .filter((node): node is DatasetTreeNode => Boolean(node)))

const selectionSummary = computed(() => {
  if (store.picker) return store.pickerSelectionId ? '1 file selected' : 'Select one file'
  const count = selectedNodes.value.length
  return `${count} item${count === 1 ? '' : 's'} selected`
})

const uploadFolderId = computed(() => {
  if (selectedNodes.value.length !== 1) return null
  const node = selectedNodes.value[0]
  if (node.data.kind === 'folder') return node.data.record.id
  return node.data.record.folder_id
})

onMounted(() => { void store.refresh() })

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

function onNodeSelect(treeNode: TreeNode) {
  if (!store.picker) return
  const node = treeNode as DatasetTreeNode
  const id = node.data.record.id
  store.pickerSelectionId = node.data.kind === 'dataset' ? id : null
  store.selectionKeys = store.pickerSelectionId ? { [store.pickerSelectionId]: true } : {}
}

function onNodeUnselect(treeNode: TreeNode) {
  if (!store.picker) return
  const id = (treeNode as DatasetTreeNode).data.record.id
  if (store.pickerSelectionId === id) store.pickerSelectionId = null
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
  const node = selectedNodes.value[0]
  if (!node) return
  editorMode.value = 'rename'
  editorName.value = String(node.label)
  actionError.value = ''
  editorVisible.value = true
}

function newFolderParent(): string | null {
  if (selectedNodes.value.length !== 1) return null
  const node = selectedNodes.value[0]
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
      const node = selectedNodes.value[0]
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
    store.selectionKeys = {}
    await store.refresh()
    if (!result.errors.length) deleteVisible.value = false
  } catch (error) {
    actionError.value = message(error)
  } finally {
    actionBusy.value = false
  }
}

async function moveNode(node: DatasetTreeNode, folderId: string | null) {
  if (node.data.kind === 'folder') {
    if (node.key === folderId) return
    await updateDatasetFolder(node.key, { parent_id: folderId })
  } else {
    await updateDataset(node.key, { folder_id: folderId })
  }
  await store.refresh()
}

function onNodeDrop(event: TreeNodeDropEvent) {
  const dragNode = event.dragNode as DatasetTreeNode
  const dropNode = event.dropNode as DatasetTreeNode
  if (locked.value || !dragNode || dropNode?.data.kind !== 'folder') return
  void moveNode(dragNode, dropNode.key).catch(error => { actionError.value = message(error) })
}

function rememberTreeDrag(event: DragEvent) {
  const row = (event.target as HTMLElement | null)?.closest('[role="treeitem"]')
  const id = row?.querySelector<HTMLElement>('[data-dataset-id]')?.dataset.datasetId
  if (id) event.dataTransfer?.setData('text/plain', id)
}

function dropAtRoot(event: DragEvent) {
  if (locked.value) return
  const id = event.dataTransfer?.getData('text/plain')
  const node = id ? nodeMap.value.get(id) : undefined
  if (node) void moveNode(node, null).catch(error => { actionError.value = message(error) })
}

async function createFilesNode() {
  actionError.value = ''
  try {
    const datasets = await resolveDatasetSelection(store.selectedIds())
    commands.addToolNode('Files', { files: datasets.map(dataset => dataset.path) })
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
.upload-message { display: flex; align-items: center; justify-content: space-between; font-size: .8rem; }
.upload-message.error, .action-error { color: var(--p-red-500); }
.upload-message.success { color: var(--p-green-500); }
.dataset-search { width: 100%; }
.dataset-toolbar, .dataset-footer { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
.root-drop-zone { padding: .3rem; border: 1px dashed var(--p-surface-400); border-radius: .25rem; text-align: center; color: var(--p-text-muted-color); font-size: .75rem; }
.dataset-tree { flex: 1; min-height: 0; overflow: auto; }
.dataset-node-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dataset-footer { justify-content: flex-end; }
.dataset-footer > span { margin-right: auto; color: var(--p-text-muted-color); font-size: .8rem; }
.dialog-field { display: grid; gap: .4rem; min-width: 20rem; }
</style>
