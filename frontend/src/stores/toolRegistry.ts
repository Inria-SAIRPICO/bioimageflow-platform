import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { useWorkflowStore } from '@/stores/workflow'
import type { EnvironmentRecoveryAction } from '@/stores/execution'
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

export interface EnvironmentStatusPayload {
  type: 'environment_status'
  env_name: string
  status: string
}

export interface EnvironmentDeleteResponse {
  environment: string
  status: string
}

export interface PackageInstallPayload {
  type: 'package_install'
  package_name: string
  status: string
  detail?: string | null
}

function apiErrorMessage(error: unknown): string {
  const response = (error as {
    response?: { data?: { detail?: string; message?: string } }
  })?.response?.data
  return response?.detail
    ?? response?.message
    ?? (error instanceof Error ? error.message : String(error))
}

export const useToolRegistryStore = defineStore('toolRegistry', () => {
  const tools = ref<ToolMetadata[]>([])
  const packages = ref<PackageInfo[]>([])
  const environmentStatuses = ref<Record<string, string>>({})
  const error = ref<string | null>(null)
  const customToolBusy = ref(false)
  const packageInstallOperations = ref(new Set<string>())

  function packageInstallKey(packageName: string, version: string): string {
    return `${packageName}@${version}`
  }

  function markPackageInstallBusy(key: string, active: boolean): void {
    const next = new Set(packageInstallOperations.value)
    if (active) next.add(key)
    else next.delete(key)
    packageInstallOperations.value = next
  }

  function isPackageVersionInstalling(packageName: string, version: string): boolean {
    return packageInstallOperations.value.has(packageInstallKey(packageName, version))
  }

  function isPackageInstalling(packageName: string): boolean {
    const prefix = `${packageName}@`
    return Array.from(packageInstallOperations.value).some(key => key.startsWith(prefix))
  }

  function currentWorkflowRequestConfig():
    | { params: { workflow_name: string } }
    | undefined {
    const workflowStore = useWorkflowStore()
    return workflowStore.currentName
      ? { params: { workflow_name: workflowStore.currentName } }
      : undefined
  }

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

  async function installPackageVersion(
    packageName: string,
    version: string,
    options: { refresh?: boolean } = {},
  ): Promise<void> {
    const key = packageInstallKey(packageName, version)
    if (packageInstallOperations.value.has(key)) return
    markPackageInstallBusy(key, true)
    try {
      await api.post(`/api/v1/tools/packages/${packageName}/install`, { version })
      if (options.refresh !== false) {
        await Promise.all([fetchPackages(), fetchTools()])
      }
      error.value = null
    } catch (e: unknown) {
      error.value = apiErrorMessage(e)
      throw e
    } finally {
      markPackageInstallBusy(key, false)
    }
  }

  function applyPackageInstall(payload: PackageInstallPayload): void {
    if (payload.status === 'installed' || payload.status === 'uninstalled') {
      void Promise.all([fetchPackages(), fetchTools()])
    }
  }

  function getToolByName(name: string): ToolMetadata | undefined {
    return tools.value.find((t) => t.name === name)
  }

  function getToolEnvironmentName(tool: ToolMetadata): string {
    const envName = tool.environment?.name
    return typeof envName === 'string' ? envName : ''
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
    const envName = getToolEnvironmentName(tool)
    if (envName && environmentStatuses.value[envName]) {
      return environmentStatuses.value[envName]
    }
    if (environmentStatuses.value[tool.name]) {
      return environmentStatuses.value[tool.name]
    }
    if (environmentStatuses.value[tool.package]) {
      return environmentStatuses.value[tool.package]
    }
    const pkg = packages.value.find((p) => p.name === tool.package)
    return pkg?.environment_status ?? 'unknown'
  }

  function packageNamesForEnvironment(envName: string): Set<string> {
    const packageNames = new Set<string>()
    for (const pkg of packages.value) {
      if (pkg.name === envName) packageNames.add(pkg.name)
    }
    for (const tool of tools.value) {
      if (
        tool.package === envName ||
        tool.name === envName ||
        getToolEnvironmentName(tool) === envName
      ) {
        packageNames.add(tool.package)
      }
    }
    return packageNames
  }

  function applyEnvironmentStatus(payload: EnvironmentStatusPayload) {
    const envName = payload.env_name
    const status = payload.status
    if (!envName || !status) return

    environmentStatuses.value = {
      ...environmentStatuses.value,
      [envName]: status,
    }

    const packageNames = packageNamesForEnvironment(envName)
    if (packageNames.size === 0) return

    packages.value = packages.value.map((pkg) => (
      packageNames.has(pkg.name)
        ? { ...pkg, environment_status: status }
        : pkg
    ))
  }

  async function createTool(body: {
    name: string
    tool_type: 'ProcessingTool' | 'DataFrameTool'
  }): Promise<ToolCreateResponse> {
    customToolBusy.value = true
    try {
      const requestConfig = currentWorkflowRequestConfig()
      const { data } = requestConfig
        ? await api.post<ToolCreateResponse>('/api/v1/tools', body, requestConfig)
        : await api.post<ToolCreateResponse>('/api/v1/tools', body)
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
    const requestConfig = currentWorkflowRequestConfig()
    const { data } = requestConfig
      ? await api.get<ToolUsageResponse>(`/api/v1/tools/${toolName}/usage`, requestConfig)
      : await api.get<ToolUsageResponse>(`/api/v1/tools/${toolName}/usage`)
    return data
  }

  async function renameTool(toolName: string, newName: string): Promise<ToolRenameResponse> {
    customToolBusy.value = true
    try {
      const requestConfig = currentWorkflowRequestConfig()
      const { data } = requestConfig
        ? await api.patch<ToolRenameResponse>(
          `/api/v1/tools/${toolName}`,
          { new_name: newName },
          requestConfig,
        )
        : await api.patch<ToolRenameResponse>(
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
      const requestConfig = currentWorkflowRequestConfig()
      const { data } = requestConfig
        ? await api.delete<ToolDeleteResponse>(`/api/v1/tools/${toolName}`, requestConfig)
        : await api.delete<ToolDeleteResponse>(`/api/v1/tools/${toolName}`)
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

  async function deleteEnvironment(
    action: EnvironmentRecoveryAction,
  ): Promise<EnvironmentDeleteResponse> {
    try {
      const { data } = await api.delete<EnvironmentDeleteResponse>(
        `/api/v1/tools/environments/${action.envName}`,
        {
          data: {
            path: action.path,
            existing_hash: action.existingHash,
            requested_hash: action.requestedHash ?? null,
          },
        },
      )
      applyEnvironmentStatus({
        type: 'environment_status',
        env_name: action.envName,
        status: 'stopped',
      })
      await Promise.all([fetchTools(), fetchPackages()])
      error.value = null
      return data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
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
    environmentStatuses,
    error,
    customToolBusy,
    packageInstallOperations,
    fetchTools,
    fetchPackages,
    installPackageVersion,
    isPackageVersionInstalling,
    isPackageInstalling,
    applyPackageInstall,
    createTool,
    getToolUsage,
    renameTool,
    deleteTool,
    deleteEnvironment,
    getToolByName,
    searchTools,
    getEnvStatusForTool,
    applyEnvironmentStatus,
    applyToolReload,
    applyToolRemoved,
  }
})
