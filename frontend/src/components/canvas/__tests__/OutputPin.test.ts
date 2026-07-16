import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import OutputPin from '../OutputPin.vue'

vi.mock('@vue-flow/core', () => ({
  Handle: defineComponent({
    name: 'Handle',
    props: ['type', 'position', 'id'],
    template: '<div class="mock-handle" />',
  }),
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
}))

describe('OutputPin', () => {
  function factory(props: Record<string, unknown>) {
    return mount(OutputPin, { props: props as any })
  }

  it('renders field name', () => {
    const w = factory({ fieldName: 'result', fieldType: 'ImageFile' })
    expect(w.find('.pin-label').text()).toBe('result')
  })

  it('renders the display name without changing the handle field name', () => {
    const w = factory({
      fieldName: 'output_image',
      displayName: 'Output image',
      fieldType: 'ImageFile',
    })
    expect(w.find('.pin-label').text()).toBe('Output image')
  })

  it('renders type badge', () => {
    const w = factory({ fieldName: 'result', fieldType: 'ImageFile' })
    expect(w.find('.type-badge').text()).toBe('ImageFile')
  })

  it('applies correct handle color', () => {
    const w = factory({ fieldName: 'result', fieldType: 'ImageFile' })
    expect(w.find('.pin-handle').attributes('style')).toContain('background-color: rgb(74, 144, 217)')
  })

  it('uses default color for unknown types', () => {
    const w = factory({ fieldName: 'out', fieldType: 'UnknownType' })
    // #8E8E93 = rgb(142, 142, 147)
    expect(w.find('.pin-handle').attributes('style')).toContain('background-color: rgb(142, 142, 147)')
  })

  it('shows type in tooltip', () => {
    const w = factory({ fieldName: 'result', fieldType: 'Path' })
    expect(w.find('.output-pin').attributes('title')).toBe('Path')
  })

  // --- Phase 3: variant prop ---

  describe('variant prop', () => {
    it('defaults to body variant with round pin styling', () => {
      const w = factory({ fieldName: 'result', fieldType: 'ImageFile' })
      expect(w.find('.output-pin').classes()).not.toContain('output-pin--header')
    })

    it('header variant adds output-pin--header class', () => {
      const w = factory({ fieldName: '__dataframe_out', fieldType: 'DataFrame', variant: 'header' })
      expect(w.find('.output-pin').classes()).toContain('output-pin--header')
    })

    it('header variant renders square pin (no border-radius 50%)', () => {
      const w = factory({ fieldName: '__dataframe_out', fieldType: 'DataFrame', variant: 'header' })
      const handle = w.find('.pin-handle')
      expect(handle.classes()).toContain('pin-handle--header')
    })

    it('body variant does not add header class', () => {
      const w = factory({ fieldName: 'result', fieldType: 'ImageFile', variant: 'body' })
      expect(w.find('.output-pin').classes()).not.toContain('output-pin--header')
    })
  })
})
