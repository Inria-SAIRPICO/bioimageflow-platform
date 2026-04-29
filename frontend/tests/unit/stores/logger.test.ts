import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { ALL_LEVELS, useLoggerStore } from '@/stores/logger'

function entry(message: string, level = 'INFO', nodeId: string | null = null, timestamp = 1) {
  return { level, message, nodeId, timestamp }
}

describe('logger store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with an empty buffer and default filters', () => {
    const store = useLoggerStore()
    expect(store.entries).toEqual([])
    expect(store.autoScroll).toBe(true)
    expect(store.filter.nodeId).toBeNull()
    expect(store.filter.searchText).toBe('')
    expect([...store.filter.levels].sort()).toEqual(['ERROR', 'INFO', 'WARNING'])
  })

  it('appends entries, accepts empty messages, and caps the ring buffer', () => {
    const store = useLoggerStore()
    store.addEntry(entry('', 'INFO', null, 0))
    expect(store.entries[0].message).toBe('')

    for (let i = 0; i < store.maxEntries + 1; i += 1) {
      store.addEntry(entry(`entry ${i}`, 'INFO', null, i))
    }
    expect(store.entries).toHaveLength(store.maxEntries)
    expect(store.entries[0].message).toBe('entry 1')
    expect(store.entries.at(-1)?.message).toBe(`entry ${store.maxEntries}`)
  })

  it('filters by level, node, and text with AND semantics', () => {
    const store = useLoggerStore()
    store.addEntry(entry('debug hello', 'DEBUG', 'n1', 1))
    store.addEntry(entry('failed hello', 'ERROR', 'n1', 2))
    store.addEntry(entry('failed elsewhere', 'ERROR', 'n2', 3))

    store.setFilter({
      levels: new Set(['ERROR']),
      nodeId: 'n1',
      searchText: 'HELLO',
    })

    expect(store.filteredEntries.map((e) => e.message)).toEqual(['failed hello'])
  })

  it('supports non-contiguous and empty level selections', () => {
    const store = useLoggerStore()
    store.addEntry(entry('debug', 'DEBUG'))
    store.addEntry(entry('info', 'INFO'))
    store.addEntry(entry('warning', 'WARNING'))
    store.addEntry(entry('error', 'ERROR'))

    store.setFilter({ levels: new Set(['DEBUG', 'ERROR']) })
    expect(store.filteredEntries.map((e) => e.message)).toEqual(['debug', 'error'])

    store.setFilter({ levels: new Set() })
    expect(store.filteredEntries).toEqual([])
    expect(store.minimumActiveLevel).toBeNull()
  })

  it('shows unknown levels only when all known levels are active', () => {
    const store = useLoggerStore()
    store.addEntry(entry('critical', 'CRITICAL'))
    store.addEntry(entry('info', 'INFO'))

    store.setFilter({ levels: new Set(ALL_LEVELS) })
    expect(store.filteredEntries.map((e) => e.message)).toEqual(['critical', 'info'])

    store.setFilter({ levels: new Set(['INFO', 'WARNING', 'ERROR']) })
    expect(store.filteredEntries.map((e) => e.message)).toEqual(['info'])
  })

  it('returns per-node entries without display filters', () => {
    const store = useLoggerStore()
    store.addEntry(entry('node', 'INFO', 'n1'))
    store.addEntry(entry('system', 'INFO', null, 2))

    expect(store.nodeEntries('n1').value.map((e) => e.message)).toEqual(['node'])
    expect(store.nodeEntries('missing').value).toEqual([])
  })

  it('merges filter updates, toggles levels, and preserves settings on clear', () => {
    const store = useLoggerStore()
    const initialLevels = new Set(store.filter.levels)

    store.setFilter({ nodeId: 'n1' })
    expect(store.filter.nodeId).toBe('n1')
    expect(store.filter.levels).toEqual(initialLevels)

    store.toggleLevel('DEBUG')
    expect(store.filter.levels.has('DEBUG')).toBe(true)
    store.toggleLevel('INFO')
    expect(store.filter.levels.has('INFO')).toBe(false)

    store.addEntry(entry('one'))
    store.setAutoScroll(false)
    store.clearEntries()
    expect(store.entries).toEqual([])
    expect(store.filter.nodeId).toBe('n1')
    expect(store.autoScroll).toBe(false)
  })

  it('tracks last server subscription state', () => {
    const store = useLoggerStore()
    expect(store.getLastSubscription()).toEqual({ nodeId: null, level: null })
    store.setLastSubscription({ nodeId: 'n1', level: 'WARNING' })
    expect(store.getLastSubscription()).toEqual({ nodeId: 'n1', level: 'WARNING' })
  })

  it('computes the minimum active server-side level', () => {
    const store = useLoggerStore()
    store.setFilter({ levels: new Set(['WARNING', 'ERROR']) })
    expect(store.minimumActiveLevel).toBe('WARNING')

    store.setFilter({ levels: new Set(['DEBUG', 'ERROR']) })
    expect(store.minimumActiveLevel).toBe('DEBUG')

    store.setFilter({ levels: new Set(ALL_LEVELS) })
    expect(store.minimumActiveLevel).toBeNull()

    store.setFilter({ levels: new Set() })
    expect(store.minimumActiveLevel).toBeNull()
  })

  it('maintains insertion order across rapid adds and after clearing', () => {
    const store = useLoggerStore()
    for (let i = 0; i < 100; i += 1) {
      store.addEntry(entry(`entry ${i}`, 'INFO', null, i))
    }
    expect(store.entries.map((e) => e.message).slice(0, 3)).toEqual([
      'entry 0',
      'entry 1',
      'entry 2',
    ])
    expect(store.entries.at(-1)?.message).toBe('entry 99')

    store.clearEntries()
    store.addEntry(entry('fresh'))
    expect(store.entries.map((e) => e.message)).toEqual(['fresh'])
  })
})
