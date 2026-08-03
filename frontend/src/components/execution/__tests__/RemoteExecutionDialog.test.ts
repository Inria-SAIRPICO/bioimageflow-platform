import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { createPinia } from 'pinia'

vi.mock('@/utils/nativeDialogs', () => ({
  isDesktop: () => true,
  selectFile: vi.fn(),
  selectFiles: vi.fn(),
  selectFolder: vi.fn(),
}))

import RemoteExecutionDialog from '../RemoteExecutionDialog.vue'

describe('RemoteExecutionDialog', () => {
  it('requires an explicit source for every path leaf and preserves list order', async () => {
    const wrapper = mount(RemoteExecutionDialog, {
      props: {
        visible: true,
        prepared: null,
        unresolved: [{
          node_path: 'preprocessing/masks', input_name: 'files', value_shape: 'list',
          values: ['/laptop/a.tif', '/cluster/b.tif'],
        }],
      },
      global: { plugins: [createPinia(), PrimeVue] },
      attachTo: document.body,
    })
    await flushPromises()

    expect((wrapper.vm as any).canResolve).toBe(false)
    const drafts = (wrapper.vm as any).drafts['preprocessing/masks\nfiles']
    drafts[0].source = 'upload'
    drafts[1].source = 'cluster'
    await wrapper.vm.$nextTick()
    expect((wrapper.vm as any).canResolve).toBe(true)

    ;(wrapper.vm as any).resolve()
    expect(wrapper.emitted('resolve')?.[0]?.[0]).toEqual([{
      node_path: 'preprocessing/masks', input_name: 'files', value_shape: 'list',
      values: [
        { source: 'upload', path: '/laptop/a.tif' },
        { source: 'cluster', path: '/cluster/b.tif' },
      ],
    }])
    wrapper.unmount()
  })

  it('shows immutable manifest digests and unpinned pre-launch warnings', async () => {
    const wrapper = mount(RemoteExecutionDialog, {
      props: {
        visible: true,
        unresolved: [],
        prepared: {
          status: 'ready', token: 'token', expires_at: '2026-08-03T10:15:00Z',
          manifest: {
            uploads_count: 1, total_bytes: 42,
            entries: [{
              kind: 'pre_launch_script', label: 'Cluster setup', digest: 'sha256:abc',
              pinned: false,
            }],
          },
        },
      },
      global: { plugins: [createPinia(), PrimeVue] },
      attachTo: document.body,
    })
    await flushPromises()

    expect(document.body.textContent).toContain('sha256:abc')
    expect(document.body.textContent).toContain('unpinned cluster script')
    wrapper.unmount()
  })
})
