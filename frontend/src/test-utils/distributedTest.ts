import { it } from 'vitest'
import { DISTRIBUTED_TAG } from './testSuite'

/** Declare an optional distributed feature case, visible in native test reports. */
export function distributedTest(name: string, handler: () => void | Promise<void>) {
  return it(`${name} ${DISTRIBUTED_TAG}`, handler)
}
