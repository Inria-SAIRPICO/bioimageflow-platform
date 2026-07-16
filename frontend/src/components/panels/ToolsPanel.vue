<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import CreateToolDialog from './CreateToolDialog.vue'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useSettingsStore } from '@/stores/settings'
import { useWorkflowStore } from '@/stores/workflow'
import type { ToolCreateResponse, ToolMetadata } from '@/api/types'
import { api } from '@/api/client'
import {
  openPathWithEditor,
  openToolWithEditor,
} from '@/api/editor'

const emit = defineEmits<{
  'add-tool': [toolName: string]
}>()

const toolRegistry = useToolRegistryStore()
const settingsStore = useSettingsStore()
const workflowStore = useWorkflowStore()

const searchQuery = ref('')
const isSearchActive = computed(() => searchQuery.value.trim().length > 0)
const showCreateDialog = ref(false)
const showManageDialog = ref(false)
const confirm = useConfirm()
const toast = useToast()

/** Per-row in-flight keys, ``${pkg}@${version}``. Replaced (not mutated)
 * on change so the ref stays reactive. */
const busy = ref(new Set<string>())

const packageInstallUrl = ref('')
const packageArchiveFile = ref<File | null>(null)
const packageArchiveInput = ref<HTMLInputElement | null>(null)
const packageInstallBusy = ref(false)

const packageArchiveLabel = computed(() => packageArchiveFile.value?.name ?? '')
const canInstallPackageSource = computed(() => {
  if (packageInstallBusy.value || !packageSourceInstallAvailable.value) return false
  return packageInstallUrl.value.trim().length > 0 || packageArchiveFile.value !== null
})

function extractApiError(e: unknown): string {
  const data = (e as { response?: { data?: { detail?: string; message?: string } } })
    ?.response?.data
  if (data?.detail) return data.detail
  if (data?.message) return data.message
  return e instanceof Error ? e.message : String(e)
}

watch(packageInstallUrl, (value) => {
  if (value.trim().length === 0 || packageArchiveFile.value === null) return
  clearPackageArchiveSelection()
})

function clearPackageArchiveSelection() {
  packageArchiveFile.value = null
  if (packageArchiveInput.value) packageArchiveInput.value.value = ''
}

function selectPackageArchive() {
  packageArchiveInput.value?.click()
}

function onPackageArchiveSelected(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0] ?? null
  if (!file) {
    clearPackageArchiveSelection()
    return
  }
  packageInstallUrl.value = ''
  packageArchiveFile.value = file
}

async function installPackageSource() {
  if (!canInstallPackageSource.value) return
  packageInstallBusy.value = true
  try {
    const url = packageInstallUrl.value.trim()
    let responsePackage = ''
    let responseVersion = ''
    if (url) {
      const { data } = await api.post('/api/v1/tools/packages/import-url', { url })
      responsePackage = data?.package ?? ''
      responseVersion = data?.version ?? ''
    } else if (packageArchiveFile.value) {
      const body = new FormData()
      body.append('archive', packageArchiveFile.value)
      const { data } = await api.post('/api/v1/tools/packages/import-archive', body, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      responsePackage = data?.package ?? ''
      responseVersion = data?.version ?? ''
    }
    await Promise.all([toolRegistry.fetchPackages(), toolRegistry.fetchTools()])
    packageInstallUrl.value = ''
    clearPackageArchiveSelection()
    toast.add({
      severity: 'success',
      summary: 'Tool package installed',
      detail: [responsePackage, responseVersion].filter(Boolean).join(' '),
      life: 3000,
    })
  } catch (e: unknown) {
    const message = extractApiError(e)
    toolRegistry.error = message
    toast.add({
      severity: 'error',
      summary: 'Package install failed',
      detail: message,
      life: 5000,
    })
  } finally {
    packageInstallBusy.value = false
  }
}

function busyKey(packageName: string, version: string): string {
  return `${packageName}@${version}`
}

function isBusy(packageName: string, version: string): boolean {
  return busy.value.has(busyKey(packageName, version))
}

function markBusy(key: string, on: boolean) {
  const next = new Set(busy.value)
  if (on) next.add(key)
  else next.delete(key)
  busy.value = next
}

const filteredTools = computed(() => toolRegistry.searchTools(searchQuery.value))
const localToolActionsAvailable = computed(() => {
  return (
    settingsStore.settings?.deployment_mode !== 'webapp'
    || settingsStore.settings?.enable_unsafe_webapp_features === true
  )
})

const packageSourceInstallAvailable = computed(() => localToolActionsAvailable.value)

function shouldShowEmbeddedEditorLoading(): boolean {
  return !settingsStore.settings?.external_editor?.trim()
}

/** Tools grouped by their primary category for the sidebar list. The list
 * is rendered as a tree (category -> tool rows), mirroring the package tree
 * in the Manage Tools dialog. Tools without categories are grouped under
 * "Uncategorized". */
export interface CategoryGroup {
  category: string
  tools: ToolMetadata[]
}

const categoryGroups = computed<CategoryGroup[]>(() => {
  const grouped: Record<string, ToolMetadata[]> = {}
  for (const tool of filteredTools.value) {
    const category = tool.categories[0] ?? 'Uncategorized'
    if (!grouped[category]) grouped[category] = []
    grouped[category].push(tool)
  }
  return Object.keys(grouped)
    .sort((a, b) => a.localeCompare(b))
    .map((category) => ({ category, tools: grouped[category] }))
})

/** Categories collapsed by the user. Categories are expanded by default, so
 * we track collapse state instead of expand state — that way newly arriving
 * categories appear open. */
const collapsedCategories = ref(new Set<string>())

function isCategoryCollapsed(category: string): boolean {
  // Every rendered group contains a search match, so keep it open while the
  // query is active. Preserve the user's collapse state for normal browsing.
  return !isSearchActive.value && collapsedCategories.value.has(category)
}

function toggleCategoryCollapsed(category: string) {
  if (isSearchActive.value) return
  const next = new Set(collapsedCategories.value)
  if (next.has(category)) next.delete(category)
  else next.add(category)
  collapsedCategories.value = next
}

export interface TreeNode {
  key: string
  data: {
    name: string
    display_name: string
    categories: string
    tags: string
    versions: string
    isCustomPackage?: boolean
    tool?: ToolMetadata
  }
  children?: TreeNode[]
}

function packageDisplayName(name: string): string {
  return name === '__custom__' ? 'Custom workflow tools' : name
}

const treeNodes = computed<TreeNode[]>(() => {
  const grouped: Record<string, ToolMetadata[]> = {}
  for (const tool of filteredTools.value) {
    if (!grouped[tool.package]) {
      grouped[tool.package] = []
    }
    grouped[tool.package].push(tool)
  }

  // Seed from the union of known packages and grouped tools so
  // known-but-not-installed packages still appear as tree nodes (the user
  // needs them to install from a clean tool store).
  //
  // While a search query is active, hide package rows that have no tool
  // children — the user is looking for a tool, not browsing packages.
  const names = new Set<string>(Object.keys(grouped))
  if (!isSearchActive.value) {
    for (const pkg of toolRegistry.packages) {
      names.add(pkg.name)
    }
  }

  return Array.from(names).map((pkg) => {
    const pkgInfo = toolRegistry.packages.find((p) => p.name === pkg)
    const versions = pkgInfo ? pkgInfo.installed_versions.join(', ') : ''
    const tools = grouped[pkg] ?? []

    return {
      key: pkg,
      data: {
        name: pkg,
        display_name: packageDisplayName(pkg),
        categories: '',
        tags: '',
        versions,
        isCustomPackage: pkg === '__custom__',
      },
      children: tools.map((tool) => ({
        key: tool.name,
        data: {
          name: tool.name,
          display_name: tool.display_name,
          categories: tool.categories.join(', '),
          tags: tool.tags.join(', '),
          versions: tool.package_version,
          tool,
        },
      })),
    }
  })
})

/** Expansion map for the Manage Tools TreeTable. PrimeVue's TreeTable expects
 * a record `{ [nodeKey]: true }` of expanded keys; we seed it with every
 * known package row whenever the tree node set changes so newly arriving
 * packages start expanded, but we still let the user collapse a row.
 *
 * `seenPackages` records keys we've already auto-expanded — once the user
 * collapses a row it stays collapsed instead of being re-expanded on the
 * next package fetch. */
const manageExpandedKeys = ref<Record<string, boolean>>({})
const seenPackages = ref(new Set<string>())

watch(
  treeNodes,
  (nodes) => {
    const next = { ...manageExpandedKeys.value }
    for (const node of nodes) {
      if (!seenPackages.value.has(node.key)) {
        next[node.key] = true
        seenPackages.value.add(node.key)
      }
    }
    manageExpandedKeys.value = next
  },
  { immediate: true },
)

function onToolDragStart(event: DragEvent, tool: ToolMetadata) {
  event.dataTransfer?.setData('application/bioimageflow-tool', tool.name)
}

function onToolClick(toolName: string) {
  emit('add-tool', toolName)
}

async function onToolCreated(response: ToolCreateResponse) {
  showCreateDialog.value = false
  if (response.path) {
    try {
      await openPathWithEditor(response.path, toast, {
        showEmbeddedLoading: shouldShowEmbeddedEditorLoading(),
      })
    } catch (e: unknown) {
      toolRegistry.error = e instanceof Error ? e.message : String(e)
    }
  }
}

// --- Version management (Task 14) ---

export interface VersionRow {
  version: string
  installed: boolean
  available: boolean
  loadError: string | null
}

/** Packages whose version list is currently revealed (set-backed per-package,
 * so install/uninstall actions inside a row don't collapse the list). */
const expandedVersions = ref(new Set<string>())

function isVersionsExpanded(packageName: string): boolean {
  return expandedVersions.value.has(packageName)
}

function toggleVersionsExpanded(packageName: string) {
  const next = new Set(expandedVersions.value)
  if (next.has(packageName)) {
    next.delete(packageName)
  } else {
    next.add(packageName)
  }
  expandedVersions.value = next
}

function closeAllVersionDropdowns() {
  if (expandedVersions.value.size === 0) return
  expandedVersions.value = new Set()
}

/** Label for the dropdown trigger. Shows the active version with a hint when
 * other installed versions are available (so the user knows the dropdown is
 * worth opening), or "uninstalled" when nothing is on disk. */
function versionTriggerLabel(packageName: string): string {
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  if (!pkg || pkg.installed_versions.length === 0) return 'uninstalled'
  if (pkg.active_version) {
    if (pkg.load_errors?.[pkg.active_version]) {
      return `${pkg.active_version} (failed)`
    }
    if (pkg.installed_versions.length > 1) {
      return `${pkg.active_version} (active, +${pkg.installed_versions.length - 1})`
    }
    return `${pkg.active_version} (active)`
  }
  return pkg.installed_versions.join(', ')
}

/** Document-level click listener to close open dropdowns when the user clicks
 * outside any `.version-dropdown` element. Registered at mount time. */
function onDocumentClick(event: MouseEvent) {
  const target = event.target as Element | null
  if (target && target.closest('.version-dropdown')) return
  closeAllVersionDropdowns()
}

function getVersionRows(packageName: string): VersionRow[] {
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  if (!pkg) return []

  const versions = new Set([...pkg.installed_versions, ...pkg.available_versions])
  return Array.from(versions).map((version) => ({
    version,
    installed: pkg.installed_versions.includes(version),
    available: pkg.available_versions.includes(version),
    loadError: pkg.load_errors?.[version] ?? null,
  }))
}

async function installVersion(packageName: string, version: string) {
  const key = busyKey(packageName, version)
  markBusy(key, true)
  toast.add({
    severity: 'info',
    summary: 'Installing',
    detail: `${packageName}==${version}`,
    life: 3000,
  })
  try {
    await api.post(`/api/v1/tools/packages/${packageName}/install`, { version })
    await Promise.all([toolRegistry.fetchPackages(), toolRegistry.fetchTools()])
    toast.add({
      severity: 'success',
      summary: 'Installed',
      detail: `${packageName}==${version}`,
      life: 3000,
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e)
    toolRegistry.error = message
    toast.add({
      severity: 'error',
      summary: 'Install failed',
      detail: `${packageName}==${version}: ${message}`,
      life: 5000,
    })
  } finally {
    markBusy(key, false)
  }
}

async function uninstallVersion(packageName: string, version: string) {
  const key = busyKey(packageName, version)
  markBusy(key, true)
  toast.add({
    severity: 'info',
    summary: 'Uninstalling',
    detail: `${packageName}==${version}`,
    life: 3000,
  })
  try {
    await api.delete(`/api/v1/tools/packages/${packageName}`, { params: { version } })
    await Promise.all([toolRegistry.fetchPackages(), toolRegistry.fetchTools()])
    toast.add({
      severity: 'success',
      summary: 'Uninstalled',
      detail: `${packageName}==${version}`,
      life: 3000,
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e)
    toolRegistry.error = message
    toast.add({
      severity: 'error',
      summary: 'Uninstall failed',
      detail: `${packageName}==${version}: ${message}`,
      life: 5000,
    })
  } finally {
    markBusy(key, false)
  }
}

/** True when ``version`` is the currently active version for ``packageName``
 * in the workflow. Used to disable the "Set current" button on the active
 * row and to render the "current" badge. */
function isActiveVersion(packageName: string, version: string): boolean {
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  return pkg?.active_version === version
}

/** Make ``packageName==version`` the active version for the workflow. There
 * is one active version per package, so this affects every node from this
 * package — confirm before switching because nodes built against a different
 * schema may need to be re-validated. */
function useVersionInWorkflow(packageName: string, version: string) {
  if (isActiveVersion(packageName, version)) return
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  if (pkg?.load_errors?.[version]) return
  confirm.require({
    message: `Set ${packageName} ${version} as the active version for this workflow? Every node from this package will use the new version's schema.`,
    header: 'Change Package Version',
    acceptLabel: 'Set current',
    rejectLabel: 'Cancel',
    accept: async () => {
      const key = busyKey(packageName, version)
      markBusy(key, true)
      try {
        await api.post(`/api/v1/tools/packages/${packageName}/use`, { version })
        await Promise.all([toolRegistry.fetchPackages(), toolRegistry.fetchTools()])
        toast.add({
          severity: 'success',
          summary: 'Active version changed',
          detail: `${packageName} ${version}`,
          life: 3000,
        })
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : String(e)
        toolRegistry.error = message
        toast.add({
          severity: 'error',
          summary: 'Failed to change active version',
          detail: `${packageName} ${version}: ${message}`,
          life: 5000,
        })
      } finally {
        markBusy(key, false)
      }
    },
  })
}

// --- Info and Open in Editor (Task 15) ---

/** Single active documentation panel in the main tool list */
const activeDoc = ref<string | null>(null)

/** Single active documentation panel inside the manage dialog */
const manageActiveDoc = ref<string | null>(null)

function toggleDocumentation(toolName: string) {
  activeDoc.value = activeDoc.value === toolName ? null : toolName
}

function toggleManageDocumentation(toolName: string) {
  manageActiveDoc.value = manageActiveDoc.value === toolName ? null : toolName
}

function getDocumentation(toolName: string): string {
  const tool = toolRegistry.getToolByName(toolName)
  return tool?.documentation ?? ''
}

function getToolDisplayName(toolName: string): string {
  const tool = toolRegistry.getToolByName(toolName)
  return tool?.display_name ?? toolName
}

function parentPath(path: string): string {
  const slash = path.lastIndexOf('/')
  const backslash = path.lastIndexOf('\\')
  const index = Math.max(slash, backslash)
  if (index < 0) return path
  if (index === 0) return path.slice(0, 1)
  if (index === 2 && /^[A-Za-z]:[\\/]/.test(path)) return path.slice(0, 3)
  return path.slice(0, index)
}

async function openInEditor(toolName: string) {
  if (!localToolActionsAvailable.value) return
  const showEmbeddedLoading = shouldShowEmbeddedEditorLoading()
  try {
    await openToolWithEditor(toolName, workflowStore.currentName, toast, {
      showEmbeddedLoading,
    })
  } catch (e: unknown) {
    toolRegistry.error = e instanceof Error ? e.message : String(e)
  }
}

function isEditableTool(tool: ToolMetadata): boolean {
  return tool.editable === true || tool.source_kind === 'custom'
}

async function renameCustomTool(tool: ToolMetadata) {
  if (!isEditableTool(tool)) return
  const nextName = window.prompt('Rename custom tool', tool.name)?.trim()
  if (!nextName || nextName === tool.name) return
  try {
    const result = await toolRegistry.renameTool(tool.name, nextName)
    window.dispatchEvent(new CustomEvent('bioimageflow:tool-renamed', { detail: result }))
    toast.add({
      severity: 'success',
      summary: 'Tool renamed',
      detail: `${result.old_name} -> ${result.new_name}`,
      life: 3000,
    })
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e)
    toast.add({
      severity: 'error',
      summary: 'Rename failed',
      detail: message,
      life: 5000,
    })
  }
}

async function requestDeleteCustomTool(tool: ToolMetadata) {
  if (!isEditableTool(tool)) return
  let affected: string[] = []
  try {
    const usage = await toolRegistry.getToolUsage(tool.name)
    affected = usage.affected_workflows
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e)
    toast.add({
      severity: 'error',
      summary: 'Usage check failed',
      detail: message,
      life: 5000,
    })
    return
  }
  const usageMessage = affected.length
    ? `Delete ${tool.name}? Saved workflows referencing it: ${affected.join(', ')}.`
    : `Delete ${tool.name}?`
  confirm.require({
    message: usageMessage,
    header: 'Delete Custom Tool',
    acceptLabel: 'Delete',
    rejectLabel: 'Cancel',
    accept: async () => {
      try {
        const result = await toolRegistry.deleteTool(tool.name)
        window.dispatchEvent(new CustomEvent('bioimageflow:tool-deleted', {
          detail: { tool_name: tool.name, ...result },
        }))
        toast.add({
          severity: 'success',
          summary: 'Tool deleted',
          detail: tool.name,
          life: 3000,
        })
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : String(e)
        toast.add({
          severity: 'error',
          summary: 'Delete failed',
          detail: message,
          life: 5000,
        })
      }
    },
  })
}

// --- Environment controls (Task 16) ---

function getEnvStatus(packageName: string): string {
  const liveStatus = toolRegistry.environmentStatuses[packageName]
  if (liveStatus) return liveStatus
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  return pkg?.environment_status ?? 'unknown'
}

function getToolEnvName(tool: ToolMetadata): string {
  const name = tool.environment?.name
  return typeof name === 'string' ? name : ''
}

function getToolEnvStatus(tool: ToolMetadata): string {
  const envName = getToolEnvName(tool)
  if (!envName) return 'unavailable'
  const statusByEnvName = toolRegistry.environmentStatuses[envName]
  if (statusByEnvName) return statusByEnvName

  const packageEnvNames = new Set(
    toolRegistry.tools
      .filter((candidate) => candidate.package === tool.package)
      .map((candidate) => candidate.environment?.name)
      .filter((name): name is string => typeof name === 'string' && name.length > 0),
  )
  if (packageEnvNames.size > 1) return 'stopped'
  return toolRegistry.getEnvStatusForTool(tool.name)
}

async function toggleEnvironment(packageName: string) {
  try {
    const status = getEnvStatus(packageName)
    if (status === 'running') {
      const { data } = await api.post(`/api/v1/tools/environments/${packageName}/stop`)
      toolRegistry.applyEnvironmentStatus({
        type: 'environment_status',
        env_name: packageName,
        status: data?.status ?? 'stopped',
      })
    } else {
      const { data } = await api.post(`/api/v1/tools/environments/${packageName}/start`)
      toolRegistry.applyEnvironmentStatus({
        type: 'environment_status',
        env_name: packageName,
        status: data?.status ?? 'running',
      })
    }
    await toolRegistry.fetchPackages()
  } catch (e: unknown) {
    toolRegistry.error = e instanceof Error ? e.message : String(e)
  }
}

async function toggleToolEnvironment(tool: ToolMetadata) {
  try {
    const status = getToolEnvStatus(tool)
    const envName = getToolEnvName(tool)
    if (!envName || status === 'unavailable') return
    if (status === 'running') {
      const { data } = await api.post(`/api/v1/tools/environments/${envName}/stop`)
      toolRegistry.applyEnvironmentStatus({
        type: 'environment_status',
        env_name: envName,
        status: data?.status ?? 'stopped',
      })
    } else {
      const { data } = await api.post(`/api/v1/tools/environments/${envName}/start`)
      toolRegistry.applyEnvironmentStatus({
        type: 'environment_status',
        env_name: envName,
        status: data?.status ?? 'running',
      })
    }
    await toolRegistry.fetchPackages()
  } catch (e: unknown) {
    toolRegistry.error = e instanceof Error ? e.message : String(e)
  }
}

onMounted(async () => {
  await Promise.all([toolRegistry.fetchTools(), toolRegistry.fetchPackages()])
  document.addEventListener('click', onDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
})

defineExpose({
  treeNodes,
  manageExpandedKeys,
  filteredTools,
  categoryGroups,
  isCategoryCollapsed,
  toggleCategoryCollapsed,
  getVersionRows,
  installVersion,
  uninstallVersion,
  useVersionInWorkflow,
  isActiveVersion,
  toggleDocumentation,
  toggleManageDocumentation,
  getDocumentation,
  getToolDisplayName,
  parentPath,
  openInEditor,
  isEditableTool,
  renameCustomTool,
  requestDeleteCustomTool,
  getEnvStatus,
  getToolEnvName,
  getToolEnvStatus,
  toggleEnvironment,
  toggleToolEnvironment,
  isVersionsExpanded,
  toggleVersionsExpanded,
  isBusy,
  versionTriggerLabel,
  packageInstallUrl,
  packageArchiveFile,
  packageArchiveInput,
  packageArchiveLabel,
  packageInstallBusy,
  canInstallPackageSource,
  packageSourceInstallAvailable,
  clearPackageArchiveSelection,
  selectPackageArchive,
  onPackageArchiveSelected,
  installPackageSource,
  searchQuery,
  activeDoc,
  manageActiveDoc,
  showCreateDialog,
  showManageDialog,
  onToolCreated,
})
</script>

<template>
  <div class="tools-panel">
    <!-- Search bar -->
    <div class="tools-panel-header">
      <InputText
        v-model="searchQuery"
        placeholder="Search tools..."
        data-testid="tool-search"
        class="w-full"
      />
    </div>

    <!-- Manage tools button -->
    <div class="tools-panel-actions">
      <Button
        label="Manage tools"
        icon="pi pi-cog"
        severity="secondary"
        outlined
        size="small"
        data-testid="manage-tools-btn"
        class="w-full"
        @click="showManageDialog = true"
      />
    </div>

    <!-- Tool list grouped by category. Categories are expanded by default and
         can be collapsed individually; the structure mirrors the package tree
         in the Manage Tools dialog. -->
    <div class="tool-list" data-testid="tool-list">
      <div
        v-for="group in categoryGroups"
        :key="group.category"
        class="tool-category-group"
        :data-testid="`category-group-${group.category}`"
      >
        <button
          type="button"
          class="tool-category-header"
          :aria-expanded="!isCategoryCollapsed(group.category)"
          :disabled="isSearchActive"
          :data-testid="`category-toggle-${group.category}`"
          @click="toggleCategoryCollapsed(group.category)"
        >
          <i
            class="pi tool-category-chevron"
            :class="isCategoryCollapsed(group.category) ? 'pi-chevron-right' : 'pi-chevron-down'"
          />
          <span class="tool-category-label">{{ group.category }}</span>
        </button>
        <div v-if="!isCategoryCollapsed(group.category)" class="tool-category-items">
          <div
            v-for="tool in group.tools"
            :key="tool.name"
            class="tool-list-item"
            :data-testid="`tool-item-${tool.name}`"
            draggable="true"
            @dragstart="onToolDragStart($event, tool)"
            @click="onToolClick(tool.name)"
          >
            <div class="tool-list-item-row">
              <span class="tool-list-name">{{ tool.display_name }}</span>
              <span class="tool-list-right">
                <span class="tool-list-secondary-actions">
                  <Button
                    icon="pi pi-info-circle"
                    text
                    size="small"
                    class="tool-list-info-btn"
                    title="Tool information"
                    :data-testid="`tool-info-${tool.name}`"
                    @click.stop="toggleDocumentation(tool.name)"
                  />
                  <Button
                    v-if="localToolActionsAvailable"
                    icon="pi pi-code"
                    text
                    size="small"
                    class="tool-list-action-btn"
                    title="Open tool script"
                    :data-testid="`tool-open-script-${tool.name}`"
                    @click.stop="openInEditor(tool.name)"
                  />
                  <Button
                    v-if="localToolActionsAvailable && isEditableTool(tool)"
                    icon="pi pi-file-edit"
                    text
                    size="small"
                    class="tool-list-action-btn"
                    title="Rename tool"
                    :disabled="toolRegistry.customToolBusy"
                    :data-testid="`tool-rename-${tool.name}`"
                    @click.stop="renameCustomTool(tool)"
                  />
                  <Button
                    v-if="localToolActionsAvailable && isEditableTool(tool)"
                    icon="pi pi-trash"
                    text
                    size="small"
                    severity="danger"
                    class="tool-list-action-btn"
                    title="Delete tool"
                    :disabled="toolRegistry.customToolBusy"
                    :data-testid="`tool-delete-${tool.name}`"
                    @click.stop="requestDeleteCustomTool(tool)"
                  />
                </span>
                <Button
                  icon="pi pi-power-off"
                  text
                  size="small"
                  class="tool-list-power-btn"
                  :class="`env-${getToolEnvStatus(tool)}`"
                  :data-testid="`tool-power-${tool.name}`"
                  :disabled="getToolEnvStatus(tool) === 'unavailable'"
                  :title="getToolEnvStatus(tool)"
                  @click.stop="toggleToolEnvironment(tool)"
                />
              </span>
            </div>
            <div
              v-if="tool.tags.length"
              class="tool-list-meta"
              :title="tool.tags.join(' · ')"
            >
              <span class="tool-list-tags">{{ tool.tags.join(' · ') }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="categoryGroups.length === 0" class="tool-list-empty">
        No tools found.
      </div>
    </div>

    <!-- Create tool button at the bottom -->
    <div class="tools-panel-footer">
      <Button
        v-if="localToolActionsAvailable"
        label="Create Tool"
        icon="pi pi-plus"
        data-testid="create-tool-btn"
        class="w-full"
        @click="showCreateDialog = true"
      />
    </div>

    <!-- Single documentation panel for active tool -->
    <div
      v-if="activeDoc"
      :data-testid="`tool-doc-${activeDoc}`"
      class="tool-documentation"
    >
      <div class="tool-documentation-header">
        <h4>{{ getToolDisplayName(activeDoc) }}</h4>
        <Button
          icon="pi pi-times"
          text
          size="small"
          class="tool-doc-close-btn"
          aria-label="Close documentation"
          title="Close documentation"
          data-testid="tool-doc-close"
          @click="activeDoc = null"
        />
      </div>
      <p>{{ getDocumentation(activeDoc) }}</p>
    </div>

    <!-- Manage Tools modal dialog with full TreeTable -->
    <Dialog
      v-model:visible="showManageDialog"
      header="Manage Tools"
      modal
      :style="{ width: '80vw' }"
      content-class="manage-tools-dialog-content"
      data-testid="manage-tools-dialog"
    >
      <TreeTable
        :value="treeNodes"
        v-model:expanded-keys="manageExpandedKeys"
        class="manage-tools-tree mt-2"
      >
        <Column field="display_name" header="Name" expander>
          <template #body="{ node }">
            <span>{{ node.data.display_name }}</span>
          </template>
        </Column>
        <Column field="categories" header="Categories" />
        <Column field="tags" header="Tags" />
        <Column header="Versions">
          <template #body="{ node }">
            <!-- Package row: dropdown-style toggle reveals the version list.
                 The list is rendered as an absolute-positioned popover that
                 overlays the table, so expanding it doesn't reflow rows.
                 Install/uninstall clicks do NOT collapse the list — users can
                 change several versions in one go. -->
            <template v-if="!node.data.tool && node.data.isCustomPackage">
              <span data-testid="custom-workflow-tools-version">local</span>
            </template>
            <template v-else-if="!node.data.tool">
              <div class="version-dropdown">
                <button
                  type="button"
                  class="version-dropdown-toggle"
                  :aria-expanded="isVersionsExpanded(node.data.name)"
                  :data-testid="`version-toggle-${node.data.name}`"
                  @click.stop="toggleVersionsExpanded(node.data.name)"
                >
                  <span
                    class="version-dropdown-summary"
                    :class="{ 'version-dropdown-summary-empty': !node.data.versions }"
                  >
                    {{ versionTriggerLabel(node.data.name) }}
                  </span>
                  <i
                    class="pi version-dropdown-chevron"
                    :class="isVersionsExpanded(node.data.name) ? 'pi-chevron-up' : 'pi-chevron-down'"
                  />
                </button>
                <div
                  v-if="isVersionsExpanded(node.data.name)"
                  class="version-popover"
                  :data-testid="`version-list-${node.data.name}`"
                  role="menu"
                  @click.stop
                >
                  <ul class="version-list">
                    <li
                      v-for="row in getVersionRows(node.data.name)"
                      :key="row.version"
                      class="version-row"
                      :class="{ 'version-row-current': isActiveVersion(node.data.name, row.version) }"
                      role="menuitem"
                    >
                      <span class="version-label">{{ row.version }}</span>
                      <span
                        class="version-status-dot"
                        :class="row.loadError ? 'version-status-failed' : row.installed ? 'version-status-installed' : 'version-status-missing'"
                        :title="row.loadError ?? (row.installed ? 'Installed' : 'Not installed')"
                        :aria-label="row.loadError ? 'Failed to load' : row.installed ? 'Installed' : 'Not installed'"
                      />
                      <span
                        v-if="row.loadError"
                        class="version-failed-badge"
                        :title="row.loadError"
                        :data-testid="`failed-version-${node.data.name}-${row.version}`"
                      >
                        Failed
                      </span>
                      <!-- "Current" badge marks the active version for the
                           workflow. Otherwise, an installed row offers a
                           "Set current" button to switch to it. Only
                           installed versions can be set current. -->
                      <span
                        v-if="row.installed && !row.loadError && isActiveVersion(node.data.name, row.version)"
                        class="version-current-badge"
                        :data-testid="`current-version-${node.data.name}-${row.version}`"
                      >
                        Current
                      </span>
                      <Button
                        v-else-if="row.installed && !row.loadError"
                        label="Set current"
                        icon="pi pi-check"
                        size="small"
                        severity="secondary"
                        text
                        class="version-action"
                        :loading="isBusy(node.data.name, row.version)"
                        :disabled="isBusy(node.data.name, row.version)"
                        :data-testid="`set-current-version-${node.data.name}-${row.version}`"
                        @click="useVersionInWorkflow(node.data.name, row.version)"
                      />
                      <Button
                        v-if="!row.installed"
                        label="Install"
                        icon="pi pi-download"
                        size="small"
                        class="version-action"
                        :loading="isBusy(node.data.name, row.version)"
                        :disabled="isBusy(node.data.name, row.version)"
                        :data-testid="`install-version-${node.data.name}-${row.version}`"
                        @click="installVersion(node.data.name, row.version)"
                      />
                      <Button
                        v-else
                        label="Uninstall"
                        icon="pi pi-trash"
                        size="small"
                        severity="secondary"
                        outlined
                        class="version-action"
                        :loading="isBusy(node.data.name, row.version)"
                        :disabled="isBusy(node.data.name, row.version)"
                        :data-testid="`uninstall-version-${node.data.name}-${row.version}`"
                        @click="uninstallVersion(node.data.name, row.version)"
                      />
                    </li>
                  </ul>
                </div>
              </div>
            </template>
            <!-- Tool row: just show version string -->
            <template v-else>
              <span>{{ node.data.versions }}</span>
            </template>
          </template>
        </Column>
        <Column header="Actions">
          <template #body="{ node }">
            <!-- Tool row: info button + edit button + env toggle -->
            <template v-if="node.data.tool">
              <div class="tool-actions">
                <Button
                  icon="pi pi-info-circle"
                  text
                  size="small"
                  aria-label="Tool information"
                  title="Tool information"
                  :data-testid="`manage-tool-info-${node.data.name}`"
                  @click.stop="toggleManageDocumentation(node.data.name)"
                />
                <Button
                  v-if="localToolActionsAvailable"
                  icon="pi pi-pencil"
                  text
                  size="small"
                  aria-label="Open tool script"
                  title="Open tool script"
                  :data-testid="`manage-tool-edit-${node.data.name}`"
                  @click.stop="openInEditor(node.data.name)"
                />
                <Button
                  v-if="localToolActionsAvailable && isEditableTool(node.data.tool)"
                  icon="pi pi-file-edit"
                  text
                  size="small"
                  aria-label="Rename tool"
                  title="Rename tool"
                  :disabled="toolRegistry.customToolBusy"
                  :data-testid="`manage-tool-rename-${node.data.name}`"
                  @click.stop="renameCustomTool(node.data.tool)"
                />
                <Button
                  v-if="localToolActionsAvailable && isEditableTool(node.data.tool)"
                  icon="pi pi-trash"
                  text
                  size="small"
                  severity="danger"
                  aria-label="Delete tool"
                  title="Delete tool"
                  :disabled="toolRegistry.customToolBusy"
                  :data-testid="`manage-tool-delete-${node.data.name}`"
                  @click.stop="requestDeleteCustomTool(node.data.tool)"
                />
                <span
                  :data-testid="`tool-env-status-${node.data.name}`"
                  class="env-badge"
                  :class="`env-${getToolEnvStatus(node.data.tool)}`"
                >
                  {{ getToolEnvStatus(node.data.tool) }}
                </span>
                <Button
                  icon="pi pi-power-off"
                  text
                  size="small"
                  :class="`env-${getToolEnvStatus(node.data.tool)}`"
                  :disabled="getToolEnvStatus(node.data.tool) === 'unavailable'"
                  :title="getToolEnvStatus(node.data.tool)"
                  :data-testid="`tool-env-toggle-${node.data.name}`"
                  @click="toggleToolEnvironment(node.data.tool)"
                />
              </div>
            </template>
            <!-- Package row: no env controls (only version management in Versions column) -->
            <template v-else />
          </template>
        </Column>
      </TreeTable>

      <div
        v-if="packageSourceInstallAvailable"
        class="manage-tools-install-footer"
        data-testid="package-install-footer"
        aria-label="Install tool package"
      >
        <label
          for="package-install-url"
          class="manage-tools-install-label"
          data-testid="package-install-footer-label"
        >
          Install tool package
        </label>
        <InputText
          id="package-install-url"
          v-model="packageInstallUrl"
          placeholder="GitHub/GitLab URL"
          class="manage-tools-install-url"
          data-testid="package-install-url"
          :disabled="packageInstallBusy"
        />
        <span class="manage-tools-install-or" data-testid="package-install-or">or</span>
        <input
          ref="packageArchiveInput"
          type="file"
          accept=".zip,application/zip,application/x-zip-compressed"
          class="sr-only"
          data-testid="package-install-archive-input"
          @change="onPackageArchiveSelected"
        >
        <Button
          label="Select .zip archive"
          icon="pi pi-file-zip"
          severity="secondary"
          outlined
          data-testid="package-install-archive-button"
          :disabled="packageInstallBusy"
          @click="selectPackageArchive"
        />
        <span
          v-if="packageArchiveLabel"
          class="manage-tools-install-archive-name"
          data-testid="package-install-archive-name"
        >
          {{ packageArchiveLabel }}
        </span>
        <Button
          label="Install"
          icon="pi pi-download"
          data-testid="package-install-button"
          :loading="packageInstallBusy"
          :disabled="!canInstallPackageSource"
          @click="installPackageSource"
        />
      </div>


      <!-- Documentation panel docked at the bottom of the modal, always visible -->
      <template #footer>
        <div
          v-if="manageActiveDoc"
          :data-testid="`manage-tool-doc-${manageActiveDoc}`"
          class="tool-documentation manage-tool-documentation"
        >
          <div class="tool-documentation-header">
            <h4>{{ getToolDisplayName(manageActiveDoc) }}</h4>
            <Button
              icon="pi pi-times"
              text
              size="small"
              class="tool-doc-close-btn"
              aria-label="Close documentation"
              title="Close documentation"
              data-testid="manage-tool-doc-close"
              @click="manageActiveDoc = null"
            />
          </div>
          <p>{{ getDocumentation(manageActiveDoc) }}</p>
        </div>
      </template>
    </Dialog>

    <CreateToolDialog
      v-model:visible="showCreateDialog"
      @created="onToolCreated"
    />
    <ConfirmDialog />
  </div>
</template>

<style scoped>
.tools-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.tools-panel-header {
  padding: 10px 10px 0;
}

.tools-panel-actions {
  padding: 8px 10px;
}

.tools-panel-footer {
  padding: 8px 10px 10px;
}

/* --- Tool list (category tree) --- */
.tool-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px;
}

.tool-category-group {
  margin-bottom: 4px;
}

.tool-category-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  background: color-mix(in srgb, var(--p-primary-color) 10%, var(--bif-surface-active));
  border: 0;
  padding: 4px 4px;
  text-align: left;
  cursor: pointer;
  color: var(--p-text-color);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  border-radius: 3px;
}

.tool-category-header:not(:disabled):hover {
  background-color: color-mix(in srgb, var(--p-primary-color) 18%, var(--bif-surface-active));
}

.tool-category-header:disabled {
  cursor: default;
}

.tool-category-chevron {
  font-size: 10px;
  color: var(--p-text-muted-color);
}

.tool-category-label {
  flex: 1;
}

.tool-category-items {
  padding-left: 12px;
}

.tool-list-item {
  cursor: grab;
  user-select: none;
  padding: 7px 6px;
  background-color: var(--bif-surface);
  border-bottom: 1px solid var(--bif-border-muted);
  border-radius: 4px;
  transition: background-color 0.15s;
}

.tool-list-item:nth-child(even) {
  background-color: color-mix(in srgb, var(--p-primary-color) 5%, var(--bif-surface));
}

.tool-list-item:hover,
.tool-list-item:focus-within {
  background-color: color-mix(in srgb, var(--p-primary-color) 14%, var(--bif-surface));
}

.tool-list-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.tool-list-name {
  font-size: 13px;
  font-weight: 600;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--p-text-color);
}

.tool-list-right {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.tool-list-secondary-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  max-width: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-width 0.15s ease, opacity 0.15s ease;
}

.tool-list-item:hover .tool-list-secondary-actions,
.tool-list-item:focus-within .tool-list-secondary-actions {
  max-width: 104px;
  opacity: 1;
}

.tool-list-info-btn,
.tool-list-action-btn,
.tool-list-power-btn {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.tool-list-info-btn :deep(.p-button-icon),
.tool-list-action-btn :deep(.p-button-icon),
.tool-list-power-btn :deep(.p-button-icon) {
  line-height: 1;
}

.tool-list-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  margin-top: 3px;
  color: var(--bif-text-subtle);
  font-size: 10px;
  font-weight: 400;
  line-height: 14px;
  white-space: nowrap;
  overflow: hidden;
}

.tool-list-category {
  font-size: 10px;
  color: var(--p-text-muted-color);
}

.tool-list-tags {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (hover: none) {
  .tool-list-secondary-actions {
    max-width: 104px;
    opacity: 1;
  }
}

.tool-list-empty {
  padding: 12px 6px;
  color: var(--p-text-muted-color);
  font-size: 13px;
  text-align: center;
}

/* --- Environment status: color on power button + badge --- */
.env-badge {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}
.env-stopped {
  color: var(--p-surface-400);
}
.env-creating {
  color: var(--p-yellow-500);
}
.env-running,
.env-ready {
  color: var(--p-green-500);
}

/* Force PrimeVue text Button to inherit the env color */
.tool-list-power-btn.env-stopped :deep(.p-button-icon) {
  color: var(--p-surface-400);
}
.tool-list-power-btn.env-creating :deep(.p-button-icon) {
  color: var(--p-yellow-500);
}
.tool-list-power-btn.env-running :deep(.p-button-icon),
.tool-list-power-btn.env-ready :deep(.p-button-icon) {
  color: var(--p-green-500);
}

.tool-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* --- Version management --- */
.version-dropdown {
  position: relative;
  display: inline-block;
}

.version-dropdown-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 8px;
  background: var(--bif-surface);
  border: 1px solid var(--p-content-border-color);
  border-radius: 4px;
  font: inherit;
  font-size: 12px;
  color: var(--p-text-color);
  cursor: pointer;
  min-width: 160px;
  width: 100%;
}

.version-dropdown-toggle:hover {
  background: var(--bif-surface-hover);
}

.version-dropdown-summary {
  font-family: var(--font-family-mono, monospace);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-dropdown-summary-empty {
  font-family: inherit;
  font-style: italic;
  color: var(--p-text-muted-color);
}

.version-dropdown-chevron {
  font-size: 11px;
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.version-popover {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 20;
  min-width: 100%;
  background: var(--bif-surface);
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.14);
  padding: 4px;
}

.version-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.version-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 4px;
}

.version-row:hover {
  background: var(--bif-surface-hover);
}

.version-label {
  font-size: 12px;
  font-family: var(--font-family-mono, monospace);
  flex: 1;
}

.version-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.version-status-installed {
  background: var(--p-green-500);
}

.version-status-missing {
  background: var(--p-surface-400);
}

.version-status-failed {
  background: var(--p-red-500);
}

.version-row-current {
  background: color-mix(in srgb, var(--p-primary-color) 8%, transparent);
}

.version-current-badge,
.version-failed-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 2px 6px;
  border-radius: 999px;
  flex-shrink: 0;
}

.version-current-badge {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color, #fff);
}

.version-failed-badge {
  background: var(--p-red-100);
  color: var(--p-red-700);
}

.version-action {
  flex-shrink: 0;
}

.tool-documentation {
  padding: 8px 10px;
  background: var(--bif-surface-hover);
  color: var(--p-text-color);
  border-radius: 4px;
  margin: 4px 6px;
}

.tool-documentation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tool-documentation-header h4 {
  margin: 0;
}

.tool-doc-close-btn {
  width: 24px;
  height: 24px;
}

.manage-tool-documentation {
  margin: 0;
  width: 100%;
}


.manage-tools-install-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0 8px;
  border-top: 1px solid var(--p-content-border-color);
  flex-wrap: wrap;
}

.manage-tools-install-label {
  font-weight: 600;
  white-space: nowrap;
}

.manage-tools-install-url {
  flex: 1 1 260px;
  min-width: 0;
}

.manage-tools-install-or {
  color: var(--p-text-muted-color);
  font-size: 12px;
  text-transform: uppercase;
}

.manage-tools-install-archive-name {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--p-text-muted-color);
  font-size: 12px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Constrain the dialog content so the footer (info panel) stays visible
   and only the TreeTable scrolls. */
:global(.manage-tools-dialog-content) {
  display: flex;
  flex-direction: column;
  max-height: 70vh;
  overflow: hidden;
}
:global(.manage-tools-dialog-content .manage-tools-tree) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
</style>
