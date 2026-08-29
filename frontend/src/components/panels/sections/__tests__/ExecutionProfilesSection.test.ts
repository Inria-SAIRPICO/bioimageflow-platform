import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

vi.mock('@/utils/nativeDialogs', () => ({
  selectFile: vi.fn(),
}))

import { api } from '@/api/client'
import ExecutionProfilesSection from '../ExecutionProfilesSection.vue'

const profile = {
  schema: 'bioimageflow.platform.execution-profile.v2',
  id: 'profile-cluster', revision: 1, name: 'GPU cluster', enabled: true,
  config_path: '/site/cluster.py', config_digest: `sha256:${'a'.repeat(64)}`,
  cluster_host: 'login.cluster', cluster_root: '/cluster/workflows',
}

describe('ExecutionProfilesSection', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.delete).mockReset()
    vi.mocked(api.get).mockResolvedValue({ data: { editable: true, profiles: [profile] } })
  })

  it('shows only the trusted config script and capability-driven Describe report', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.mocked(api.post).mockResolvedValueOnce({ data: {
      profile_id: profile.id, profile_revision: 1,
      config_digest: profile.config_digest, cluster_host: profile.cluster_host,
      cluster_root: profile.cluster_root, configured: true,
      cluster: { host: profile.cluster_host, root: profile.cluster_root },
      capabilities: {
        schema: 'bioimageflow.execution_capabilities.v1',
        capabilities: {
          durable_remote_diagnostics: { supported: true, reason: null },
          managed_wheelhouse_environment: { supported: false, reason: 'Not implemented' },
        },
      },
      connection: null,
      diagnostics: [{
        schema: 'bioimageflow.cluster_diagnostic.v1', phase: 'describe',
        category: 'configuration', message: 'Setup script is configured.',
        allocation_state: 'none', retry_safety: 'not-applicable',
        next_action: 'No action required.', identities: {},
      }],
    } })
    const wrapper = mount(ExecutionProfilesSection, {
      props: { editable: true },
      global: primeVueTestGlobal({ pinia, dialog: true }),
    })
    await flushPromises()

    expect(wrapper.text()).toContain('cluster = RemoteCluster(...)')
    expect(wrapper.text()).toContain('login.cluster')
    expect(wrapper.text()).toContain('/site/cluster.py')
    expect(wrapper.text()).not.toContain('configuration factory')

    const describeButton = wrapper.findAll('button').find(button => button.text() === 'Describe')
    await describeButton!.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="cluster-description"]').text()).toContain(
      'durable_remote_diagnostics',
    )
    expect(wrapper.get('[data-testid="cluster-description"]').text()).toContain(
      'Not implemented',
    )
    expect(wrapper.get('[data-testid="cluster-description"]').text()).toContain(
      'No action required.',
    )
  })
})
