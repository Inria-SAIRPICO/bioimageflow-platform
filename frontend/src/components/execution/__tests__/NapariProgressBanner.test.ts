import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'

import NapariProgressBanner from '../NapariProgressBanner.vue'
import { useNapariStore } from '@/stores/napari'

function mountBanner() {
  return mount(NapariProgressBanner, {
    global: {
      plugins: [[PrimeVue, { theme: { preset: Aura } }]],
    },
  })
}

describe('NapariProgressBanner', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('is hidden when no Napari open request is pending', () => {
    const wrapper = mountBanner()

    expect(wrapper.find('[data-testid="napari-progress-banner"]').exists()).toBe(false)
  })

  it('shows installation progress while the Napari environment is being created', async () => {
    const wrapper = mountBanner()
    const napari = useNapariStore()

    napari.requestPending = true
    napari.applyEnvironmentStatus({
      env_name: 'napari',
      status: 'creating',
    })
    await nextTick()

    expect(wrapper.find('[data-testid="napari-progress-headline"]').text())
      .toBe('Installing Napari…')
    expect(wrapper.find('[data-testid="napari-progress-bar"]').exists()).toBe(true)
  })

  it('shows opening progress while the installed Napari environment launches', async () => {
    const wrapper = mountBanner()
    const napari = useNapariStore()

    napari.requestPending = true
    napari.applyEnvironmentStatus({
      env_name: 'napari',
      status: 'opening',
    })
    await nextTick()

    expect(wrapper.find('[data-testid="napari-progress-headline"]').text())
      .toBe('Opening in Napari…')
  })
})
