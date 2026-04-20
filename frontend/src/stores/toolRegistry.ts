import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { ToolMetadata, PackageInfo } from '@/api/types'

export const useToolRegistryStore = defineStore('toolRegistry', () => {
  const tools = ref<ToolMetadata[]>([])
  const packages = ref<PackageInfo[]>([])
  const error = ref<string | null>(null)

  async function fetchTools() {
    try {
      const { data } = await api.get<ToolMetadata[]>('/api/v1/tools')
      tools.value = data
      error.value = null
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  async function fetchPackages() {
    try {
      const { data } = await api.get<PackageInfo[]>('/api/v1/tools/packages')
      packages.value = data
      error.value = null
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  function getToolByName(name: string): ToolMetadata | undefined {
    return tools.value.find((t) => t.name === name)
  }

  function searchTools(query: string): ToolMetadata[] {
    if (!query) return tools.value
    const tokens = query.toLowerCase().split(/\s+/).filter(Boolean)
    return tools.value.filter((t) => {
      const haystack = [
        t.name,
        t.display_name,
        ...t.tags,
        ...t.categories,
      ]
        .join(' ')
        .toLowerCase()
      return tokens.every((token) => haystack.includes(token))
    })
  }

  function getEnvStatusForTool(toolName: string): string {
    const tool = tools.value.find((t) => t.name === toolName)
    if (!tool) return 'unknown'
    const pkg = packages.value.find((p) => p.name === tool.package)
    return pkg?.environment_status ?? 'unknown'
  }

  return {
    tools,
    packages,
    error,
    fetchTools,
    fetchPackages,
    getToolByName,
    searchTools,
    getEnvStatusForTool,
  }
})
