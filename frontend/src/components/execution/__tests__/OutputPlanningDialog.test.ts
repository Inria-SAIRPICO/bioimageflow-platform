import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'
import { makeOutputPlanningReport } from '@/test-utils/outputPlanningFixtures'
import OutputPlanningDialog from '../OutputPlanningDialog.vue'

function mountDialog(report = makeOutputPlanningReport(), extra = {}) {
  return mount(OutputPlanningDialog, {
    props: { report, ...extra },
    global: primeVueTestGlobal({ dialog: true }),
  })
}

describe('OutputPlanningDialog', () => {
  it('explains token expansion, ownership and the consequences of the explicit edit', async () => {
    const wrapper = mountDialog()
    expect(wrapper.text()).toContain('Six rows produce the same filename')
    expect(wrapper.get('[data-testid="output-template-expansion"]').text()).toContain('{input_image.stem}')
    expect(wrapper.text()).toContain('literal text')
    expect(wrapper.text()).toContain('One file per input row')
    expect(wrapper.text()).toContain('downstream tools that interpret')
    const input = wrapper.get<HTMLInputElement>('[data-testid="collision-template-output_image"]')
    expect(input.element.value).toContain('{row_index}')
    await input.setValue('custom_{row_index}.ome.tif')
    await wrapper.get('[data-testid="apply-output-correction"]').trigger('click')
    expect(wrapper.emitted('submit')).toEqual([[{ output_image: 'custom_{row_index}.ome.tif' }]])
  })

  it('cancels without submitting any template change', async () => {
    const wrapper = mountDialog()
    await wrapper.get('[data-testid="cancel-output-correction"]').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('disables dismissal and both actions during submission', async () => {
    const wrapper = mountDialog(makeOutputPlanningReport(), { busy: true })
    expect(wrapper.get('[data-testid="cancel-output-correction"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="apply-output-correction"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="cancel-output-correction"]').trigger('click')
    expect(wrapper.emitted('cancel')).toBeUndefined()
  })

  it('retains custom input when a submitted template still conflicts', async () => {
    const wrapper = mountDialog()
    const input = wrapper.get<HTMLInputElement>('[data-testid="collision-template-output_image"]')
    await input.setValue('custom.tif')
    await wrapper.setProps({ validationReports: [makeOutputPlanningReport({ detail: 'The custom filename still collides.' })] })
    expect(input.element.value).toBe('custom.tif')
    expect(wrapper.text()).toContain('custom filename still collides')
  })

  it('explains group disagreement and disables expired correction evidence', () => {
    const wrapper = mountDialog(makeOutputPlanningReport({
      code: 'output_group_destination_mismatch', correction_available: false,
      correction_unavailable_reason: 'The original input evidence is no longer available.',
    }))
    expect(wrapper.text()).toContain('Rows contributing to one file')
    expect(wrapper.text()).toContain('edit the workflow normally')
    expect(wrapper.get('[data-testid="apply-output-correction"]').attributes('disabled')).toBeDefined()
  })
})
