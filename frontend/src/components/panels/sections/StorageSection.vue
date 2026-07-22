<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import type { SettingsResponse, WorkspaceInfo } from '@/api/types'
import {
  getDemoWorkflowsStatus,
  installDemoWorkflows,
  type DemoWorkflowsStatus,
} from '@/api/demoWorkflows'
import { getWorkspaceInfo, revealFilesystemPath } from '@/api/workspace'
import { useWorkflowStore } from '@/stores/workflow'
import { requestWorkflowDeletion } from '@/services/workflowDeletion'
import { workflowPanelId } from '@/utils/canvasPanels'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import { isDesktop, selectFolder } from '@/utils/nativeDialogs'

type StorageSettings = SettingsResponse & {
  workspace_path?: string | null
  workspaces_root?: string | null
}

const props = defineProps<{ modelValue: StorageSettings }>()
const workflowStore = useWorkflowStore()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof StorageSettings; value: unknown }): void
  (e: 'refresh-output-capabilities'): void
}>()

const outputModeOptions = [
  { label: 'Automatic (symlink, then pointer)', value: 'auto' },
  { label: 'Portable pointer files', value: 'pointer' },
  { label: 'Symbolic links', value: 'symlink' },
  { label: 'Copy files', value: 'copy' },
]
const selectedOutputCapability = computed(() => {
  const selected = props.modelValue.latest_output_mode
  if (selected === 'auto') return props.modelValue.latest_output_capabilities?.symlink
  return props.modelValue.latest_output_capabilities?.[selected]
})

let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}
let confirm: ReturnType<typeof useConfirm> | null = null
try {
  confirm = useConfirm()
} catch {
  confirm = null
}

const demoStatus = ref<DemoWorkflowsStatus | null>(null)
const demoBusy = ref(false)
const demoError = ref<string | null>(null)
const workspaceInfo = ref<WorkspaceInfo | null>(null)
const effectiveWorkspacePath = computed(() => (
  workspaceInfo.value?.workspace_path
  ?? props.modelValue.workspace_path
  ?? props.modelValue.workspaces_root
  ?? ''
))
const installedDemoCount = computed(() => (
  demoStatus.value?.workflows.filter(item => item.status === 'installed').length ?? 0
))
const demoStatusLabel = computed(() => {
  if (!demoStatus.value) return 'Checking…'
  if (demoStatus.value.status === 'installed') return 'Installed'
  if (demoStatus.value.status === 'missing') return 'Not installed'
  if (demoStatus.value.status === 'partial') return 'Partially installed'
  return 'Canonical locations are occupied by other workflows'
})

function errorMessage(error: unknown): string {
  if (
    typeof error === 'object'
    && error !== null
    && 'response' in error
  ) {
    const detail = (error as { response?: { data?: { detail?: unknown } } })
      .response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return error instanceof Error ? error.message : String(error)
}

function workflowId(workflow: { name: string; id?: string | null }): string {
  return workflow.id ?? workflow.name
}

async function refreshDemoStatus(): Promise<void> {
  try {
    demoStatus.value = await getDemoWorkflowsStatus()
    demoError.value = null
  } catch (error) {
    demoError.value = errorMessage(error)
  }
}

async function refreshWorkspaceInfo(): Promise<void> {
  try {
    workspaceInfo.value = await getWorkspaceInfo()
  } catch (error) {
    toast?.add({
      severity: 'error',
      summary: 'Could not resolve workspace path',
      detail: errorMessage(error),
      life: 6000,
    })
  }
}

defineExpose({ refreshDemoStatus, refreshWorkspaceInfo })

function captureDeletionRequest(workflowName: string) {
  const canvasId = canvasIdFromPanelId(workflowPanelId(workflowName))
  const session = canvasSessionRegistry.get(canvasId)
  const mountedRoot = session?.descriptor.kind === 'root'
    && session.descriptor.workflowId === workflowName
    ? session
    : null
  return {
    canvasId: mountedRoot ? canvasId : null,
    workflowName,
    localIdentityGeneration: workflowStore.workflowIdentityGeneration(workflowName),
    serverIdentityGeneration: workflowStore.workflowServerIdentityGeneration(workflowName),
    sessionRegistrationToken: mountedRoot?.registrationToken ?? null,
  }
}

async function installDemos(): Promise<void> {
  demoBusy.value = true
  try {
    await refreshDemoStatus()
    if (!demoStatus.value?.can_install) return
    demoStatus.value = await installDemoWorkflows()
    await workflowStore.fetchWorkflowTree()
    toast?.add({
      severity: 'success',
      summary: 'Example workflows installed',
      detail: 'The bundled workflows are available in the Demo folder.',
      life: 4000,
    })
  } catch (error) {
    demoError.value = errorMessage(error)
    toast?.add({
      severity: 'error',
      summary: 'Could not install example workflows',
      detail: demoError.value,
      life: 6000,
    })
  } finally {
    demoBusy.value = false
    await refreshDemoStatus()
  }
}

async function removeInstalledDemos(): Promise<void> {
  demoBusy.value = true
  try {
    await refreshDemoStatus()
    const workflowIds = demoStatus.value?.workflows
      .filter(item => item.status === 'installed')
      .map(item => item.workflow_id) ?? []
    for (const workflowId of workflowIds) {
      await requestWorkflowDeletion(captureDeletionRequest(workflowId))
    }
    await workflowStore.fetchWorkflowTree()
    const demoHasWorkflows = workflowStore.workflows.some(
      workflow => workflowId(workflow).startsWith('Demo/'),
    )
    const demoHasFolders = workflowStore.workflowFolders.some(
      folder => folder.parentId === 'Demo',
    )
    if (
      !demoHasWorkflows
      && !demoHasFolders
      && workflowStore.workflowFolders.some(folder => folder.id === 'Demo')
    ) {
      await workflowStore.deleteWorkflowFolder('Demo', 'empty')
    }
    toast?.add({
      severity: 'success',
      summary: 'Example workflows removed',
      life: 4000,
    })
  } catch (error) {
    demoError.value = errorMessage(error)
    toast?.add({
      severity: 'error',
      summary: 'Could not remove all example workflows',
      detail: demoError.value,
      life: 6000,
    })
  } finally {
    demoBusy.value = false
    await workflowStore.fetchWorkflowTree().catch(() => undefined)
    await refreshDemoStatus()
  }
}

function confirmRemoveDemos(): void {
  const remove = () => void removeInstalledDemos()
  if (!confirm) {
    remove()
    return
  }
  confirm.require({
    header: 'Remove example workflows',
    message: `Remove ${installedDemoCount.value} installed example workflow${installedDemoCount.value === 1 ? '' : 's'} and their server-managed output caches? Your other workflows in the Demo folder will be kept.`,
    icon: 'pi pi-exclamation-triangle',
    accept: remove,
  })
}

onMounted(() => {
  void refreshDemoStatus()
  void refreshWorkspaceInfo()
})
watch(
  () => workflowStore.workflows.map(workflow => (
    workflowId(workflow)
  )).join('\n'),
  () => void refreshDemoStatus(),
)

async function reveal(path: string, label: string) {
  try {
    await revealFilesystemPath(path)
  } catch (error) {
    toast?.add({
      severity: 'error',
      summary: `Could not reveal ${label}`,
      detail: errorMessage(error),
      life: 6000,
    })
  }
}

function revealWorkspace() {
  return reveal(effectiveWorkspacePath.value, 'workspace folder')
}

function revealOutputFolder() {
  return reveal(props.modelValue.resolved_output_data_folder, 'output data folder')
}

async function changeFolder() {
  const picked = await selectFolder('Select output data folder')
  if (!picked) return
  const apply = () =>
    emit('update:field', { field: 'output_data_folder', value: picked })
  if (confirm) {
    confirm.require({
      message:
        'Change output data folder? Existing data will not be moved to the new location.',
      header: 'Confirm change',
      icon: 'pi pi-exclamation-triangle',
      accept: apply,
    })
  } else {
    apply()
  }
}

async function changeWorkspacePath() {
  const picked = await selectFolder('Select workspace folder')
  if (!picked) return
  emit('update:field', { field: 'workspace_path', value: picked })
}
</script>

<template>
  <div class="settings-section">
    <div class="field">
      <label class="field-label" for="workspace-path-input">Workspace path</label>
      <div class="field-row">
        <InputText
          id="workspace-path-input"
          :model-value="effectiveWorkspacePath"
          readonly
          data-testid="workspace-path-input"
          class="grow"
        />
        <Button
          label="Reveal"
          severity="secondary"
          :disabled="!effectiveWorkspacePath"
          data-testid="workspace-path-reveal-button"
          @click="revealWorkspace"
        />
        <Button
          v-if="modelValue.deployment_mode === 'desktop' && isDesktop()"
          label="Browse..."
          severity="secondary"
          data-testid="workspace-path-change-button"
          @click="changeWorkspacePath"
        />
      </div>
      <p class="help-text" data-testid="workspace-path-help">
        <template v-if="modelValue.deployment_mode === 'desktop'">
          Desktop workspace location.
        </template>
        <template v-else>
          Workspace location is managed by the web application.
        </template>
      </p>
    </div>

    <div class="field latest-output-field">
      <label class="field-label" for="latest-output-mode">Latest output view</label>
      <div class="field-row">
        <Select
          id="latest-output-mode"
          :model-value="modelValue.latest_output_mode"
          :options="outputModeOptions"
          option-label="label"
          option-value="value"
          data-testid="latest-output-mode"
          class="grow"
          @update:model-value="emit('update:field', { field: 'latest_output_mode', value: $event })"
        />
        <Button
          label="Retest"
          severity="secondary"
          data-testid="latest-output-retest"
          @click="emit('refresh-output-capabilities')"
        />
      </div>
      <p class="help-text" data-testid="latest-output-effective-mode">
        Effective mode: <code>{{ modelValue.latest_output_effective_mode }}</code>.
        Latest means the latest successful result for each node, not necessarily one workflow execution snapshot.
      </p>
      <p
        v-if="modelValue.latest_output_warning"
        class="output-warning"
        data-testid="latest-output-warning"
      >
        {{ modelValue.latest_output_warning }}
      </p>
      <p
        v-else-if="selectedOutputCapability && !selectedOutputCapability.supported"
        class="output-warning"
      >
        This mode is unavailable: {{ selectedOutputCapability.code }}.
      </p>
      <p v-if="modelValue.latest_output_mode === 'pointer'" class="help-text">
        Pointer files use little space and work without link permissions, but image applications cannot open them directly.
      </p>
      <p v-if="modelValue.latest_output_mode === 'symlink'" class="help-text">
        Windows may require Developer Mode or symbolic-link privileges for this mode.
      </p>
      <p v-if="modelValue.latest_output_mode === 'copy'" class="output-warning">
        Copies open everywhere but can use roughly twice the asset storage space.
      </p>
    </div>

    <div class="field">
      <label class="field-label" for="output-data-folder-input">Output data folder</label>
      <div class="field-row">
        <InputText
          id="output-data-folder-input"
          :model-value="modelValue.resolved_output_data_folder"
          readonly
          data-testid="output-data-folder-input"
          class="grow"
        />
        <Button
          label="Reveal"
          severity="secondary"
          data-testid="output-reveal-button"
          @click="revealOutputFolder"
        />
        <Button
          v-if="isDesktop()"
          label="Browse..."
          severity="secondary"
          data-testid="output-change-button"
          @click="changeFolder"
        />
      </div>
      <p class="help-text">
        Workflow outputs are written here. Stored value:
        <code>{{ modelValue.output_data_folder }}</code>
      </p>
    </div>

    <div class="field">
      <label class="field-label" for="tool-store-path-input">Tool store path</label>
      <InputText
        id="tool-store-path-input"
        :model-value="modelValue.resolved_tool_store_path"
        readonly
        data-testid="tool-store-path-input"
      />
      <p class="help-text">
        Default: <code>~/.bioimageflow/tool_packages/</code>. Override with the
        <code>BIOIMAGEFLOW_TOOL_STORE</code> environment variable.
      </p>
    </div>

    <div class="field demo-workflows-field">
      <div class="field-row demo-heading">
        <div>
          <div class="field-label">Example workflows</div>
          <p class="help-text" data-testid="demo-workflows-status">
            {{ demoStatusLabel }}. Bundled examples use the
            <code>Demo</code> folder and download their public input data when run.
          </p>
        </div>
        <span v-if="demoStatus" class="demo-count">
          {{ installedDemoCount }}/{{ demoStatus.workflows.length }}
        </span>
      </div>
      <p v-if="demoError" class="demo-error" data-testid="demo-workflows-error">
        {{ demoError }}
      </p>
      <div class="field-row">
        <Button
          label="Install demos"
          icon="pi pi-download"
          :disabled="demoBusy || !demoStatus?.can_install"
          :loading="demoBusy"
          data-testid="demo-workflows-install"
          @click="installDemos"
        />
        <Button
          label="Remove demos"
          icon="pi pi-trash"
          severity="secondary"
          :disabled="demoBusy || !demoStatus?.can_remove"
          data-testid="demo-workflows-remove"
          @click="confirmRemoveDemos"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.field-label {
  font-weight: 600;
}
.field-row {
  display: flex;
  gap: 0.5rem;
}
.grow {
  flex: 1;
}
.help-text {
  margin: 0;
  color: var(--p-text-muted-color, #888);
  font-size: 0.85rem;
}
.output-warning {
  margin: 0;
  color: var(--p-orange-600, #c65d00);
  font-size: 0.85rem;
}
.demo-workflows-field {
  border-top: 1px solid var(--p-content-border-color, #ddd);
  padding-top: 1rem;
}
.demo-heading {
  align-items: flex-start;
  justify-content: space-between;
}
.demo-count {
  color: var(--p-text-muted-color, #888);
  font-size: 0.85rem;
  white-space: nowrap;
}
.demo-error {
  color: var(--p-red-500);
  font-size: 0.85rem;
  margin: 0;
}
</style>
