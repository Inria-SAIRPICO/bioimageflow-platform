// STUB: canonical loggerStore is owned by the Logger Panel plan
// (2026-04-01-logger-panel.md, Task 1). This file only exposes the
// minimum surface useWebSocket touches — addEntry, clearEntries,
// getLastSubscription, and the LogEntry type — so the WebSocket layer
// can be built independently. It will be replaced wholesale when the
// Logger Panel plan lands; do not add LogFilter or display logic here.

import { ref } from 'vue'
import { defineStore } from 'pinia'

export interface LogEntry {
  level: string
  message: string
  nodeId: string | null
  timestamp: number
}

export interface LogSubscription {
  nodeId?: string
  level?: string
}

export const useLoggerStore = defineStore('logger', () => {
  const entries = ref<LogEntry[]>([])
  const lastSubscription = ref<LogSubscription | null>(null)

  function addEntry(entry: LogEntry): void {
    entries.value.push(entry)
  }

  function clearEntries(): void {
    entries.value = []
  }

  function getLastSubscription(): LogSubscription | null {
    return lastSubscription.value
  }

  function setLastSubscription(sub: LogSubscription | null): void {
    lastSubscription.value = sub
  }

  return {
    entries,
    addEntry,
    clearEntries,
    getLastSubscription,
    setLastSubscription,
  }
})
