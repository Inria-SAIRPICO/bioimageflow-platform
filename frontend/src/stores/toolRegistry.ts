import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { ToolMetadata, PackageInfo } from '@/api/types'

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
    fetchTools,
    fetchPackages,
    getToolByName,
    searchTools,
    getEnvStatusForTool,
    applyToolReload,
    applyToolRemoved,
  }
})
