import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { NapariViewingReadinessOutput, NapariViewingReadinessResponse, NapariViewingRequirementGroup } from '@/api/types'
import ViewingRequirementsGuidance from '../ViewingRequirementsGuidance.vue'

const unknown: NapariViewingReadinessOutput = {
  output_identity: 'unresolved::tool-output/*', manifest_status: 'unknown', status: 'unknown',
  reason: 'manifest_unknown', manifest_reason: 'Tool declaration is unavailable',
  effective_reason: 'Tool declaration is unavailable',
}
const group: NapariViewingRequirementGroup = {
  id: 'reader-group', members: ['known::tool-output/image'],
  managed_create_prefill: {
    requested_packages: ['image-reader>=2'], package_source: 'unverified', requires_source_confirmation: false,
  },
}
const declared: NapariViewingReadinessOutput = {
  output_identity: 'known::tool-output/image', manifest_status: 'known', status: 'not_covered',
  reason: 'requirements_not_satisfied', group_id: group.id,
  effective_reason: 'Required image-reader is missing',
}

function mountGuidance(report: NapariViewingReadinessResponse) {
  return mount(ViewingRequirementsGuidance, {
    props: { workflowName: 'Analysis', report, pending: false, error: null },
  })
}

describe('ViewingRequirementsGuidance', () => {
  it('shows unknown tool/source diagnostics without offering viewer environment mutations', () => {
    const wrapper = mountGuidance({
      manifest_schema: 'bioimageflow.viewing_requirements.v1', manifest_complete: false,
      outputs: [unknown], groups: [],
      summary: {
        total_outputs: 1, covered_outputs: 0, not_covered_outputs: 0, unknown_outputs: 1,
        outputs_needing_setup: 0, message: 'Viewing requirements are unknown for 1 node',
      },
    })

    expect(wrapper.text()).toContain('Viewing requirements are unknown for 1 node')
    expect(wrapper.text()).toContain('Workflow execution is unaffected.')
    expect(wrapper.get('summary').text()).toBe('Tool/source details')
    expect(wrapper.text()).toContain('Tool declaration is unavailable')
    expect(wrapper.text()).toContain('Check the tool/source diagnostics')
    expect(wrapper.findAll('button').map(button => button.text())).toEqual(['Continue configuring later'])
    expect(wrapper.emitted('create')).toBeUndefined()
    expect(wrapper.emitted('manage')).toBeUndefined()
  })

  it('retains exact group actions alongside separate unknown metadata', async () => {
    const message = '1 output needs viewer setup; viewing requirements are unknown for 1 node'
    const wrapper = mountGuidance({
      manifest_schema: 'bioimageflow.viewing_requirements.v1', manifest_complete: false,
      outputs: [declared, unknown], groups: [group],
      summary: {
        total_outputs: 2, covered_outputs: 0, not_covered_outputs: 1, unknown_outputs: 1,
        outputs_needing_setup: 1, message,
      },
    })

    expect(wrapper.text()).toContain(message)
    expect(wrapper.get('summary').text()).toBe('Viewer setup details')
    expect(wrapper.text()).toContain('image-reader>=2')
    await wrapper.findAll('button').find(button => button.text() === 'Create environment for this set')!.trigger('click')
    expect(wrapper.emitted('create')).toEqual([[group]])
    await wrapper.findAll('button').find(button => button.text() === 'Manage/attach environments')!.trigger('click')
    expect(wrapper.emitted('manage')).toHaveLength(1)
    expect(wrapper.text()).toContain('Tool declaration is unavailable')
  })

  it('offers viewer management when a declared group has stale or unknown inventory', () => {
    const wrapper = mountGuidance({
      manifest_schema: 'bioimageflow.viewing_requirements.v1', manifest_complete: true,
      outputs: [{ ...declared, status: 'unknown', reason: 'requirements_not_verified', effective_reason: 'Inventory is stale' }],
      groups: [group],
      summary: {
        total_outputs: 1, covered_outputs: 0, not_covered_outputs: 0, unknown_outputs: 1,
        outputs_needing_setup: 1, message: '1 output needs viewer setup',
      },
    })

    expect(wrapper.text()).toContain('Inventory is stale')
    expect(wrapper.findAll('button').map(button => button.text())).toContain('Manage/attach environments')
    expect(wrapper.findAll('button').map(button => button.text())).toContain('Create environment for this set')
    expect(wrapper.text()).not.toContain('Check the tool/source diagnostics')
  })
})
