import { config } from '@vue/test-utils'
import { PrimeVueConfirmSymbol } from 'primevue/useconfirm'
import { PrimeVueToastSymbol } from 'primevue/usetoast'

const testToastService = {
  add: () => undefined,
  remove: () => undefined,
  removeGroup: () => undefined,
  removeAllGroups: () => undefined,
}

const testConfirmationService = {
  require: () => undefined,
  close: () => undefined,
}

config.global.provide = {
  ...config.global.provide,
  [PrimeVueToastSymbol]: testToastService,
  [PrimeVueConfirmSymbol]: testConfirmationService,
}

if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    media: '',
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }) as unknown as MediaQueryList
}
