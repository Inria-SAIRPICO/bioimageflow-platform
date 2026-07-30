<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'
import { useWorkflowStore } from '@/stores/workflow'
import { revealPath, selectFolder } from '@/utils/nativeDialogs'

type ExportAction = 'workflow' | 'latest-results' | 'workflow-results' | 'folder'

const props = withDefaults(defineProps<{
  visible: boolean
  workflowName: string | null
  workflowDisplayName?: string | null
  desktop?: boolean
  workflowExportsDisabled?: boolean
  prepareWorkflowExport?: (workflowName: string) => Promise<string | null>
}>(), {
  workflowDisplayName: null,
  desktop: false,
  workflowExportsDisabled: false,
  prepareWorkflowExport: undefined,
})

const emit = defineEmits<{
  'update:visible': [visible: boolean]
}>()

const workflowStore = useWorkflowStore()
let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

const activeAction = ref<ExportAction | null>(null)
const errorMessage = ref<string | null>(null)
const exportedDestination = ref<string | null>(null)
const exportedItemCount = ref<number | null>(null)
let activeController: AbortController | null = null

const isBusy = computed(() => activeAction.value !== null)
const progressMessage = computed(() => {
  if (activeAction.value === 'folder') return 'Copying the latest results to a portable folder…'
  if (activeAction.value === 'workflow-results') return 'Preparing the workflow and successful-run bundle…'
  if (activeAction.value === 'workflow') return 'Preparing the workflow archive…'
  if (activeAction.value === 'latest-results') return 'Preparing the latest-results archive…'
  return null
})
const title = computed(() => (
  props.workflowDisplayName
    ? `Export ${props.workflowDisplayName}`
    : 'Export workflow'
))

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      errorMessage.value = null
      exportedDestination.value = null
      exportedItemCount.value = null
      return
    }
    activeController?.abort()
    activeController = null
    activeAction.value = null
  },
)

function setVisible(visible: boolean): void {
  if (!visible) activeController?.abort()
  emit('update:visible', visible)
}

function cancel(): void {
  activeController?.abort()
  emit('update:visible', false)
}

function responseStatus(error: unknown): number | null {
  return axios.isAxiosError(error) ? (error.response?.status ?? null) : null
}

interface ExportErrorIssue {
  status: number | null
  code: string | null
  detail: string | null
}

async function responseData(error: unknown): Promise<unknown> {
  if (!axios.isAxiosError(error)) return null
  const data = error.response?.data
  if (data instanceof Blob) {
    const text = await data.text()
    if (!text) return null
    try {
      return JSON.parse(text) as unknown
    } catch {
      return text
    }
  }
  return data
}

async function responseIssue(error: unknown): Promise<ExportErrorIssue> {
  const data = await responseData(error)
  if (typeof data === 'string') {
    return { status: responseStatus(error), code: null, detail: data }
  }
  if (!data || typeof data !== 'object' || !('detail' in data)) {
    return { status: responseStatus(error), code: null, detail: null }
  }
  const detail = data.detail
  if (typeof detail === 'string') {
    return { status: responseStatus(error), code: null, detail }
  }
  if (detail && typeof detail === 'object') {
    return {
      status: responseStatus(error),
      code: 'error' in detail && typeof detail.error === 'string' ? detail.error : null,
      detail: 'detail' in detail && typeof detail.detail === 'string' ? detail.detail : null,
    }
  }
  return { status: responseStatus(error), code: null, detail: null }
}

async function actionError(error: unknown): Promise<string> {
  const issue = await responseIssue(error)
  if (issue.status === 404) {
    return 'This workflow no longer exists. Close this dialog, refresh the workflow list, and try again.'
  }
  if (issue.detail) return issue.detail
  if (error instanceof Error && error.message) return error.message
  return 'The export could not be created. Check that the workflow still exists and try again.'
}

async function runAction(
  action: ExportAction,
  operation: (signal: AbortSignal) => Promise<void>,
): Promise<void> {
  if (isBusy.value || !props.workflowName) return
  errorMessage.value = null
  exportedDestination.value = null
  exportedItemCount.value = null
  activeAction.value = action
  const controller = new AbortController()
  activeController = controller
  try {
    await operation(controller.signal)
  } catch (error: unknown) {
    if (!axios.isCancel(error) && !controller.signal.aborted) {
      errorMessage.value = await actionError(error)
    }
  } finally {
    if (activeController === controller) {
      activeController = null
      activeAction.value = null
    }
  }
}

async function preparedWorkflowName(): Promise<string | null> {
  if (!props.workflowName || props.workflowExportsDisabled) return null
  return props.prepareWorkflowExport
    ? props.prepareWorkflowExport(props.workflowName)
    : props.workflowName
}

function exportWorkflowOnly(): void {
  void runAction('workflow', async (signal) => {
    const name = await preparedWorkflowName()
    if (!name || signal.aborted) return
    await workflowStore.exportWorkflow(name, signal)
    if (!signal.aborted) setVisible(false)
  })
}

function exportLatestResults(): void {
  void runAction('latest-results', async (signal) => {
    await workflowStore.exportLatestResults(props.workflowName!, signal)
    if (!signal.aborted) setVisible(false)
  })
}

function exportWorkflowWithResults(): void {
  void runAction('workflow-results', async (signal) => {
    const name = await preparedWorkflowName()
    if (!name || signal.aborted) return
    await workflowStore.exportWorkflowRunBundle(name, signal)
    if (!signal.aborted) setVisible(false)
  })
}

function exportLatestResultsToFolder(): void {
  void runAction('folder', async (signal) => {
    const parent = await selectFolder('Choose where to export latest results')
    if (!parent || signal.aborted) return

    let result
    try {
      result = await workflowStore.exportLatestResultsToFolder(
        props.workflowName!,
        parent,
        false,
        signal,
      )
    } catch (error: unknown) {
      const issue = await responseIssue(error)
      if (
        issue.status !== 409
        || issue.code !== 'export_destination_exists'
        || signal.aborted
      ) {
        throw error
      }
      const replace = window.confirm(
        'The destination folder already exists. Replace it with a fresh export of the latest results?',
      )
      if (!replace || signal.aborted) return
      result = await workflowStore.exportLatestResultsToFolder(
        props.workflowName!,
        parent,
        true,
        signal,
      )
    }

    exportedDestination.value = result.destination
    exportedItemCount.value = result.exported_items
    toast?.add({
      severity: 'success',
      summary: 'Latest results exported',
      detail: result.destination,
      life: 4000,
    })
  })
}

async function revealExport(): Promise<void> {
  if (!exportedDestination.value) return
  try {
    await revealPath(exportedDestination.value)
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error
      ? error.message
      : 'The exported folder could not be revealed.'
  }
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :header="title"
    :closable="!isBusy"
    :close-on-escape="!isBusy"
    :style="{ width: 'min(620px, 94vw)' }"
    data-testid="workflow-export-dialog"
    @update:visible="setVisible"
  >
    <p class="workflow-export-dialog__intro">
      Choose what you want to take out of BioImageFlow.
    </p>

    <div class="workflow-export-dialog__choices">
      <button
        type="button"
        class="workflow-export-dialog__choice"
        :disabled="isBusy || workflowExportsDisabled"
        data-testid="export-workflow-only"
        @click="exportWorkflowOnly"
      >
        <i class="pi pi-file-export" aria-hidden="true" />
        <span>
          <strong>Workflow only</strong>
          <small>Saves any unsaved workflow changes, then downloads a reusable workflow archive without results.</small>
        </span>
        <i v-if="activeAction === 'workflow'" class="pi pi-spinner pi-spin" aria-hidden="true" />
      </button>

      <button
        type="button"
        class="workflow-export-dialog__choice"
        :disabled="isBusy"
        data-testid="export-latest-results"
        @click="exportLatestResults"
      >
        <i class="pi pi-images" aria-hidden="true" />
        <span>
          <strong>Latest results</strong>
          <small>Downloads the human-friendly latest output from each node. These outputs may come from different workflow runs.</small>
        </span>
        <i v-if="activeAction === 'latest-results'" class="pi pi-spinner pi-spin" aria-hidden="true" />
      </button>

      <button
        type="button"
        class="workflow-export-dialog__choice"
        :disabled="isBusy || workflowExportsDisabled"
        data-testid="export-workflow-with-results"
        @click="exportWorkflowWithResults"
      >
        <i class="pi pi-box" aria-hidden="true" />
        <span>
          <strong>Workflow with results</strong>
          <small>Saves any unsaved workflow changes, then downloads the workflow with outputs and provenance from one latest successful run.</small>
        </span>
        <i v-if="activeAction === 'workflow-results'" class="pi pi-spinner pi-spin" aria-hidden="true" />
      </button>

      <button
        v-if="desktop"
        type="button"
        class="workflow-export-dialog__choice"
        :disabled="isBusy"
        data-testid="export-latest-results-folder"
        @click="exportLatestResultsToFolder"
      >
        <i class="pi pi-folder-open" aria-hidden="true" />
        <span>
          <strong>Export latest results to folder</strong>
          <small>Choose a parent folder. BioImageFlow creates a named child folder containing real, portable files.</small>
        </span>
        <i v-if="activeAction === 'folder'" class="pi pi-spinner pi-spin" aria-hidden="true" />
      </button>
    </div>

    <p
      v-if="workflowExportsDisabled"
      class="workflow-export-dialog__notice"
      data-testid="workflow-export-mutation-notice"
    >
      Workflow-containing exports are unavailable while execution is changing the workflow. Results-only exports remain available.
    </p>

    <p
      v-if="progressMessage"
      class="workflow-export-dialog__progress"
      role="status"
      aria-live="polite"
      data-testid="workflow-export-progress"
    >
      <i class="pi pi-spinner pi-spin" aria-hidden="true" />
      {{ progressMessage }}
    </p>

    <div
      v-if="exportedDestination"
      class="workflow-export-dialog__success"
      data-testid="workflow-export-folder-success"
    >
      <div>
        <strong>Latest results exported</strong>
        <span>{{ exportedItemCount }} item{{ exportedItemCount === 1 ? '' : 's' }} copied to {{ exportedDestination }}</span>
      </div>
      <Button
        label="Show in folder"
        icon="pi pi-folder-open"
        size="small"
        outlined
        data-testid="workflow-export-reveal"
        @click="revealExport"
      />
    </div>

    <p
      v-if="errorMessage"
      class="workflow-export-dialog__error"
      role="alert"
      data-testid="workflow-export-error"
    >
      {{ errorMessage }}
    </p>

    <template #footer>
      <Button
        :label="isBusy ? 'Cancel export' : 'Close'"
        :icon="isBusy ? 'pi pi-times' : undefined"
        text
        data-testid="workflow-export-cancel"
        @click="cancel"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.workflow-export-dialog__intro {
  margin: 0 0 1rem;
  color: var(--p-text-muted-color);
}

.workflow-export-dialog__choices {
  display: grid;
  gap: 0.65rem;
}

.workflow-export-dialog__choice {
  display: grid;
  grid-template-columns: 1.5rem 1fr auto;
  gap: 0.8rem;
  align-items: center;
  width: 100%;
  padding: 0.9rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  color: var(--p-text-color);
  background: var(--p-content-background);
  text-align: left;
  cursor: pointer;
}

.workflow-export-dialog__choice:hover:not(:disabled) {
  border-color: var(--p-primary-color);
  background: var(--p-primary-50);
}

.workflow-export-dialog__choice:focus-visible {
  outline: 2px solid var(--p-primary-color);
  outline-offset: 2px;
}

.workflow-export-dialog__choice:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.workflow-export-dialog__choice span {
  display: grid;
  gap: 0.2rem;
}

.workflow-export-dialog__choice small {
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.workflow-export-dialog__notice,
.workflow-export-dialog__progress,
.workflow-export-dialog__error {
  margin: 0.9rem 0 0;
  padding: 0.75rem;
  border-radius: var(--p-border-radius-md);
}

.workflow-export-dialog__notice {
  background: var(--p-surface-100);
  color: var(--p-text-muted-color);
}

.workflow-export-dialog__progress {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  background: var(--p-blue-50);
  color: var(--p-blue-700);
}

.workflow-export-dialog__error {
  background: var(--p-red-50);
  color: var(--p-red-700);
}

.workflow-export-dialog__success {
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.9rem;
  padding: 0.8rem;
  border-radius: var(--p-border-radius-md);
  background: var(--p-green-50);
  color: var(--p-green-800);
}

.workflow-export-dialog__success > div {
  display: grid;
  gap: 0.2rem;
  min-width: 0;
}

.workflow-export-dialog__success span {
  overflow-wrap: anywhere;
}
</style>
