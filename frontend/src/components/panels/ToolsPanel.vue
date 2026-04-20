<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import Select from 'primevue/select'
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

/** Currently selected version in the version dropdown per package */
const selectedVersion = ref<Record<string, string>>({})

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
  searchQuery,
  activeDoc,
  manageActiveDoc,
  showCreateDialog,
  showManageDialog,
  selectedVersion,
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
              :data-testid="`tool-power-${tool.name}`"
              @click.stop="toggleEnvironment(tool.package)"
            />
            <span
              class="env-dot"
              :class="`env-${toolRegistry.getEnvStatusForTool(tool.name)}`"
              :data-testid="`env-dot-${tool.name}`"
              :title="toolRegistry.getEnvStatusForTool(tool.name)"
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
      data-testid="manage-tools-dialog"
    >
      <TreeTable :value="treeNodes" class="mt-2">
        <Column field="display_name" header="Name" expander>
          <template #body="{ node }">
            <span>{{ node.data.display_name }}</span>
          </template>
        </Column>
        <Column field="categories" header="Categories" />
        <Column field="tags" header="Tags" />
        <Column header="Versions">
          <template #body="{ node }">
            <!-- Package row: version dropdown with install/uninstall -->
            <template v-if="!node.data.tool">
              <div class="version-management">
                <Select
                  :model-value="selectedVersion[node.data.name]"
                  :options="getVersionRows(node.data.name)"
                  option-label="version"
                  option-value="version"
                  placeholder="Select version"
                  :data-testid="`version-select-${node.data.name}`"
                  class="version-select"
                  @update:model-value="selectedVersion[node.data.name] = $event"
                >
                  <template #option="{ option }">
                    <span>{{ option.version }}</span>
                    <Tag
                      v-if="option.installed"
                      value="installed"
                      severity="success"
                      class="version-tag"
                    />
                  </template>
                </Select>
                <Button
                  v-if="selectedVersion[node.data.name] && !getVersionRows(node.data.name).find(r => r.version === selectedVersion[node.data.name])?.installed"
                  icon="pi pi-download"
                  text
                  size="small"
                  title="Install version"
                  :data-testid="`install-version-${node.data.name}`"
                  @click="installVersion(node.data.name, selectedVersion[node.data.name])"
                />
                <Button
                  v-if="selectedVersion[node.data.name] && getVersionRows(node.data.name).find(r => r.version === selectedVersion[node.data.name])?.installed"
                  icon="pi pi-trash"
                  text
                  size="small"
                  severity="danger"
                  title="Uninstall version"
                  :data-testid="`uninstall-version-${node.data.name}`"
                  @click="uninstallVersion(node.data.name, selectedVersion[node.data.name])"
                />
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

      <!-- Documentation panel inside dialog -->
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

/* --- Environment status dot --- */
.env-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--p-surface-400);
}
.env-dot.env-stopped {
  background-color: var(--p-surface-400);
}
.env-dot.env-creating {
  background-color: var(--p-yellow-500);
}
.env-dot.env-running,
.env-dot.env-ready {
  background-color: var(--p-green-500);
}

/* --- Manage dialog TreeTable badges --- */
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
.env-running {
  color: var(--p-green-500);
}

.tool-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* --- Version management --- */
.version-management {
  display: flex;
  align-items: center;
  gap: 4px;
}

.version-select {
  min-width: 120px;
  font-size: 12px;
}

.version-tag {
  margin-left: 6px;
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
  margin-top: 8px;
}
</style>
