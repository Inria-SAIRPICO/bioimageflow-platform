import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AvivatorPanel from '../AvivatorPanel.vue'

describe('AvivatorPanel', () => {
  it('renders an iframe when Dockview passes direct params', () => {
    const wrapper = mount(AvivatorPanel, {
      props: {
        params: {
          url: 'http://avivator.gehlenborglab.org/?image_url=http%3A%2F%2Flocalhost%2Fimage.ome.tif',
          title: 'image.ome.tif',
        },
      },
    })

    const frame = wrapper.find('[data-testid="avivator-iframe"]')
    expect(frame.exists()).toBe(true)
    expect(frame.attributes('src')).toContain('image_url=')
    expect(frame.attributes('title')).toBe('Avivator - image.ome.tif')
    expect(wrapper.find('[data-testid="avivator-empty"]').exists()).toBe(false)
  })

  it('renders an iframe when Dockview wraps panel params', () => {
    const wrapper = mount(AvivatorPanel, {
      props: {
        params: {
          params: {
            url: 'http://avivator.gehlenborglab.org/?image_url=http%3A%2F%2Flocalhost%2Fimage.ome.tif',
            title: 'image.ome.tif',
          },
        },
      },
    })

    const frame = wrapper.find('[data-testid="avivator-iframe"]')
    expect(frame.exists()).toBe(true)
    expect(frame.attributes('src')).toContain('image_url=')
    expect(frame.attributes('title')).toBe('Avivator - image.ome.tif')
    expect(wrapper.find('[data-testid="avivator-empty"]').exists()).toBe(false)
  })
})
