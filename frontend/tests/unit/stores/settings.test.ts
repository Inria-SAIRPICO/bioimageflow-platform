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
    let resolveRequest!: (value: { data: typeof settings }) => void
    mockedApi.get.mockReturnValueOnce(new Promise((resolve) => {
      resolveRequest = resolve
    }))

    const store = useSettingsStore()
    const request = store.fetchSettings()

    expect(store.isLoading).toBe(true)
    resolveRequest({ data: settings })
    await request

    expect(mockedApi.get).toHaveBeenCalledWith('/api/v1/settings')
    expect(store.settings).toEqual(settings)
    expect(store.isLoaded).toBe(true)
    expect(store.isLoading).toBe(false)
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

  it('unsafeWebappFeaturesEnabled reflects the file-backed debug flag', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: {
        deployment_mode: 'webapp',
        output_data_folder: '/out',
        enable_unsafe_webapp_features: true,
      },
    })

    const store = useSettingsStore()
    await store.fetchSettings()

    expect(store.unsafeWebappFeaturesEnabled).toBe(true)
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

  it('updateSettings supports desktop workspace path patches', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: {
        deployment_mode: 'desktop',
        output_data_folder: '/out',
        workspace_path: '/old/workspace',
      },
    })
    mockedApi.patch.mockResolvedValueOnce({
      data: {
        deployment_mode: 'desktop',
        output_data_folder: '/out',
        workspace_path: '/new/workspace',
      },
    })

    const store = useSettingsStore()
    await store.fetchSettings()
    await store.updateSettings({ workspace_path: '/new/workspace' })

    expect(mockedApi.patch).toHaveBeenCalledWith('/api/v1/settings', {
      workspace_path: '/new/workspace',
    })
    expect(store.settings?.workspace_path).toBe('/new/workspace')
  })

  it('reads webapp workspace path without enabling desktop mode', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: {
        deployment_mode: 'webapp',
        output_data_folder: '/out',
        workspace_path: '/srv/workspaces/current',
      },
    })

    const store = useSettingsStore()
    await store.fetchSettings()

    expect(store.isWebapp).toBe(true)
    expect(store.isDesktop).toBe(false)
    expect(store.settings?.workspace_path).toBe('/srv/workspaces/current')
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
    expect(store.isLoading).toBe(false)
  })

  it('updateSettings handles API errors gracefully', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { deployment_mode: 'desktop', output_data_folder: '/out' },
    })
    mockedApi.patch.mockRejectedValueOnce(new Error('Server error'))

    const store = useSettingsStore()
    await store.fetchSettings()
    const original = JSON.parse(JSON.stringify(store.settings))
    await store.updateSettings({ external_editor: 'vim' })

    expect(store.error).toBe('Server error')
    // Settings reverted to pre-PATCH snapshot.
    expect(store.settings).toEqual(original)
  })

  it('updateSettings sends OMERO password without storing it optimistically', async () => {
    const settings = {
      deployment_mode: 'desktop' as const,
      output_data_folder: '/out',
      omero_instances: [
        {
          name: null,
          host: 'omero.example.com',
          port: 4064,
          username: 'admin',
          password_stored: false,
        },
      ],
    }
    mockedApi.get.mockResolvedValueOnce({ data: settings })
    let resolvePatch: (value: { data: unknown }) => void = () => undefined
    mockedApi.patch.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolvePatch = resolve
        }),
    )

    const store = useSettingsStore()
    await store.fetchSettings()
    const patchPromise = store.updateSettings({
      omero_instances: [
        {
          name: null,
          host: 'omero.example.com',
          port: 4064,
          username: 'admin',
          password: 'secret',
        },
      ],
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(mockedApi.patch).toHaveBeenCalledWith('/api/v1/settings', {
      omero_instances: [
        {
          name: null,
          host: 'omero.example.com',
          port: 4064,
          username: 'admin',
          password: 'secret',
        },
      ],
    })
    expect(JSON.stringify(store.settings)).not.toContain('secret')

    resolvePatch({
      data: {
        ...settings,
        omero_instances: [{ ...settings.omero_instances[0], password_stored: true }],
      },
    })
    await patchPromise
    expect(store.settings?.omero_instances[0].password_stored).toBe(true)
    expect(JSON.stringify(store.settings)).not.toContain('secret')
  })

  it('failed OMERO password save restores previous settings without raw password', async () => {
    const settings = {
      deployment_mode: 'desktop' as const,
      output_data_folder: '/out',
      omero_instances: [
        {
          name: null,
          host: 'omero.example.com',
          port: 4064,
          username: 'admin',
          password_stored: false,
        },
      ],
    }
    mockedApi.get.mockResolvedValueOnce({ data: settings })
    mockedApi.patch.mockRejectedValueOnce(new Error('keyring unavailable'))

    const store = useSettingsStore()
    await store.fetchSettings()
    await store.updateSettings({
      omero_instances: [
        {
          name: null,
          host: 'omero.example.com',
          port: 4064,
          username: 'admin',
          password: 'secret',
        },
      ],
    })

    expect(store.error).toBe('keyring unavailable')
    expect(store.settings).toEqual(settings)
    expect(JSON.stringify(store.settings)).not.toContain('secret')
  })

  it('updateSettings 422 surfaces server detail', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { deployment_mode: 'desktop', output_data_folder: '/out' },
    })
    const axiosError = Object.assign(new Error('Request failed'), {
      isAxiosError: true,
      response: {
        status: 422,
        data: { error: 'validation_error', detail: 'execution_engine must be valid' },
      },
    })
    Object.setPrototypeOf(axiosError, (await import('axios')).AxiosError.prototype)
    mockedApi.patch.mockRejectedValueOnce(axiosError)

    const store = useSettingsStore()
    await store.fetchSettings()
    await store.updateSettings({ execution_engine: 'bad' as 'parallel' })

    expect(store.error).toContain('execution_engine')
  })

  it('updateSettings serializes rapid concurrent calls', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { deployment_mode: 'desktop', output_data_folder: '/out' },
    })
    let firstResolve: (value: { data: unknown }) => void = () => undefined
    let secondResolve: (value: { data: unknown }) => void = () => undefined
    const order: string[] = []
    mockedApi.patch.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          order.push('first-start')
          firstResolve = (value) => {
            order.push('first-end')
            resolve(value)
          }
        }),
    )
    mockedApi.patch.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          order.push('second-start')
          secondResolve = (value) => {
            order.push('second-end')
            resolve(value)
          }
        }),
    )

    const store = useSettingsStore()
    await store.fetchSettings()
    const p1 = store.updateSettings({ external_editor: 'vim' })
    const p2 = store.updateSettings({ napari_env_path: '/n' })

    // Let the promise chain reach the first PATCH.
    await new Promise((r) => setTimeout(r, 0))
    // Second call must not have started yet — chain is serialized.
    expect(order).toEqual(['first-start'])
    firstResolve({
      data: {
        deployment_mode: 'desktop',
        output_data_folder: '/out',
        external_editor: 'vim',
      },
    })
    await p1
    expect(order).toEqual(['first-start', 'first-end', 'second-start'])
    secondResolve({
      data: {
        deployment_mode: 'desktop',
        output_data_folder: '/out',
        external_editor: 'vim',
        napari_env_path: '/n',
      },
    })
    await p2
    expect(store.settings?.external_editor).toBe('vim')
    expect(store.settings?.napari_env_path).toBe('/n')
  })

  it('isLoaded stays false when fetchSettings fails', async () => {
    mockedApi.get.mockRejectedValueOnce(new Error('boom'))
    const store = useSettingsStore()
    await store.fetchSettings()
    expect(store.isLoaded).toBe(false)
    expect(store.error).toBe('boom')
  })
})
