import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import InputNumber from 'primevue/inputnumber'
import ParameterRow from '../ParameterRow.vue'
import type { InputFieldSchema } from '@/api/types'
const field: InputFieldSchema = { type: 'float', required: false, nullable: true, connectable: 'not_by_default', min: 0, max: 1, step: .000001 }
function row(props: Record<string, unknown> = {}) {
  return mount(ParameterRow, { props: { fieldKey: 'p', field, value: .001, errors: [], ...props }, global: { plugins: [PrimeVue] } })
}
describe('shared parameter row', () => {
  it('uses full scientific precision and spinner controls alongside a slider', async () => {
    const wrapper = row()
    const number = wrapper.getComponent(InputNumber)
    expect(number.props('maxFractionDigits')).toBe(20)
    expect(number.props('showButtons')).toBe(true)
    await wrapper.get('.p-inputnumber-increment-button').trigger('mousedown', { button: 0 })
    await wrapper.get('.p-inputnumber-increment-button').trigger('mouseup')
    expect(wrapper.emitted('updateValue')?.[0]).toEqual([.001001])
    wrapper.unmount()
  })
  it('shows a connected source before a retained null and refuses hiding the pin', () => {
    const wrapper = row({ value: null, connectedSource: 'source.p', canPin: true })
    expect(wrapper.get('.connected-source').text()).toBe('source.p')
    expect(wrapper.find('.null-indicator').exists()).toBe(false)
    expect(wrapper.get('[data-testid="pin-toggle"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="reset-default"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('distinguishes inherited unset from explicit None and reset emits no value', async () => {
    const wrapper = row({ value: undefined, inherited: true })
    expect(wrapper.get('input').attributes('placeholder')).toBe('Inherited / unset')
    expect(wrapper.getComponent(InputNumber).props('modelValue')).toBeNull()
    await wrapper.get('[data-testid="none-toggle"]').trigger('click')
    expect(wrapper.emitted('updateValue')).toEqual([[null]])
    await wrapper.get('[data-testid="reset-default"]').trigger('click')
    expect(wrapper.emitted('reset')).toEqual([[]])
    wrapper.unmount()
  })
  it('retains invalid JSON through an equivalent external array projection', async () => {
    const wrapper = row({ field: { ...field, type: 'list' }, value: [1] })
    await wrapper.get('textarea').setValue('{')
    await wrapper.setProps({ value: [1], inherited: true })
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('{')
    expect(wrapper.find('.list-input-error').exists()).toBe(true)
    await wrapper.setProps({ value: [2] })
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toContain('2')
    expect(wrapper.find('.list-input-error').exists()).toBe(false)
    wrapper.unmount()
  })
  it('keeps malformed list text local and accepts tuple values as arrays', async () => {
    const wrapper = row({ field: { ...field, type: 'tuple' }, value: [1] })
    await wrapper.get('textarea').setValue('{')
    expect(wrapper.emitted('updateValue')).toBeUndefined()
    expect(wrapper.get('.list-input-error').text()).not.toBe('')
    await wrapper.get('textarea').setValue('[2, null]')
    expect(wrapper.emitted('updateValue')).toEqual([[[2, null]]])
    wrapper.unmount()
  })
})
