import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import PathCell from '../PathCell.vue'

describe('PathCell', () => {
  it('anchors overflowing path text to its right edge so the filename stays visible', () => {
    const path = '/Users/researcher/shared/experiment/segmentation/cells.ome.tif'
    const wrapper = mount(PathCell, {
      props: { value: path, showActions: false },
      global: { plugins: [PrimeVue] },
    })
    const display = wrapper.get('[data-testid="path-display"]')
    const value = display.get('.path-cell__path-value')

    expect(display.text()).toBe(path)
    expect(display.attributes('title')).toBe(path)
    expect(display.classes()).toContain('path-cell__path')
    expect(value.classes()).toContain('path-cell__path-value')
    expect(wrapper.text()).toContain('cells.ome.tif')
  })
})
