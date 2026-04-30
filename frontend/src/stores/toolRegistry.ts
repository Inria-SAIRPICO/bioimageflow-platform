import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type {
  PackageInfo,
  ToolCreateResponse,
  ToolDeleteResponse,
  ToolMetadata,
  ToolRenameResponse,
  ToolUsageResponse,
} from '@/api/types'

export interface ToolReloadPayload {
  type: 'tool_reload'
  tool_name: string
  tool_metadata: ToolMetadata
}

export interface ToolRemovedPayload {
  type: 'tool_removed'
  tool_name: string
}

export const useToolRegistryStore = defineStore('toolRegistry', () => {
  const tools = ref<ToolMetadata[]>([])
  const packages = ref<PackageInfo[]>([])
  const error = ref<string | null>(null)
  const customToolBusy = ref(false)

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

  async function createTool(body: {
    name: string
    tool_type: 'ProcessingTool' | 'DataFrameTool'
  }): Promise<ToolCreateResponse> {
    customToolBusy.value = true
    try {
      const { data } = await api.post<ToolCreateResponse>('/api/v1/tools', body)
      await Promise.all([fetchTools(), fetchPackages()])
      error.value = null
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      customToolBusy.value = false
    }
  }

  async function getToolUsage(toolName: string): Promise<ToolUsageResponse> {
    const { data } = await api.get<ToolUsageResponse>(`/api/v1/tools/${toolName}/usage`)
    return data
  }

  async function renameTool(toolName: string, newName: string): Promise<ToolRenameResponse> {
    customToolBusy.value = true
    try {
      const { data } = await api.patch<ToolRenameResponse>(
        `/api/v1/tools/${toolName}`,
        { new_name: newName },
      )
      await Promise.all([fetchTools(), fetchPackages()])
      error.value = null
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      customToolBusy.value = false
    }
  }

  async function deleteTool(toolName: string): Promise<ToolDeleteResponse> {
    customToolBusy.value = true
    try {
      const { data } = await api.delete<ToolDeleteResponse>(`/api/v1/tools/${toolName}`)
      await Promise.all([fetchTools(), fetchPackages()])
      error.value = null
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      customToolBusy.value = false
    }
  }

  function applyToolReload(payload: ToolReloadPayload) {
    const meta = payload.tool_metadata
    const idx = tools.value.findIndex((t) => t.name === payload.tool_name)
    const next = [...tools.value]
    if (idx === -1) {
      next.push(meta)
    } else {
      next[idx] = meta
    }
    tools.value = next

    // Keep PackageInfo.tools[version] in sync so the Tools Panel doesn't
    // need a separate refresh.
    const pkgIdx = packages.value.findIndex((p) => p.name === meta.package)
    if (pkgIdx !== -1) {
      const pkg = packages.value[pkgIdx]
      const versionTools = pkg.tools[meta.package_version] ?? []
      if (!versionTools.includes(payload.tool_name)) {
        const updated: PackageInfo = {
          ...pkg,
          tools: {
            ...pkg.tools,
            [meta.package_version]: [...versionTools, payload.tool_name],
          },
        }
        const nextPkgs = [...packages.value]
        nextPkgs[pkgIdx] = updated
        packages.value = nextPkgs
      }
    }
  }

  function applyToolRemoved(payload: ToolRemovedPayload) {
    const removed = tools.value.find((t) => t.name === payload.tool_name)
    const next = tools.value.filter((t) => t.name !== payload.tool_name)
    tools.value = next

    if (removed !== undefined) {
      const pkgIdx = packages.value.findIndex(
        (p) => p.name === removed.package,
      )
      if (pkgIdx !== -1) {
        const pkg = packages.value[pkgIdx]
        const versionTools = pkg.tools[removed.package_version] ?? []
        const filtered = versionTools.filter((n) => n !== payload.tool_name)
        if (filtered.length !== versionTools.length) {
          const updated: PackageInfo = {
            ...pkg,
            tools: {
              ...pkg.tools,
              [removed.package_version]: filtered,
            },
          }
          const nextPkgs = [...packages.value]
          nextPkgs[pkgIdx] = updated
          packages.value = nextPkgs
        }
      }
    }
  }

  return {
    tools,
    packages,
    error,
    customToolBusy,
    fetchTools,
    fetchPackages,
    createTool,
    getToolUsage,
    renameTool,
    deleteTool,
    getToolByName,
    searchTools,
    getEnvStatusForTool,
    applyToolReload,
    applyToolRemoved,
  }
})
