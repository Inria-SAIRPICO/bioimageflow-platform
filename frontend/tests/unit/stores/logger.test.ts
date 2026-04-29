import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLoggerStore } from '@/stores/logger'

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

  it('caps the ring buffer at maxEntries', () => {
    const store = useLoggerStore()
    for (let i = 0; i < store.maxEntries + 1; i += 1) {
      store.addEntry({
        level: 'INFO',
        message: `entry ${i}`,
        nodeId: null,
        timestamp: i,
      })
    }
    expect(store.entries).toHaveLength(store.maxEntries)
    expect(store.entries[0].message).toBe('entry 1')
  })

  it('filters by level, node, and text with AND semantics', () => {
    const store = useLoggerStore()
    store.addEntry({ level: 'DEBUG', message: 'debug hello', nodeId: 'n1', timestamp: 1 })
    store.addEntry({ level: 'ERROR', message: 'failed hello', nodeId: 'n1', timestamp: 2 })
    store.addEntry({ level: 'ERROR', message: 'failed elsewhere', nodeId: 'n2', timestamp: 3 })

    store.setFilter({
      levels: new Set(['ERROR']),
      nodeId: 'n1',
      searchText: 'HELLO',
    })

    expect(store.filteredEntries).toHaveLength(1)
    expect(store.filteredEntries[0].message).toBe('failed hello')
  })

  it('returns no entries when no levels are active', () => {
    const store = useLoggerStore()
    store.addEntry({ level: 'ERROR', message: 'failed', nodeId: null, timestamp: 1 })
    store.setFilter({ levels: new Set() })
    expect(store.filteredEntries).toEqual([])
    expect(store.minimumActiveLevel).toBeNull()
  })

  it('computes the minimum active server-side level', () => {
    const store = useLoggerStore()
    store.setFilter({ levels: new Set(['WARNING', 'ERROR']) })
    expect(store.minimumActiveLevel).toBe('WARNING')

    store.setFilter({ levels: new Set(['DEBUG', 'ERROR']) })
    expect(store.minimumActiveLevel).toBe('DEBUG')

    store.setFilter({ levels: new Set(['DEBUG', 'INFO', 'WARNING', 'ERROR']) })
    expect(store.minimumActiveLevel).toBeNull()
  })

  it('returns per-node entries without display filters', () => {
    const store = useLoggerStore()
    store.addEntry({ level: 'INFO', message: 'node', nodeId: 'n1', timestamp: 1 })
    store.addEntry({ level: 'INFO', message: 'system', nodeId: null, timestamp: 2 })

    expect(store.nodeEntries('n1').value.map((entry) => entry.message)).toEqual([
      'node',
    ])
  })

  it('clears entries while preserving filter and auto-scroll settings', () => {
    const store = useLoggerStore()
    store.addEntry({ level: 'INFO', message: 'one', nodeId: null, timestamp: 1 })
    store.setFilter({ nodeId: 'n1' })
    store.setAutoScroll(false)

    store.clearEntries()

    expect(store.entries).toEqual([])
    expect(store.filter.nodeId).toBe('n1')
    expect(store.autoScroll).toBe(false)
  })
})
