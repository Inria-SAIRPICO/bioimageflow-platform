import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import PathCell from '../PathCell.vue'

describe('PathCell', () => {
  it('keeps the full path while anchoring its visible text to the right', () => {
    const path = '/Users/researcher/shared/experiment/segmentation/cells.ome.tif'
    const wrapper = mount(PathCell, {
      props: { value: path, showActions: false },
      global: { plugins: [PrimeVue] },
    })
    const display = wrapper.get('[data-testid="path-display"]')

    expect(display.text()).toBe(path)
    expect(display.attributes('title')).toBe(path)
    expect(getComputedStyle(display.element).textAlign).toBe('right')
    expect(wrapper.text()).toContain('cells.ome.tif')
  })
})
