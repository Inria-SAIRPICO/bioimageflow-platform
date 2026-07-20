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
