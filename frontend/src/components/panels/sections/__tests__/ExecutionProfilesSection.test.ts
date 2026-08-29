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
      cluster: {
        schema: 'bioimageflow.remote_cluster.v1',
        host: profile.cluster_host,
        root: profile.cluster_root,
        configured: true,
        results_root: '/cluster/workflows/results',
        environment: { kind: 'existing-python' },
        parsl: { source_kind: 'file', factory: 'build' },
        orchestrator: {
          scheduler: 'slurm', queue: 'gpu', project: 'BIOIMAGE',
          walltime_seconds: 14_400, cpu: 4,
        },
        setup: {
          source_kind: 'file', digest: `sha256:${'b'.repeat(64)}`,
          cluster_path: '/cluster/workflows/setup/setup.sh',
        },
      },
      capabilities: {
        schema: 'bioimageflow.execution_capabilities.v1',
        capabilities: {
          durable_remote_diagnostics: { supported: true, reason: null },
          managed_pixi_environment: { supported: false, reason: 'Not implemented' },
          attached_parsl: { supported: false, reason: 'Install the Parsl extra' },
        },
      },
      connection: {
        schema: 'bioimageflow.cluster_connection_report.v1',
        reachable: true,
        gateway_available: false,
        bootstrap_required: true,
        gateway_version: null,
        protocol_versions: [],
        diagnostics: [],
      },
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
      'not requirements for this managed target',
    )
    expect(wrapper.get('[data-testid="cluster-description"]').text()).toContain(
      'No action required.',
    )
    expect(wrapper.get('[data-testid="cluster-description"]').text()).toContain(
      'gateway bootstrap required',
    )
    const siteFacts = wrapper.get('[data-testid="cluster-site-facts"]').text()
    expect(siteFacts).toContain('/cluster/workflows/results')
    expect(siteFacts).toContain('existing-python')
    expect(siteFacts).toContain('file')
    expect(siteFacts).toContain('build')
    expect(siteFacts).toContain('slurm')
    expect(siteFacts).toContain('BIOIMAGE')
    expect(siteFacts).toContain('gpu')
    expect(siteFacts).toContain('14400 seconds')
    expect(siteFacts).toContain('/cluster/workflows/setup/setup.sh')
  })
})
