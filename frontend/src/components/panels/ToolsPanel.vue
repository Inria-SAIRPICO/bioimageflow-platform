<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
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

const filteredTools = computed(() => toolRegistry.searchTools(searchQuery.value))

export interface TreeNode {
  key: string
  data: {
    name: string
    display_name: string
    categories: string
    tags: string
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

  return Object.entries(grouped).map(([pkg, tools]) => ({
    key: pkg,
    data: {
      name: pkg,
      display_name: pkg,
      categories: '',
      tags: '',
    },
    children: tools.map((tool) => ({
      key: tool.name,
      data: {
        name: tool.name,
        display_name: tool.display_name,
        categories: tool.categories.join(', '),
        tags: tool.tags.join(', '),
        tool,
      },
    })),
  }))
})

function onToolDragStart(event: DragEvent, tool: ToolMetadata) {
  event.dataTransfer?.setData('application/bioimageflow-tool', tool.name)
}

function onToolClick(toolName: string) {
  emit('add-tool', toolName)
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
  await api.post(`/api/v1/tools/packages/${packageName}/install`, { version })
  await toolRegistry.fetchPackages()
}

async function uninstallVersion(packageName: string, version: string) {
  await api.delete(`/api/v1/tools/packages/${packageName}/versions/${version}`)
  await toolRegistry.fetchPackages()
}

async function useVersionInWorkflow(packageName: string, version: string) {
  if (confirm(`Switch ${packageName} to version ${version} in the current workflow?`)) {
    await api.post(`/api/v1/tools/packages/${packageName}/use`, { version })
    await toolRegistry.fetchTools()
  }
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
  const { data } = await api.get<{ source: string }>(`/api/v1/tools/${toolName}/source`)
  await api.post('/api/v1/editor/open', { file_path: data.source })
}

// --- Environment controls (Task 16) ---

function getEnvStatus(packageName: string): string {
  const pkg = toolRegistry.packages.find((p) => p.name === packageName)
  return pkg?.environment_status ?? 'unknown'
}

async function toggleEnvironment(packageName: string) {
  const status = getEnvStatus(packageName)
  if (status === 'running') {
    await api.post(`/api/v1/tools/packages/${packageName}/environment/stop`)
  } else {
    await api.post(`/api/v1/tools/packages/${packageName}/environment/start`)
  }
  await toolRegistry.fetchPackages()
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
      />
    </div>

    <TreeTable :value="treeNodes" class="mt-2">
      <Column field="display_name" header="Name" expander />
      <Column field="categories" header="Categories" />
      <Column field="tags" header="Tags" />
      <Column header="Actions">
        <template #body="{ node }">
          <template v-if="node.data.tool">
            <Button
              icon="pi pi-info-circle"
              text
              size="small"
              :data-testid="`tool-info-${node.data.name}`"
              @click="toggleDocumentation(node.data.name)"
            />
            <Button
              v-if="settingsStore.isDesktop"
              icon="pi pi-pencil"
              text
              size="small"
              :data-testid="`tool-edit-${node.data.name}`"
              @click="openInEditor(node.data.name)"
            />
            <div
              draggable="true"
              class="tool-row"
              @dragstart="onToolDragStart($event, node.data.tool)"
              @click="onToolClick(node.data.name)"
            />
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
  </div>
</template>
