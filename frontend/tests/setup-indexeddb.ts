import { IDBFactory } from 'fake-indexeddb'
import { beforeEach } from 'vitest'

beforeEach(() => {
  Object.defineProperty(globalThis, 'indexedDB', {
    configurable: true,
    value: new IDBFactory(),
  })
})
