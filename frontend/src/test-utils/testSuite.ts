export type TestSuite = 'local' | 'distributed' | 'all'

export const DISTRIBUTED_TAG = '@distributed'

export function readTestSuite(value = process.env.BIOIMAGEFLOW_TEST_SUITE ?? 'local'): TestSuite {
  if (value !== 'local' && value !== 'distributed' && value !== 'all') {
    throw new Error(`Unknown test suite: ${value}`)
  }
  return value
}

export function includesTest(suite: TestSuite, distributed: boolean): boolean {
  return suite === 'all' || distributed === (suite === 'distributed')
}

// Playwright intersects grepInvert with user-supplied file/title/critical filters.
export function suiteGrepInvert(suite: TestSuite): RegExp | undefined {
  if (suite === 'local') return /@distributed\b/
  if (suite === 'distributed') return /^(?!.*@distributed\b)/
  return undefined
}
