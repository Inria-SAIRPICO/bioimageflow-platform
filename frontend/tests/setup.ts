import 'fake-indexeddb/auto'

import { config } from '@vue/test-utils'
import { IDBFactory } from 'fake-indexeddb'
import { PrimeVueConfirmSymbol } from 'primevue/useconfirm'
import { PrimeVueToastSymbol } from 'primevue/usetoast'
import { beforeEach } from 'vitest'

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

beforeEach(() => {
  Object.defineProperty(globalThis, 'indexedDB', {
    configurable: true,
    value: new IDBFactory(),
  })
})
