import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { AxiosError } from 'axios'
import { api } from '@/api/client'
import type { OmeroInstanceResponse, SettingsResponse } from '@/api/types'

type OmeroInstancePatch = Omit<OmeroInstanceResponse, 'password_stored'> & {
  password?: string | null
}

export type WorkspaceSettings = SettingsResponse & {
  workspace_path?: string | null
  workspaces_root?: string | null
}
export type Settings = SettingsResponse
export type SettingsPatch = Omit<Partial<WorkspaceSettings>, 'omero_instances'> & {
  omero_instances?: OmeroInstancePatch[]
}

function _extractError(e: unknown): string {
  if (e instanceof AxiosError && e.response?.data) {
    const data = e.response.data as { detail?: string; message?: string }
    if (data.detail) return data.detail
    if (data.message) return data.message
  }
  return e instanceof Error ? e.message : String(e)
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<WorkspaceSettings | null>(null)
  const error = ref<string | null>(null)

  // Internal serialization chain: each updateSettings() call appends to it
  // so concurrent calls run in submit order rather than racing the server.
  let lastPromise: Promise<unknown> = Promise.resolve()

  const isLoaded = computed(() => settings.value !== null)
  const isDesktop = computed(() => settings.value?.deployment_mode === 'desktop')
  const isWebapp = computed(() => settings.value?.deployment_mode === 'webapp')
  const unsafeWebappFeaturesEnabled = computed(
    () => settings.value?.enable_unsafe_webapp_features === true,
  )

  async function fetchSettings() {
    try {
      const { data } = await api.get<WorkspaceSettings>('/api/v1/settings')
      settings.value = data
      error.value = null
    } catch (e: unknown) {
      error.value = _extractError(e)
    }
  }

  function _sanitizeOptimisticPatch(partial: SettingsPatch): Partial<WorkspaceSettings> {
    const sanitized = { ...partial } as Partial<WorkspaceSettings>
    if (partial.omero_instances) {
      sanitized.omero_instances = partial.omero_instances.map(
        ({ password: _password, ...instance }) => instance,
      ) as Settings['omero_instances']
    }
    return sanitized
  }

  async function _doPatch(partial: SettingsPatch): Promise<void> {
    const previous = settings.value
    const containsOmeroInstances = partial.omero_instances !== undefined
    // Optimistic merge so listeners see ordinary changes immediately. OMERO
    // patches wait for the server response so local password form state is not
    // cleared before a failed keyring write can be retried.
    if (previous !== null && !containsOmeroInstances) {
      settings.value = {
        ...previous,
        ..._sanitizeOptimisticPatch(partial),
      } as Settings
    }
    try {
      const { data } = await api.patch<WorkspaceSettings>('/api/v1/settings', partial)
      settings.value = data
      error.value = null
    } catch (e: unknown) {
      // Revert on failure: restore the snapshot taken before the optimistic
      // mutation. This avoids leaving the store mirroring a server-rejected
      // value (the previous behaviour).
      settings.value = previous
      error.value = _extractError(e)
    }
  }

  async function updateSettings(partial: SettingsPatch) {
    const next = lastPromise.then(() => _doPatch(partial))
    lastPromise = next.catch(() => {
      /* swallow so a single rejection doesn't poison subsequent calls */
    })
    return next
  }

  return {
    settings,
    error,
    isLoaded,
    isDesktop,
    isWebapp,
    unsafeWebappFeaturesEnabled,
    fetchSettings,
    updateSettings,
  }
})
