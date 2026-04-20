<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import CreateToolDialog from './CreateToolDialog.vue'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useSettingsStore } from '@/stores/settings'
import type { ToolMetadata } from '@/api/types'
import { api } from '@/api/client'

const emit = defineEmits<{
  'add-tool': [toolName: string]
}>()

const toolRegistry = useToolRegistryStore()
const settingsStore = useSettingsStore()

const searchQuery = ref('')
const showCreateDialog = ref(false)
const showManageDialog = ref(false)
const confirm = useConfirm()

const filteredTools = computed(() => toolRegistry.searchTools(searchQuery.value))

export interface TreeNode {
  key: string
  data: {
    name: string
    display_name: string
    categories: string
    tags: string
    versions: string
    tool?: ToolMetadata
  }
  children?: TreeNode[]
}

const treeNodes = computed<TreeNode[]>(() => {
  const grouped: Record<string, ToolMetadata[]> = {}
  for (const tool of filteredTools.value) {
    if (!grouped[tool.package]) {
      grouped[tool.package] = []
    }
    grouped[tool.package].push(tool)
  }

  return Object.entries(grouped).map(([pkg, tools]) => {
    const pkgInfo = toolRegistry.packages.find((p) => p.name === pkg)
    const versions = pkgInfo ? pkgInfo.installed_versions.join(', ') : ''

    return {
      key: pkg,
      data: {
        name: pkg,
        display_name: pkg,
        categories: '',
        tags: '',
        versions,
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

function onToolDragStart(event: DragEvent, tool: ToolMetadata) {
  event.dataTransfer?.setData('application/bioimageflow-tool', tool.name)
}

function onToolClick(toolName: string) {
  emit('add-tool', toolName)
}

async function onToolCreated(toolName: string) {
  showCreateDialog.value = false
  await toolRegistry.fetchTools()
}

// --- Version management (Task 14) ---

interface VersionRow {
  version: string
  installed: boolean
  available: boolean
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

function getVersionRows(packageName: string): VersionRow[] {
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  if (!pkg) return []

  const versions = new Set([...pkg.installed_versions, ...pkg.available_versions])
  return Array.from(versions).map((version) => ({
    version,
    installed: pkg.installed_versions.includes(version),
    available: pkg.available_versions.includes(version),
  }))
}

async function installVersion(packageName: string, version: string) {
  try {
    await api.post(`/api/v1/tools/packages/${packageName}/install`, { version })
    await toolRegistry.fetchPackages()
  } catch (e: unknown) {
    toolRegistry.error = e instanceof Error ? e.message : String(e)
  }
}

async function uninstallVersion(packageName: string, version: string) {
  try {
    await api.delete(`/api/v1/tools/packages/${packageName}`, { data: { version } })
    await toolRegistry.fetchPackages()
  } catch (e: unknown) {
    toolRegistry.error = e instanceof Error ? e.message : String(e)
  }
}

function useVersionInWorkflow(packageName: string, version: string) {
  confirm.require({
    message: `Switch ${packageName} to version ${version} in the current workflow? Affected nodes will be marked as out-of-date.`,
    header: 'Change Package Version',
    acceptLabel: 'Switch',
    rejectLabel: 'Cancel',
    accept: async () => {
      await toolRegistry.fetchTools()
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

async function openInEditor(toolName: string) {
  if (!settingsStore.isDesktop) return
  try {
    const { data } = await api.get<{ source: string }>(`/api/v1/tools/${toolName}/source`)
    await api.post('/api/v1/editor/open', { file_path: data.source })
  } catch (e: unknown) {
    toolRegistry.error = e instanceof Error ? e.message : String(e)
  }
}

// --- Environment controls (Task 16) ---

function getEnvStatus(packageName: string): string {
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  return pkg?.environment_status ?? 'unknown'
}

async function toggleEnvironment(packageName: string) {
  try {
    const status = getEnvStatus(packageName)
    if (status === 'running') {
      await api.post(`/api/v1/tools/environments/${packageName}/stop`)
    } else {
      await api.post(`/api/v1/tools/environments/${packageName}/start`)
    }
    await toolRegistry.fetchPackages()
  } catch (e: unknown) {
    toolRegistry.error = e instanceof Error ? e.message : String(e)
  }
}

onMounted(async () => {
  await Promise.all([toolRegistry.fetchTools(), toolRegistry.fetchPackages()])
})

defineExpose({
  treeNodes,
  filteredTools,
  getVersionRows,
  installVersion,
  uninstallVersion,
  useVersionInWorkflow,
  toggleDocumentation,
  toggleManageDocumentation,
  getDocumentation,
  openInEditor,
  getEnvStatus,
  toggleEnvironment,
  isVersionsExpanded,
  toggleVersionsExpanded,
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

    <!-- Minimalist tool list -->
    <div class="tool-list" data-testid="tool-list">
      <div
        v-for="tool in filteredTools"
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
            <Button
              icon="pi pi-info-circle"
              text
              size="small"
              class="tool-list-info-btn"
              :data-testid="`tool-info-${tool.name}`"
              @click.stop="toggleDocumentation(tool.name)"
            />
            <Button
              icon="pi pi-power-off"
              text
              size="small"
              class="tool-list-power-btn"
              :class="`env-${toolRegistry.getEnvStatusForTool(tool.name)}`"
              :data-testid="`tool-power-${tool.name}`"
              :title="toolRegistry.getEnvStatusForTool(tool.name)"
              @click.stop="toggleEnvironment(tool.package)"
            />
          </span>
        </div>
        <div class="tool-list-meta">
          <span v-if="tool.categories.length" class="tool-list-category">
            {{ tool.categories[0] }}
          </span>
          <Tag
            v-for="tag in tool.tags"
            :key="tag"
            :value="tag"
            severity="secondary"
            class="tool-list-tag"
          />
        </div>
      </div>
      <div v-if="filteredTools.length === 0" class="tool-list-empty">
        No tools found.
      </div>
    </div>

    <!-- Create tool button at the bottom -->
    <div class="tools-panel-footer">
      <Button
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
        <h4>{{ activeDoc }}</h4>
        <Button
          icon="pi pi-times"
          text
          size="small"
          class="tool-doc-close-btn"
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
      <TreeTable :value="treeNodes" class="manage-tools-tree mt-2">
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
                 Install/uninstall clicks do NOT collapse the list — users can
                 change several versions in one go. -->
            <template v-if="!node.data.tool">
              <div class="version-dropdown">
                <button
                  type="button"
                  class="version-dropdown-toggle"
                  :aria-expanded="isVersionsExpanded(node.data.name)"
                  :data-testid="`version-toggle-${node.data.name}`"
                  @click="toggleVersionsExpanded(node.data.name)"
                >
                  <span class="version-dropdown-summary">
                    {{ node.data.versions || 'No versions installed' }}
                  </span>
                  <i
                    class="pi version-dropdown-chevron"
                    :class="isVersionsExpanded(node.data.name) ? 'pi-chevron-up' : 'pi-chevron-down'"
                  />
                </button>
                <ul
                  v-if="isVersionsExpanded(node.data.name)"
                  class="version-list"
                  :data-testid="`version-list-${node.data.name}`"
                >
                  <li
                    v-for="row in getVersionRows(node.data.name)"
                    :key="row.version"
                    class="version-row"
                  >
                    <span class="version-label">{{ row.version }}</span>
                    <Tag
                      v-if="row.installed"
                      value="installed"
                      severity="success"
                      class="version-tag"
                    />
                    <Button
                      v-if="!row.installed"
                      icon="pi pi-download"
                      text
                      size="small"
                      title="Install this version"
                      :data-testid="`install-version-${node.data.name}-${row.version}`"
                      @click="installVersion(node.data.name, row.version)"
                    />
                    <Button
                      v-else
                      icon="pi pi-trash"
                      text
                      size="small"
                      severity="danger"
                      title="Uninstall this version"
                      :data-testid="`uninstall-version-${node.data.name}-${row.version}`"
                      @click="uninstallVersion(node.data.name, row.version)"
                    />
                  </li>
                </ul>
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
                  :data-testid="`manage-tool-info-${node.data.name}`"
                  @click.stop="toggleManageDocumentation(node.data.name)"
                />
                <Button
                  v-if="settingsStore.isDesktop"
                  icon="pi pi-pencil"
                  text
                  size="small"
                  :data-testid="`manage-tool-edit-${node.data.name}`"
                  @click.stop="openInEditor(node.data.name)"
                />
                <span
                  :data-testid="`tool-env-status-${node.data.name}`"
                  class="env-badge"
                  :class="`env-${toolRegistry.getEnvStatusForTool(node.data.name)}`"
                >
                  {{ toolRegistry.getEnvStatusForTool(node.data.name) }}
                </span>
                <Button
                  icon="pi pi-power-off"
                  text
                  size="small"
                  :data-testid="`tool-env-toggle-${node.data.name}`"
                  @click="toggleEnvironment(node.data.tool.package)"
                />
              </div>
            </template>
            <!-- Package row: no env controls (only version management in Versions column) -->
            <template v-else />
          </template>
        </Column>
      </TreeTable>

      <!-- Documentation panel docked at the bottom of the modal, always visible -->
      <template #footer>
        <div
          v-if="manageActiveDoc"
          :data-testid="`manage-tool-doc-${manageActiveDoc}`"
          class="tool-documentation manage-tool-documentation"
        >
          <div class="tool-documentation-header">
            <h4>{{ manageActiveDoc }}</h4>
            <Button
              icon="pi pi-times"
              text
              size="small"
              class="tool-doc-close-btn"
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

/* --- Minimalist list --- */
.tool-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px;
}

.tool-list-item {
  cursor: grab;
  user-select: none;
  padding: 6px 6px;
  border-radius: 4px;
  transition: background-color 0.15s;
}
.tool-list-item:hover {
  background-color: var(--p-surface-100);
}

.tool-list-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.tool-list-name {
  font-size: 13px;
  font-weight: 500;
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

.tool-list-info-btn {
  width: 24px;
  height: 24px;
}

.tool-list-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.tool-list-category {
  font-size: 10px;
  color: var(--p-text-muted-color);
}

.tool-list-tag {
  font-size: 10px;
  padding: 0 4px;
  line-height: 16px;
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
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.version-dropdown-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 8px;
  background: var(--p-surface-0);
  border: 1px solid var(--p-content-border-color);
  border-radius: 4px;
  font: inherit;
  font-size: 12px;
  color: var(--p-text-color);
  cursor: pointer;
  min-width: 140px;
}

.version-dropdown-toggle:hover {
  background: var(--p-surface-100);
}

.version-dropdown-summary {
  font-family: var(--font-family-mono, monospace);
}

.version-dropdown-chevron {
  font-size: 11px;
  color: var(--p-text-muted-color);
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
  gap: 6px;
}

.version-label {
  font-size: 12px;
  font-family: var(--font-family-mono, monospace);
}

.version-tag {
  font-size: 9px;
  padding: 0 4px;
}

.tool-list-power-btn {
  width: 24px;
  height: 24px;
}

.tool-documentation {
  padding: 8px 10px;
  background: var(--p-surface-100);
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
