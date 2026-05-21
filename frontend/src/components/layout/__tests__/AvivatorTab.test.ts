import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AvivatorTab from '../AvivatorTab.vue'
import type { DockviewApi, DockviewPanelApi, IDockviewPanel } from 'dockview-core'

function createTabParams(location: any = { type: 'grid' }) {
  const panel = { id: 'avivator' }
  const api = {
    id: 'avivator',
    title: 'Avivator',
    location,
    close: vi.fn(),
    onDidTitleChange: vi.fn(() => ({ dispose: vi.fn() })),
    onDidLocationChange: vi.fn(() => ({ dispose: vi.fn() })),
  }
  const containerApi = {
    addPopoutGroup: vi.fn().mockResolvedValue(true),
    getPanel: vi.fn(() => panel),
  }
  return {
    api: api as unknown as DockviewPanelApi,
    containerApi: containerApi as unknown as DockviewApi,
    panel: panel as unknown as IDockviewPanel,
    mocks: { api, containerApi },
  }
}

describe('AvivatorTab', () => {
  it('opens the Avivator panel through Dockview popout', async () => {
    const params = createTabParams()
    const wrapper = mount(AvivatorTab, { props: { params } })

    await wrapper.find('[data-testid="avivator-tab-window-toggle"]').trigger('click')
    await flushPromises()

    expect(params.mocks.containerApi.addPopoutGroup).toHaveBeenCalledWith(
      params.panel,
      { popoutUrl: '/popout.html' },
    )
  })

  it('closes the Dockview popout window instead of opening another one', async () => {
    const close = vi.fn()
    const params = createTabParams({ type: 'popout', getWindow: () => ({ close }) })
    const wrapper = mount(AvivatorTab, { props: { params } })

    await wrapper.find('[data-testid="avivator-tab-window-toggle"]').trigger('click')

    expect(close).toHaveBeenCalledOnce()
    expect(params.mocks.containerApi.addPopoutGroup).not.toHaveBeenCalled()
  })

  it('keeps the close-tab action available', async () => {
    const params = createTabParams()
    const wrapper = mount(AvivatorTab, { props: { params } })

    await wrapper.find('[data-testid="avivator-tab-close"]').trigger('click')

    expect(params.mocks.api.close).toHaveBeenCalledOnce()
  })
})
