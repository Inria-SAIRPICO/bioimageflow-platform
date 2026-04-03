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
    const w = factory({ fieldName: 'result', fieldType: 'ImagePath' })
    expect(w.find('.pin-label').text()).toBe('result')
  })

  it('renders type badge', () => {
    const w = factory({ fieldName: 'result', fieldType: 'ImagePath' })
    expect(w.find('.type-badge').text()).toBe('ImagePath')
  })

  it('applies correct dot color', () => {
    const w = factory({ fieldName: 'result', fieldType: 'ImagePath' })
    expect(w.find('.pin-dot').attributes('style')).toContain('background-color: rgb(74, 144, 217)')
  })

  it('uses default color for unknown types', () => {
    const w = factory({ fieldName: 'out', fieldType: 'UnknownType' })
    // #8E8E93 = rgb(142, 142, 147)
    expect(w.find('.pin-dot').attributes('style')).toContain('background-color: rgb(142, 142, 147)')
  })

  it('shows type in tooltip', () => {
    const w = factory({ fieldName: 'result', fieldType: 'Path' })
    expect(w.find('.output-pin').attributes('title')).toBe('Path')
  })
})
