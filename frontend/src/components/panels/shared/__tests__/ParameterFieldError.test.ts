import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import ParameterFieldError from '../ParameterFieldError.vue'
import type { GraphValidationError } from '@/api/types'

const noErrors: GraphValidationError[] = []

const oneError: GraphValidationError[] = [
  { type: 'parameter_invalid', detail: 'Must be > 0', node: 'n1', field: 'x' },
]

const twoErrors: GraphValidationError[] = [
  { type: 'parameter_invalid', detail: 'Must be > 0', node: 'n1', field: 'x' },
  {
    type: 'parameter_invalid',
    detail: 'Must be a multiple of 2',
    node: 'n1',
    field: 'x',
  },
]

function mountWithSlot(errors: GraphValidationError[]) {
  return mount(ParameterFieldError, {
    props: { errors },
    slots: {
      default: () => h('input', { 'data-testid': 'inner-input', type: 'text' }),
    },
  })
}

describe('ParameterFieldError', () => {
  it('renders the slot content', () => {
    const wrapper = mountWithSlot(noErrors)
    expect(wrapper.find('[data-testid="inner-input"]').exists()).toBe(true)
  })

  it('does NOT apply has-error when errors prop is empty', () => {
    const wrapper = mountWithSlot(noErrors)
    expect(wrapper.classes()).not.toContain('has-error')
  })

  it('applies has-error class when errors prop is non-empty', () => {
    const wrapper = mountWithSlot(oneError)
    expect(wrapper.classes()).toContain('has-error')
  })

  it('sets aria-invalid="true" when there are errors', () => {
    const wrapper = mountWithSlot(oneError)
    expect(wrapper.attributes('aria-invalid')).toBe('true')
  })

  it('does NOT set aria-invalid when there are no errors', () => {
    const wrapper = mountWithSlot(noErrors)
    const aria = wrapper.attributes('aria-invalid')
    expect(aria === undefined || aria === 'false').toBe(true)
  })

  it('renders a hidden description element with the joined details', () => {
    const wrapper = mountWithSlot(twoErrors)
    const desc = wrapper.find('[data-testid="param-error-desc"]')
    expect(desc.exists()).toBe(true)
    expect(desc.text()).toContain('Must be > 0')
    expect(desc.text()).toContain('Must be a multiple of 2')
  })

  it('aria-describedby points to the description element id', () => {
    const wrapper = mountWithSlot(oneError)
    const describedBy = wrapper.attributes('aria-describedby')
    const desc = wrapper.find('[data-testid="param-error-desc"]')
    expect(describedBy).toBeTruthy()
    expect(desc.attributes('id')).toBe(describedBy)
  })

  it('renders no description element when errors empty', () => {
    const wrapper = mountWithSlot(noErrors)
    expect(wrapper.find('[data-testid="param-error-desc"]').exists()).toBe(
      false,
    )
  })

  it('exposes the first error detail as a title attribute (native tooltip)', () => {
    const wrapper = mountWithSlot(oneError)
    expect(wrapper.attributes('title')).toBe('Must be > 0')
  })

  it('joins multiple error details into the title attribute', () => {
    const wrapper = mountWithSlot(twoErrors)
    const title = wrapper.attributes('title')
    expect(title).toContain('Must be > 0')
    expect(title).toContain('Must be a multiple of 2')
  })
})
