import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'

// Mirrors bioimageflow_server.models.settings.Settings. Not auto-generated
// because there's no /settings endpoint producing an OpenAPI schema yet.
export interface OMEROInstance {
  host: string
  username: string
}

export interface Settings {
  deployment_mode: 'desktop' | 'webapp'
  external_editor?: string | null
  napari_env_path?: string | null
  omero_instances?: OMEROInstance[]
  output_data_folder: string
  tool_store_path?: string
  update_mode?: 'auto' | 'manual' | string
  execution_engine?: 'sequential' | 'parsl'
  cache_max_executions?: number | null
  cache_max_age?: string | null
  keyboard_shortcuts?: Record<string, string>
  dev_mode?: boolean
  datasets_root?: string | null
  max_upload_size?: number
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<Settings | null>(null)
  const error = ref<string | null>(null)

  const isLoaded = computed(() => settings.value !== null)
  const isDesktop = computed(() => settings.value?.deployment_mode === 'desktop')
  const isWebapp = computed(() => settings.value?.deployment_mode === 'webapp')

  async function fetchSettings() {
    try {
      const { data } = await api.get<Settings>('/api/v1/settings')
      settings.value = data
      error.value = null
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  async function updateSettings(partial: Partial<Settings>) {
    try {
      const { data } = await api.patch<Settings>('/api/v1/settings', partial)
      settings.value = data
      error.value = null
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  return {
    settings,
    error,
    isLoaded,
    isDesktop,
    isWebapp,
    fetchSettings,
    updateSettings,
  }
})
