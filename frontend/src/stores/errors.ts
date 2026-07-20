import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useLoggerStore } from '@/stores/logger'

export type ErrorKind =
  | 'graph_sync_error'
  | 'websocket_error'
  | 'log_subscription_failed'
  | 'execution_failed'
  | 'network_unreachable'
  | 'edge_rejected'
  | 'unknown'

export const ERROR_KIND_LABELS: Record<ErrorKind, string> = {
  graph_sync_error: 'Graph sync error',
  websocket_error: 'Connection error',
  log_subscription_failed: 'Log subscription error',
  execution_failed: 'Execution failed',
  network_unreachable: 'Network unreachable',
  edge_rejected: 'Edge rejected',
  unknown: 'Error',
}

export interface ErrorEntry {
  id: string
  kind: ErrorKind
  detail: string
  fullDetail?: string
  timestamp: number
  field?: string
  status?: number
  nodeId?: string
  autoDismissMs?: number
  acknowledged?: boolean
}

export type ErrorReportInput = Omit<
  ErrorEntry,
  'id' | 'timestamp' | 'acknowledged'
> & {
  logToLogger?: boolean
}

let _idCounter = 0
function generateId(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto
  if (c?.randomUUID) {
    return c.randomUUID()
  }
  _idCounter += 1
  return `err-${Date.now().toString(36)}-${_idCounter}-${Math.random()
    .toString(36)
    .slice(2, 10)}`
}

export const useErrorStore = defineStore('errors', () => {
  const errors = ref<ErrorEntry[]>([])
  const timers = new Map<string, ReturnType<typeof setTimeout>>()

  const unreadCount = computed(
    () => errors.value.filter((e) => !e.acknowledged).length,
  )
  const hasErrors = computed(() => unreadCount.value > 0)

  function _clearTimer(id: string): void {
    const t = timers.get(id)
    if (t !== undefined) {
      clearTimeout(t)
      timers.delete(id)
    }
  }

  function report(input: ErrorReportInput): string {
    const id = generateId()
    const entry: ErrorEntry = {
      id,
      kind: input.kind,
      detail: input.detail,
      timestamp: Date.now(),
      acknowledged: false,
    }
    if (input.field !== undefined) entry.field = input.field
    if (input.status !== undefined) entry.status = input.status
    if (input.nodeId !== undefined) entry.nodeId = input.nodeId
    if (input.fullDetail !== undefined) entry.fullDetail = input.fullDetail
    if (input.autoDismissMs !== undefined) {
      entry.autoDismissMs = input.autoDismissMs
      const t = setTimeout(() => {
        timers.delete(id)
        const idx = errors.value.findIndex((e) => e.id === id)
        if (idx === -1) return
        const e = errors.value[idx]!
        if (!e.acknowledged) {
          errors.value[idx] = { ...e, acknowledged: true }
        }
      }, input.autoDismissMs)
      timers.set(id, t)
    }
    errors.value.push(entry)
    if (input.logToLogger !== false) {
      useLoggerStore().addEntry({
        level: 'ERROR',
        message: input.fullDetail ?? input.detail,
        nodeId: input.nodeId ?? null,
        timestamp: entry.timestamp / 1000,
      })
    }
    return id
  }

  function toggleAcknowledged(id: string): void {
    const idx = errors.value.findIndex((e) => e.id === id)
    if (idx === -1) return
    _clearTimer(id)
    const e = errors.value[idx]!
    errors.value[idx] = { ...e, acknowledged: !e.acknowledged }
  }

  return {
    errors,
    unreadCount,
    hasErrors,
    report,
    toggleAcknowledged,
  }
})
