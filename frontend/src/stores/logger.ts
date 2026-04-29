import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export interface LogEntry {
  level: string
  message: string
  nodeId: string | null
  timestamp: number
}

export interface LogFilter {
  levels: Set<string>
  nodeId: string | null
  searchText: string
}

export interface LogSubscription {
  nodeId: string | null
  level: string | null
}

export const LEVEL_ORDER: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
}

export const ALL_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const
export const DEFAULT_LEVELS = new Set<string>(['INFO', 'WARNING', 'ERROR'])

const MAX_ENTRIES = 5000

function normalizeLevel(level: string): string {
  return level.toUpperCase()
}

function cloneDefaultFilter(): LogFilter {
  return {
    levels: new Set(DEFAULT_LEVELS),
    nodeId: null,
    searchText: '',
  }
}

export const useLoggerStore = defineStore('logger', () => {
  const entries = ref<LogEntry[]>([])
  const filter = ref<LogFilter>(cloneDefaultFilter())
  const autoScroll = ref(true)
  const lastSubscription = ref<LogSubscription>({ nodeId: null, level: null })
  const maxEntries = MAX_ENTRIES

  const filteredEntries = computed(() => {
    const { levels, nodeId, searchText } = filter.value
    if (levels.size === 0) return []

    const allKnownLevelsActive = ALL_LEVELS.every((level) => levels.has(level))
    const query = searchText.trim().toLowerCase()
    return entries.value.filter((entry) => {
      const level = normalizeLevel(entry.level)
      if (!levels.has(level)) {
        if (!allKnownLevelsActive || (ALL_LEVELS as readonly string[]).includes(level)) {
          return false
        }
      }
      if (nodeId !== null && entry.nodeId !== nodeId) return false
      if (query && !entry.message.toLowerCase().includes(query)) return false
      return true
    })
  })

  const minimumActiveLevel = computed<string | null>(() => {
    const levels = filter.value.levels
    if (levels.size === 0) return null
    const knownActive = ALL_LEVELS.filter((level) => levels.has(level))
    if (knownActive.length === ALL_LEVELS.length) return null
    if (knownActive.length === 0) return null
    return knownActive.reduce((lowest, level) =>
      LEVEL_ORDER[level] < LEVEL_ORDER[lowest] ? level : lowest,
    )
  })

  function addEntry(entry: LogEntry): void {
    entries.value.push({
      ...entry,
      level: normalizeLevel(entry.level),
      nodeId: entry.nodeId ?? null,
    })
    if (entries.value.length > maxEntries) {
      entries.value.splice(0, entries.value.length - maxEntries)
    }
  }

  function setFilter(next: Partial<LogFilter>): void {
    filter.value = {
      ...filter.value,
      ...next,
      levels: next.levels ? new Set(next.levels) : filter.value.levels,
    }
  }

  function toggleLevel(level: string): void {
    const normalized = normalizeLevel(level)
    const next = new Set(filter.value.levels)
    if (next.has(normalized)) {
      next.delete(normalized)
    } else {
      next.add(normalized)
    }
    setFilter({ levels: next })
  }

  function clearEntries(): void {
    entries.value = []
  }

  function setAutoScroll(enabled: boolean): void {
    autoScroll.value = enabled
  }

  function nodeEntries(nodeId: string) {
    return computed(() => entries.value.filter((entry) => entry.nodeId === nodeId))
  }

  function getLastSubscription(): LogSubscription {
    return lastSubscription.value
  }

  function setLastSubscription(sub: LogSubscription): void {
    lastSubscription.value = { nodeId: sub.nodeId ?? null, level: sub.level ?? null }
  }

  return {
    entries,
    maxEntries,
    filter,
    autoScroll,
    filteredEntries,
    minimumActiveLevel,
    addEntry,
    setFilter,
    toggleLevel,
    clearEntries,
    setAutoScroll,
    nodeEntries,
    getLastSubscription,
    setLastSubscription,
  }
})
