import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

import { api } from '@/api/client'
import { useSettingsStore } from '@/stores/settings'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
}

describe('settings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('starts with null settings and isLoaded false', () => {
    const store = useSettingsStore()
    expect(store.settings).toBeNull()
    expect(store.isLoaded).toBe(false)
  })

  it('fetchSettings loads from server', async () => {
    const settings = {
      deployment_mode: 'desktop' as const,
      output_data_folder: '/out',
    }
    mockedApi.get.mockResolvedValueOnce({ data: settings })

    const store = useSettingsStore()
    await store.fetchSettings()

    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/settings')
    expect(store.settings).toEqual(settings)
    expect(store.isLoaded).toBe(true)
  })

  it('isDesktop returns true for desktop mode', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { deployment_mode: 'desktop', output_data_folder: '/out' },
    })

    const store = useSettingsStore()
    await store.fetchSettings()

    expect(store.isDesktop).toBe(true)
    expect(store.isWebapp).toBe(false)
  })

  it('isWebapp returns true for webapp mode', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { deployment_mode: 'webapp', output_data_folder: '/out' },
    })

    const store = useSettingsStore()
    await store.fetchSettings()

    expect(store.isWebapp).toBe(true)
    expect(store.isDesktop).toBe(false)
  })

  it('updateSettings sends PATCH and updates local state', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { deployment_mode: 'desktop', output_data_folder: '/out' },
    })
    mockedApi.patch.mockResolvedValueOnce({
      data: {
        deployment_mode: 'desktop',
        output_data_folder: '/out',
        external_editor: 'code {file_path}',
      },
    })

    const store = useSettingsStore()
    await store.fetchSettings()
    await store.updateSettings({ external_editor: 'code {file_path}' })

    expect(mockedApi.patch).toHaveBeenCalledWith('/api/v1/settings', {
      external_editor: 'code {file_path}',
    })
    expect(store.settings?.external_editor).toBe('code {file_path}')
  })

  it('deploymentMode accessible before settings load (no crash)', () => {
    const store = useSettingsStore()
    expect(store.isDesktop).toBe(false)
    expect(store.isWebapp).toBe(false)
  })

  it('fetchSettings handles API errors gracefully', async () => {
    mockedApi.get.mockRejectedValueOnce(new Error('Network error'))

    const store = useSettingsStore()
    await store.fetchSettings()

    expect(store.error).toBe('Network error')
    expect(store.settings).toBeNull()
  })

  it('updateSettings handles API errors gracefully', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { deployment_mode: 'desktop', output_data_folder: '/out' },
    })
    mockedApi.patch.mockRejectedValueOnce(new Error('Server error'))

    const store = useSettingsStore()
    await store.fetchSettings()
    const original = store.settings
    await store.updateSettings({ external_editor: 'vim' })

    expect(store.error).toBe('Server error')
    // Settings unchanged on error
    expect(store.settings).toEqual(original)
  })
})
