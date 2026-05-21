import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import OpenWorkflowDialog from '../OpenWorkflowDialog.vue'
import type { WorkflowInfo } from '@/api/types'

const workflows: WorkflowInfo[] = [
  {
    id: 'A/nuclei',
    name: 'nuclei',
    folder: 'A',
    display_name: 'Nuclei A',
    path: '/workspace/workflows/A/nuclei/workflow.json',
    last_modified: '2026-05-01T08:00:00Z',
  },
  {
    id: 'B/nuclei',
    name: 'nuclei',
    folder: 'B',
    display_name: 'Nuclei B',
    path: '/workspace/workflows/B/nuclei/workflow.json',
    last_modified: '2026-05-01T09:00:00Z',
  },
]

function mountDialog(currentName = 'B/nuclei') {
  return mount(OpenWorkflowDialog, {
    props: {
      visible: true,
      workflows,
      currentName,
    },
    global: {
      plugins: [PrimeVue],
      stubs: {
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot name="header" /><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

describe('OpenWorkflowDialog', () => {
  it('uses full workflow ids for duplicate leaf names', async () => {
    const wrapper = mountDialog()

    await wrapper.find('[data-testid="workflow-open-option-B_nuclei"]').trigger('click')
    await wrapper.find('[data-testid="workflow-open-submit"]').trigger('click')

    expect(wrapper.emitted('open')?.[0]).toEqual(['B/nuclei'])
  })

  it('searches by full workflow id', async () => {
    const wrapper = mountDialog('A/nuclei')

    await wrapper.find('[data-testid="workflow-open-search"]').setValue('B/')

    expect(wrapper.find('[data-testid="workflow-open-option-A_nuclei"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="workflow-open-option-B_nuclei"]').exists()).toBe(true)
  })
})
