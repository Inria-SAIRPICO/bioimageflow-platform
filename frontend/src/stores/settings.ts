import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { Settings } from '@/api/types'

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
