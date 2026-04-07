<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
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

const toolDocumentation = ref<Record<string, string>>({})
const showDocumentation = ref<Record<string, boolean>>({})

function toggleDocumentation(toolName: string) {
  const tool = toolRegistry.getToolByName(toolName)
  if (tool) {
    toolDocumentation.value[toolName] = tool.documentation
    showDocumentation.value[toolName] = !showDocumentation.value[toolName]
  }
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
  getVersionRows,
  installVersion,
  uninstallVersion,
  useVersionInWorkflow,
  toggleDocumentation,
  openInEditor,
  getEnvStatus,
  toggleEnvironment,
  searchQuery,
  toolDocumentation,
  showDocumentation,
  showCreateDialog,
  onToolCreated,
})
</script>

<template>
  <div class="tools-panel">
    <div class="tools-panel-header">
      <InputText
        v-model="searchQuery"
        placeholder="Search tools..."
        data-testid="tool-search"
        class="w-full"
      />
      <Button
        label="Create Tool"
        data-testid="create-tool-btn"
        class="mt-2"
        @click="showCreateDialog = true"
      />
    </div>

    <TreeTable :value="treeNodes" class="mt-2">
      <Column field="display_name" header="Name" expander>
        <template #body="{ node }">
          <div
            v-if="node.data.tool"
            class="tool-name-cell"
            draggable="true"
            @dragstart="onToolDragStart($event, node.data.tool)"
            @click="onToolClick(node.data.name)"
          >
            {{ node.data.display_name }}
          </div>
          <span v-else>{{ node.data.display_name }}</span>
        </template>
      </Column>
      <Column field="categories" header="Categories" />
      <Column field="tags" header="Tags" />
      <Column field="versions" header="Versions" />
      <Column header="Actions">
        <template #body="{ node }">
          <template v-if="node.data.tool">
            <div class="tool-actions">
              <Button
                icon="pi pi-info-circle"
                text
                size="small"
                :data-testid="`tool-info-${node.data.name}`"
                @click.stop="toggleDocumentation(node.data.name)"
              />
              <Button
                v-if="settingsStore.isDesktop"
                icon="pi pi-pencil"
                text
                size="small"
                :data-testid="`tool-edit-${node.data.name}`"
                @click.stop="openInEditor(node.data.name)"
              />
            </div>
          </template>
          <template v-else>
            <span
              :data-testid="`env-status-${node.data.name}`"
              class="env-badge"
            >
              {{ getEnvStatus(node.data.name) }}
            </span>
            <Button
              icon="pi pi-power-off"
              text
              size="small"
              :data-testid="`env-toggle-${node.data.name}`"
              @click="toggleEnvironment(node.data.name)"
            />
          </template>
        </template>
      </Column>
    </TreeTable>

    <div
      v-for="toolName in Object.keys(showDocumentation).filter(k => showDocumentation[k])"
      :key="toolName"
      :data-testid="`tool-doc-${toolName}`"
      class="tool-documentation"
    >
      <h4>{{ toolName }}</h4>
      <p>{{ toolDocumentation[toolName] }}</p>
    </div>
    <CreateToolDialog
      v-model:visible="showCreateDialog"
      @created="onToolCreated"
    />
    <ConfirmDialog />
  </div>
</template>

<style scoped>
.tool-name-cell {
  cursor: grab;
  padding: 4px 0;
  user-select: none;
}
.tool-name-cell:hover {
  text-decoration: underline;
}
</style>
