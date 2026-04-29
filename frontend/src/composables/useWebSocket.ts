import { ref, type Ref } from 'vue'
import { useExecutionStore } from '@/stores/execution'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useLoggerStore, type LogEntry } from '@/stores/logger'
import { useErrorStore } from '@/stores/errors'

export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'error'

export interface LogSubscriptionFilter {
  nodeId?: string
  level?: string
}

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]
const ACK_TIMEOUT_MS = 5000

interface PendingAck {
  resolve: () => void
  reject: (err: Error) => void
  timeoutHandle: ReturnType<typeof setTimeout>
  filter: LogSubscriptionFilter
  generation: number
}

interface Singleton {
  socket: WebSocket | null
  url: string | null
  connectionState: Ref<ConnectionState>
  reconnectAttempt: number
  reconnectTimer: ReturnType<typeof setTimeout> | null
  intentionallyClosed: boolean
  pending: Map<string, PendingAck>
  lastAppliedFilter: LogSubscriptionFilter | null
  messageCounter: number
  subscriptionGeneration: number
}

function createSingleton(): Singleton {
  return {
    socket: null,
    url: null,
    connectionState: ref<ConnectionState>('disconnected'),
    reconnectAttempt: 0,
    reconnectTimer: null,
    intentionallyClosed: false,
    pending: new Map(),
    lastAppliedFilter: null,
    messageCounter: 0,
    subscriptionGeneration: 0,
  }
}

let state: Singleton = createSingleton()

function resolveUrl(url?: string): string {
  if (url) return url
  const loc = globalThis.location
  const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${loc.host}/ws`
}

function nextMessageId(): string {
  state.messageCounter += 1
  return `ws-${Date.now().toString(36)}-${state.messageCounter}`
}

function clearReconnectTimer() {
  if (state.reconnectTimer !== null) {
    clearTimeout(state.reconnectTimer)
    state.reconnectTimer = null
  }
}

function cancelAllPending(reason: Error) {
  for (const p of state.pending.values()) {
    clearTimeout(p.timeoutHandle)
    p.reject(reason)
  }
  state.pending.clear()
}

// Dispatch targets intentionally duck-typed: applyToolReload,
// applyPackageInstall, and applyEnvironmentStatus are owned by peer plans
// (Hot-Reload, Tools Panel) that may not be implemented yet. This layer only
// transports messages; if a hook is missing, we warn once and skip — the peer
// plan adds it later.
function callIfExists(
  store: Record<string, unknown>,
  method: string,
  payload: unknown,
): void {
  const fn = store[method]
  if (typeof fn === 'function') {
    ;(fn as (p: unknown) => void).call(store, payload)
  } else {
    console.warn(
      `[useWebSocket] store method '${method}' not yet defined; message dropped`,
    )
  }
}

function dispatch(raw: unknown) {
  if (typeof raw !== 'object' || raw === null) return
  const msg = raw as { type?: string } & Record<string, unknown>
  switch (msg.type) {
    case 'progress':
      useExecutionStore().applyProgress(msg as never)
      break
    case 'node_state':
      useExecutionStore().applyNodeState(msg as never)
      break
    case 'log': {
      if (
        typeof msg.level !== 'string' ||
        typeof msg.message !== 'string' ||
        typeof msg.timestamp !== 'number' ||
        !Number.isFinite(msg.timestamp)
      ) {
        break
      }
      const entry: LogEntry = {
        level: msg.level,
        message: msg.message,
        nodeId: typeof msg.node_id === 'string' ? msg.node_id : null,
        timestamp: msg.timestamp,
      }
      useLoggerStore().addEntry(entry)
      break
    }
    case 'execution_complete':
      useExecutionStore().applyExecutionComplete(msg as never)
      break
    case 'tool_reload':
      callIfExists(
        useToolRegistryStore() as unknown as Record<string, unknown>,
        'applyToolReload',
        msg,
      )
      break
    case 'package_install':
      callIfExists(
        useToolRegistryStore() as unknown as Record<string, unknown>,
        'applyPackageInstall',
        msg,
      )
      mirrorPackageInstallToLogger(msg)
      break
    case 'environment_status':
      callIfExists(
        useToolRegistryStore() as unknown as Record<string, unknown>,
        'applyEnvironmentStatus',
        msg,
      )
      break
    case 'ack': {
      const ref = msg.ref as string | undefined
      if (!ref) return
      const pending = state.pending.get(ref)
      if (!pending) return
      clearTimeout(pending.timeoutHandle)
      if (pending.generation === state.subscriptionGeneration) {
        state.lastAppliedFilter = pending.filter
        useLoggerStore().setLastSubscription?.({
          nodeId: pending.filter.nodeId ?? null,
          level: pending.filter.level ?? null,
        })
      }
      state.pending.delete(ref)
      pending.resolve()
      break
    }
    case 'error': {
      const ref = msg.ref as string | undefined
      const detail = String(msg.detail ?? msg.code ?? 'ws error')
      if (ref) {
        const pending = state.pending.get(ref)
        if (pending) {
          clearTimeout(pending.timeoutHandle)
          state.pending.delete(ref)
          pending.reject(new Error(detail))
          return
        }
      }
      try {
        useErrorStore().report({
          kind: 'websocket_error',
          detail,
        })
      } catch {
        /* */
      }
      console.warn('[useWebSocket] server error without pending ref:', detail)
      break
    }
    default:
      console.warn('[useWebSocket] unknown message type:', msg.type)
  }
}

function mirrorPackageInstallToLogger(msg: Record<string, unknown>) {
  if (typeof msg.package_name !== 'string' || typeof msg.status !== 'string') return
  const detail = typeof msg.detail === 'string' && msg.detail.length > 0
    ? `: ${msg.detail}`
    : ''
  useLoggerStore().addEntry({
    level: msg.status === 'failed' ? 'ERROR' : 'INFO',
    message: `Package ${msg.package_name} ${msg.status}${detail}`,
    nodeId: null,
    timestamp: Date.now() / 1000,
  })
}

function sendUnfilteredLogSubscription() {
  void sendSubscribeLogsInternal({}).catch(() => {})
}

async function runReconnectRecovery() {
  try {
    await useExecutionStore().fetchStatus()
  } catch (err) {
    console.warn('[useWebSocket] fetchStatus on reconnect failed:', err)
  }
  try {
    await useToolRegistryStore().fetchTools()
  } catch (err) {
    console.warn('[useWebSocket] fetchTools on reconnect failed:', err)
  }

  sendUnfilteredLogSubscription()
}

function scheduleReconnect() {
  if (state.intentionallyClosed) return
  clearReconnectTimer()
  const idx = Math.min(state.reconnectAttempt, RECONNECT_DELAYS.length - 1)
  const delay = RECONNECT_DELAYS[idx]
  state.reconnectAttempt += 1
  state.reconnectTimer = setTimeout(() => {
    state.reconnectTimer = null
    if (state.url) openSocket(state.url)
  }, delay)
}

function openSocket(url: string) {
  // Detach and discard any prior socket. Without this, the old socket's
  // handlers stay live and its eventual `close` will overwrite the new
  // socket's connectionState, wipe the new pending-ack map, and spawn a
  // ghost reconnect cycle. Reachable when connect() runs while a previous
  // socket or reconnect timer exists.
  clearReconnectTimer()
  const prev = state.socket
  if (prev) {
    prev.onopen = null
    prev.onclose = null
    prev.onerror = null
    prev.onmessage = null
    try {
      prev.close()
    } catch {
      /* */
    }
    state.socket = null
  }

  state.url = url
  state.connectionState.value = 'connecting'

  const sock = new WebSocket(url)
  state.socket = sock

  sock.onopen = () => {
    state.connectionState.value = 'connected'
    const isReconnect = state.reconnectAttempt > 0
    state.reconnectAttempt = 0
    if (isReconnect) {
      void runReconnectRecovery()
    } else {
      sendUnfilteredLogSubscription()
    }
  }

  sock.onclose = () => {
    state.connectionState.value = 'disconnected'
    cancelAllPending(new Error('WebSocket closed'))
    scheduleReconnect()
  }

  sock.onerror = () => {
    state.connectionState.value = 'error'
  }

  sock.onmessage = (ev: MessageEvent) => {
    try {
      const parsed = JSON.parse(ev.data as string)
      dispatch(parsed)
    } catch (err) {
      console.warn('[useWebSocket] failed to parse message:', err)
    }
  }
}

function sendSubscribeLogsInternal(
  filter: LogSubscriptionFilter,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const sock = state.socket
    if (!sock || sock.readyState !== WebSocket.OPEN) {
      reject(new Error('WebSocket not connected'))
      return
    }
    const messageId = nextMessageId()
    state.subscriptionGeneration += 1
    const generation = state.subscriptionGeneration
    const timeoutHandle = setTimeout(() => {
      state.pending.delete(messageId)
      const err = new Error('subscribe_logs ack timed out')
      try {
        useErrorStore().report({
          kind: 'log_subscription_failed',
          detail: 'Log stream subscription could not be applied',
        })
      } catch {
        /* errorStore not ready — surface via reject only */
      }
      reject(err)
    }, ACK_TIMEOUT_MS)
    state.pending.set(messageId, {
      resolve,
      reject: (err) => {
        try {
          useErrorStore().report({
            kind: 'log_subscription_failed',
            detail: err.message,
          })
        } catch {
          /* */
        }
        reject(err)
      },
      timeoutHandle,
      filter,
      generation,
    })
    sock.send(
      JSON.stringify({
        type: 'subscribe_logs',
        message_id: messageId,
        node_id: filter.nodeId ?? null,
        level: filter.level ?? null,
      }),
    )
  })
}

// ---- Public API --------------------------------------------------------------

export function useWebSocket() {
  return {
    connectionState: state.connectionState,
    connect(url?: string) {
      state.intentionallyClosed = false
      openSocket(resolveUrl(url))
    },
    disconnect() {
      state.intentionallyClosed = true
      clearReconnectTimer()
      cancelAllPending(new Error('WebSocket disconnected by caller'))
      const sock = state.socket
      state.socket = null
      if (sock && sock.readyState !== WebSocket.CLOSED) {
        sock.close()
      }
      state.connectionState.value = 'disconnected'
    },
    sendSubscribeLogs(filter: LogSubscriptionFilter): Promise<void> {
      return sendSubscribeLogsInternal(filter)
    },
  }
}

export function __resetForTests(): void {
  const sock = state.socket
  if (sock) {
    // Clear handlers so close() doesn't loop back into scheduleReconnect /
    // cancelAllPending for the singleton we are about to discard.
    sock.onopen = null
    sock.onclose = null
    sock.onerror = null
    sock.onmessage = null
    try {
      sock.close()
    } catch {
      /* */
    }
  }
  clearReconnectTimer()
  // Drop pending-ack timers without invoking reject callbacks: tests that
  // fired `void sendSubscribeLogs(...)` would otherwise leak unhandled
  // rejections across the beforeEach boundary. We are throwing away the
  // entire singleton here, so the Promises die with it.
  for (const p of state.pending.values()) {
    clearTimeout(p.timeoutHandle)
  }
  state.pending.clear()
  state = createSingleton()
}
