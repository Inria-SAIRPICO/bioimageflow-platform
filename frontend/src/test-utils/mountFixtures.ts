import { defineComponent, h, type Plugin } from 'vue'
import type { MountingOptions } from '@vue/test-utils'
import type { Pinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'

type TestGlobalMountOptions = NonNullable<
  MountingOptions<Record<string, unknown>>['global']
>

export const visibleDialogStub = defineComponent({
  name: 'TestDialog',
  inheritAttrs: false,
  props: {
    visible: { type: Boolean, default: false },
  },
  setup(props, { attrs, slots }) {
    return () => props.visible
      ? h('div', attrs, [slots.default?.(), slots.footer?.()])
      : null
  },
})

export interface PrimeVueTestGlobalOptions {
  pinia?: Pinia
  dialog?: boolean
  plugins?: Plugin[]
  stubs?: TestGlobalMountOptions['stubs']
}

/** Consistent PrimeVue theme and optional Pinia/Dialog setup for component tests. */
export function primeVueTestGlobal(
  options: PrimeVueTestGlobalOptions = {},
): TestGlobalMountOptions {
  const plugins: NonNullable<TestGlobalMountOptions['plugins']> = [
    [PrimeVue, { theme: { preset: Aura } }],
  ]
  if (options.pinia) plugins.push(options.pinia)
  if (options.plugins) plugins.push(...options.plugins)
  return {
    plugins,
    stubs: {
      ...(options.dialog ? { Dialog: visibleDialogStub } : {}),
      ...options.stubs,
    },
  }
}
