import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MissingPackageDialog from '../MissingPackageDialog.vue'
import type { MissingPackage } from '@/api/types'

const missingPackage: MissingPackage = {
  package_name: 'common',
  required_version: '1.2.3',
  installed_versions: [],
  affected_nodes: ['generate'],
}

function mountDialog(overrides: Record<string, unknown> = {}) {
  return mount(MissingPackageDialog, {
    props: {
      visible: true,
      packages: [missingPackage],
      tools: [],
      ...overrides,
    },
    global: {
      stubs: {
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
        },
        Button: {
          props: ['label', 'disabled'],
          emits: ['click'],
          template: '<button :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
        },
      },
    },
  })
}

describe('MissingPackageDialog', () => {
  it('offers exact-version installation as the primary dependency action', async () => {
    const wrapper = mountDialog()

    const install = wrapper.get('[data-testid="missing-package-install-all"]')
    expect(install.text()).toBe('Install all missing packages')
    expect(wrapper.find('[data-testid="missing-package-rebind"]').exists()).toBe(false)

    await install.trigger('click')
    expect(wrapper.emitted('install-all')).toHaveLength(1)
  })

  it('shows installed-alternative rebinding only when the parent allows it', async () => {
    const wrapper = mountDialog({ canRebind: true })

    const rebind = wrapper.get('[data-testid="missing-package-rebind"]')
    expect(rebind.text()).toBe('Use installed alternatives…')
    await rebind.trigger('click')

    expect(wrapper.emitted('rebind')).toHaveLength(1)
  })

  it('shows bulk-install progress and disables dialog actions', () => {
    const wrapper = mountDialog({
      installing: true,
      installProgress: 'Installing 1 of 2: common 1.2.3',
    })

    expect(wrapper.get('[role="status"]').text()).toContain('Installing 1 of 2')
    expect(wrapper.get('[data-testid="missing-package-install-all"]').attributes('disabled'))
      .toBeDefined()
  })

  it('shows the error for the package version that failed', () => {
    const wrapper = mountDialog({
      installErrors: {
        'common@1.2.3': 'Package index unavailable',
      },
    })

    expect(wrapper.get('.dependency-error').text()).toBe('Package index unavailable')
  })
})
