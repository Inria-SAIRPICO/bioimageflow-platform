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

  it('submits directly after explicit path resolution without a preparation confirmation', async () => {
    const wrapper = mount(RemoteExecutionDialog, {
      props: {
        visible: true,
        unresolved: [{
          node_path: 'files', input_name: 'path', value_shape: 'path',
          values: ['/cluster/images'],
        }],
      },
      global: { plugins: [createPinia(), PrimeVue] },
      attachTo: document.body,
    })
    await flushPromises()

    const drafts = (wrapper.vm as any).drafts['files\npath']
    drafts[0].source = 'cluster'
    await wrapper.vm.$nextTick()
    expect(document.body.textContent).toContain('submitted directly')
    expect(document.querySelector('[data-testid="confirm-remote-execution"]')).toBeNull()
    expect(document.querySelector('[data-testid="prepare-remote-execution"]')?.textContent).toContain(
      'Resolve and submit',
    )
    wrapper.unmount()
  })
})
