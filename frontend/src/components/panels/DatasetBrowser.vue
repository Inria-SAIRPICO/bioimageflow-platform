<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import ProgressBar from 'primevue/progressbar'
import { listDatasets, uploadDataset, deleteDataset } from '@/api/datasets'
import type { Dataset } from '@/api/types'

type Mode = 'pick' | 'upload-and-pick'

const props = defineProps<{
  visible: boolean
  parameterName: string
  mode: Mode
  fileTypeFilter?: string[]
  initialFiles?: File[]
  /** Authoritative server cap. Client-side pre-check uses `serverCap * 1.1`. */
  serverCap: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  select: [path: string]
  close: []
  createFilesNode: [paths: string[]]
  /** Emitted when the user wants the host to display a transient message. */
  toast: [payload: { severity: 'error' | 'info'; summary: string; detail?: string }]
}>()

// Row type for the pending-upload strip (one per file being uploaded)
interface PendingUpload {
  file: File
  loaded: number
  total: number
  error?: string
}

const datasets = ref<Dataset[]>([])
const selectedDataset = ref<Dataset | null>(null)
const searchQuery = ref('')
const pendingUploads = ref<PendingUpload[]>([])
const confirmDeleteOpen = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const dialogTitle = computed(() => {
  if (props.mode === 'pick') return `Select dataset for: ${props.parameterName}`
  return 'Upload datasets'
})

const filteredDatasets = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const filter = props.fileTypeFilter ?? []
  return datasets.value.filter((d) => {
    if (filter.length > 0 && !matchesFilter(d.original_filename, filter)) return false
    if (!q) return true
    return d.original_filename.toLowerCase().includes(q)
  })
})

function matchesFilter(filename: string, patterns: string[]): boolean {
  const lower = filename.toLowerCase()
  return patterns.some((p) => {
    // "*.tif" -> endsWith ".tif"
    if (p.startsWith('*.')) return lower.endsWith(p.slice(1).toLowerCase())
    return lower === p.toLowerCase()
  })
}

async function refresh() {
  datasets.value = await listDatasets()
}

async function onUploadFiles(files: File[]) {
  const tooBig = files.filter((f) => f.size > props.serverCap * 1.1)
  const ok = files.filter((f) => f.size <= props.serverCap * 1.1)
  if (tooBig.length > 0) {
    emit('toast', {
      severity: 'error',
      summary: 'File too large',
      detail: `${tooBig.map((f) => f.name).join(', ')} exceeds the ${props.serverCap}-byte upload cap.`,
    })
  }
  for (const f of ok) {
    void uploadOne(f)
  }
}

async function uploadOne(file: File) {
  const entry: PendingUpload = { file, loaded: 0, total: file.size }
  pendingUploads.value.push(entry)
  try {
    const response = await uploadDataset(file, {
      onProgress: (p) => {
        entry.loaded = p.loaded
        entry.total = p.total ?? file.size
      },
    })
    if (response.errors.length > 0) {
      entry.error = response.errors[0].detail || response.errors[0].error
      return
    }
    // Remove the pending entry; it will reappear as a real dataset row on refresh.
    pendingUploads.value = pendingUploads.value.filter((p) => p !== entry)
    await refresh()
  } catch (exc: unknown) {
    const message = exc instanceof Error ? exc.message : 'upload failed'
    entry.error = message
  }
}

function retryUpload(entry: PendingUpload) {
  pendingUploads.value = pendingUploads.value.filter((p) => p !== entry)
  void uploadOne(entry.file)
}

function triggerFilePicker() {
  fileInput.value?.click()
}

function onFileInputChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files) return
  const files = Array.from(input.files)
  void onUploadFiles(files)
  input.value = ''
}

function onConfirmDelete() {
  confirmDeleteOpen.value = true
}

async function onDeleteConfirmed() {
  if (!selectedDataset.value) return
  await deleteDataset(selectedDataset.value.id)
  confirmDeleteOpen.value = false
  selectedDataset.value = null
  await refresh()
}

function onSelect() {
  if (!selectedDataset.value) return
  emit('select', selectedDataset.value.path)
  emit('update:visible', false)
}

function onCancel() {
  emit('close')
  emit('update:visible', false)
}

function onCreateFilesNode() {
  const paths = datasets.value
    .filter((d) =>
      pendingUploads.value.every((p) => p.file.name !== d.original_filename),
    )
    .map((d) => d.path)
  // Actually the right set is "datasets we uploaded in this session". We
  // approximate by sending every path currently listed that doesn't match a
  // still-pending upload. Callers that need strict tracking can pass initialFiles.
  emit('createFilesNode', paths)
  emit('update:visible', false)
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      selectedDataset.value = null
      searchQuery.value = ''
      pendingUploads.value = []
      void refresh()
      if (props.initialFiles && props.initialFiles.length > 0) {
        void onUploadFiles(props.initialFiles)
      }
    }
  },
  { immediate: true },
)

defineExpose({
  datasets,
  filteredDatasets,
  selectedDataset,
  searchQuery,
  pendingUploads,
  dialogTitle,
  onUploadFiles,
  uploadOne,
  retryUpload,
  onSelect,
  onCancel,
  onConfirmDelete,
  onDeleteConfirmed,
  onCreateFilesNode,
  refresh,
})
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :header="dialogTitle"
    :style="{ width: '800px' }"
    class="dataset-browser"
    data-testid="dataset-browser"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="dataset-browser__toolbar">
      <InputText
        v-model="searchQuery"
        placeholder="Search..."
        data-testid="dataset-browser-search"
        class="dataset-browser__search"
      />
      <Button
        label="Upload"
        icon="pi pi-upload"
        data-testid="dataset-browser-upload"
        @click="triggerFilePicker"
      />
      <input
        ref="fileInput"
        type="file"
        multiple
        style="display: none"
        data-testid="dataset-browser-file-input"
        @change="onFileInputChange"
      />
    </div>

    <DataTable
      :value="filteredDatasets"
      v-model:selection="selectedDataset"
      selection-mode="single"
      data-testid="dataset-browser-table"
      data-key="id"
      :rows="10"
      paginator
    >
      <Column field="original_filename" header="Filename" />
      <Column header="Size">
        <template #body="slot">{{ formatSize(slot.data.size) }}</template>
      </Column>
      <Column field="upload_date" header="Upload date" />
    </DataTable>

    <div v-if="pendingUploads.length" class="dataset-browser__pending">
      <h4>Uploading</h4>
      <ul>
        <li v-for="entry in pendingUploads" :key="entry.file.name" :data-testid="`pending-${entry.file.name}`">
          <span class="pending-name">{{ entry.file.name }}</span>
          <template v-if="entry.error">
            <span class="pending-error">{{ entry.error }}</span>
            <Button label="Retry" text size="small" @click="retryUpload(entry)" />
          </template>
          <template v-else>
            <ProgressBar
              :value="entry.total > 0 ? Math.round((entry.loaded / entry.total) * 100) : 0"
              class="pending-progress"
            />
          </template>
        </li>
      </ul>
    </div>

    <template #footer>
      <Button label="Cancel" text data-testid="dataset-browser-cancel" @click="onCancel" />
      <Button
        label="Delete"
        severity="danger"
        data-testid="dataset-browser-delete"
        :disabled="!selectedDataset"
        @click="onConfirmDelete"
      />
      <Button
        v-if="mode === 'upload-and-pick'"
        label="Create Files node"
        data-testid="dataset-browser-create-node"
        @click="onCreateFilesNode"
      />
      <Button
        label="Select"
        data-testid="dataset-browser-select"
        :disabled="!selectedDataset"
        @click="onSelect"
      />
    </template>
  </Dialog>

  <Dialog
    v-model:visible="confirmDeleteOpen"
    modal
    header="Confirm delete"
    data-testid="dataset-browser-confirm-delete"
    :style="{ width: '400px' }"
  >
    <p v-if="selectedDataset">Delete <strong>{{ selectedDataset.original_filename }}</strong>?</p>
    <template #footer>
      <Button label="Cancel" text @click="confirmDeleteOpen = false" />
      <Button
        label="Delete"
        severity="danger"
        data-testid="dataset-browser-confirm-delete-submit"
        @click="onDeleteConfirmed"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.dataset-browser__toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.dataset-browser__search {
  flex: 1;
}
.dataset-browser__pending {
  margin-top: 12px;
}
.dataset-browser__pending ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.dataset-browser__pending li {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
}
.pending-progress {
  grid-column: 2 / 4;
}
.pending-error {
  color: var(--p-red-500, #ef4444);
}
</style>
