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
    const q = query.toLowerCase()
    return tools.value.filter((t) => {
      return (
        t.name.toLowerCase().includes(q) ||
        t.display_name.toLowerCase().includes(q) ||
        t.tags.some((tag) => tag.toLowerCase().includes(q)) ||
        t.categories.some((cat) => cat.toLowerCase().includes(q))
      )
    })
  }

  return {
    tools,
    packages,
    error,
    fetchTools,
    fetchPackages,
    getToolByName,
    searchTools,
  }
})
