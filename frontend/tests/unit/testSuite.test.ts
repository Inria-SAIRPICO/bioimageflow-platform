import { describe, expect, it } from 'vitest'
import type { Task } from '@vitest/runner'
import { includesTest, readTestSuite, suiteGrepInvert } from '../../src/test-utils/testSuite'
import { selectTasks } from '../suiteRunner'

describe('feature suite selection', () => {
  it('defaults to local and rejects misspelled suites', () => {
    expect(readTestSuite('local')).toBe('local')
    expect(readTestSuite('distributed')).toBe('distributed')
    expect(readTestSuite('all')).toBe('all')
    expect(() => readTestSuite('typo')).toThrow('Unknown test suite')
  })

  it('partitions local and distributed tests without losing either group', () => {
    expect([false, true].filter(distributed => includesTest('local', distributed))).toEqual([false])
    expect([false, true].filter(distributed => includesTest('distributed', distributed))).toEqual([true])
    expect([false, true].filter(distributed => includesTest('all', distributed))).toEqual([false, true])
  })

  it.each(['local', 'distributed', 'all'] as const)('keeps browser critical filters inside the %s suite', (suite) => {
    const excluded = suiteGrepInvert(suite)
    const tests = ['ordinary @critical', 'remote @critical @distributed', 'remote @distributed']
    const selected = tests.filter(name => /@critical/.test(name) && !excluded?.test(name))
    expect(selected).toEqual(suite === 'local'
      ? ['ordinary @critical']
      : suite === 'distributed' ? ['remote @critical @distributed'] : tests.slice(0, 2))
  })

  it('skips unselected unit suites before hooks while retaining native skip decisions', () => {
    const local = { type: 'test', name: 'local', mode: 'run' }
    const remote = { type: 'test', name: 'remote @distributed', mode: 'run' }
    const skipped = { type: 'test', name: 'pending @distributed', mode: 'skip' }
    const localSuite = { type: 'suite', mode: 'run', tasks: [local] }
    const remoteSuite = { type: 'suite', mode: 'run', tasks: [remote, skipped] }
    const emptySuite = { type: 'suite', mode: 'run', tasks: [] }
    selectTasks([localSuite, remoteSuite, emptySuite] as Task[], 'distributed')
    expect(local.mode).toBe('skip')
    expect(localSuite.mode).toBe('skip')
    expect(remote.mode).toBe('run')
    expect(remoteSuite.mode).toBe('run')
    expect(skipped.mode).toBe('skip')
    expect(emptySuite.mode).toBe('run')
  })
})
