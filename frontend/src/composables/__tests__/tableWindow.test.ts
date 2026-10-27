import { describe, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createTableWindow } from '../tableWindow'

describe('bounded table blocks', () => {
  it('shares overlapping reads, caps resident payloads and reloads evicted blocks upward', async () => {
    const window = createTableWindow<number[]>(4, 2)
    const calls: number[] = []
    const load = async (page: number) => { calls.push(page); return [page * 4, page * 4 + 1] }
    window.seed(0, [0, 1])
    window.range(4, 8, 16, load)
    window.range(4, 8, 16, load)
    await flushPromises()
    expect(calls.filter(page => page === 1)).toHaveLength(1)
    expect(window.blocks.size).toBeLessThanOrEqual(2)
    window.range(12, 16, 16, load)
    await flushPromises()
    expect(window.blocks.has(0)).toBe(false)
    window.range(0, 4, 16, load)
    await flushPromises()
    expect(calls).toContain(0)
    expect(window.blocks.get(0)).toEqual([0, 1])
    expect(window.blocks.size).toBeLessThanOrEqual(2)
  })

  it('drops late old-generation replies even when the transport ignores abort', async () => {
    const window = createTableWindow<string>(4)
    let finish!: (value: string) => void
    let signal!: AbortSignal
    window.range(0, 4, 4, (_page, selectedSignal) => {
      signal = selectedSignal
      return new Promise(resolve => { finish = resolve })
    })
    window.reset()
    expect(signal.aborted).toBe(true)
    window.seed(0, 'new result')
    finish('old result')
    await flushPromises()
    expect(window.blocks.get(0)).toBe('new result')
  })

  it('does not loop permanent failures and retries only after an explicit action', async () => {
    const window = createTableWindow<string>(4)
    let reads = 0
    let fail = true
    const load = async () => { reads += 1; if (fail) throw new Error('Result unavailable'); return 'ready' }
    window.range(0, 4, 4, load)
    await flushPromises()
    window.range(0, 4, 4, load)
    await flushPromises()
    expect(reads).toBe(1)
    expect(window.errors.get(0)).toBe('Result unavailable')
    fail = false
    window.retry()
    await flushPromises()
    expect(reads).toBe(2)
    expect(window.blocks.get(0)).toBe('ready')
  })

  it('bounds failed blocks and retries only the visible failed range', async () => {
    const window = createTableWindow<string>(4, 1)
    const calls: number[] = []
    const load = async (page: number) => { calls.push(page); throw new Error(`Failed block ${page}`) }
    for (const start of [0, 4, 8]) {
      window.range(start, start + 4, 12, load)
      await flushPromises()
      expect(window.errors.size).toBeLessThanOrEqual(1)
    }
    expect([...window.errors.keys()]).toEqual([2])
    calls.length = 0
    window.retry()
    await flushPromises()
    expect(calls).toEqual([2])
    expect(window.errors.size).toBe(1)
  })
})
