import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import InputPin from '../InputPin.vue'

vi.mock('@vue-flow/core', () => ({
  Handle: defineComponent({
    name: 'Handle',
    props: ['type', 'position', 'id'],
    template: '<div class="mock-handle" />',
  }),
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
}))

describe('InputPin', () => {
  function factory(props: Record<string, unknown>) {
    return mount(InputPin, { props: props as any })
  }

  it('renders field name as label when disconnected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImagePath', connected: false })
    expect(w.find('.pin-label').text()).toBe('image')
  })

  it('shows field type in tooltip (title attribute)', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImagePath', connected: false })
    expect(w.find('.input-pin').attributes('title')).toBe('ImagePath')
  })

  it('adds .connected class when connected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImagePath', connected: true })
    expect(w.find('.pin-handle').classes()).toContain('connected')
  })

  it('does not add .connected class when disconnected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImagePath', connected: false })
    expect(w.find('.pin-handle').classes()).not.toContain('connected')
  })

  it('shows sourceLabel when connected', () => {
    const w = factory({
      fieldName: 'image',
      fieldType: 'ImagePath',
      connected: true,
      sourceLabel: 'Loader.output',
    })
    expect(w.find('.pin-label').text()).toBe('Loader.output')
  })

  it('applies correct border-color from getTypeColor', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImagePath', connected: false })
    const handle = w.find('.pin-handle')
    expect(handle.attributes('style')).toContain('border-color: rgb(74, 144, 217)')
  })

  it('fills background when connected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImagePath', connected: true })
    const handle = w.find('.pin-handle')
    expect(handle.attributes('style')).toContain('background-color: rgb(74, 144, 217)')
  })

  it('transparent background when disconnected', () => {
    const w = factory({ fieldName: 'image', fieldType: 'ImagePath', connected: false })
    const handle = w.find('.pin-handle')
    expect(handle.attributes('style')).toContain('background-color: transparent')
  })

  it('shows positional index number in positional mode', () => {
    const w = factory({
      fieldName: '__positional_0',
      fieldType: 'DataFrame',
      connected: false,
      positional: true,
      positionalIndex: 0,
    })
    expect(w.find('.pin-label').text()).toBe('1')
  })

  it('shows positional index 3 as "4"', () => {
    const w = factory({
      fieldName: '__positional_3',
      fieldType: 'DataFrame',
      connected: false,
      positional: true,
      positionalIndex: 3,
    })
    expect(w.find('.pin-label').text()).toBe('4')
  })
})
