import { ref, shallowRef, type Ref, type ShallowRef } from 'vue'
import type { GraphState } from '@/api/types'
import type { CanvasId, DisposableCanvasResource } from './canvasSessionRegistry'

export type RecoveryPersistenceState = 'idle' | 'pending' | 'error'

export interface RecoveryPersistenceRequest {
  canvasId: CanvasId
  recoveryKey: string
  queueRevision: number
  timestamp: number
  graph: GraphState
  signal: AbortSignal
}

export type RecoveryPersistenceTransport = (
  request: RecoveryPersistenceRequest,
) => Promise<void>

export interface RecoveryPersistenceAcceptance {
  canvasId: CanvasId
  recoveryKey: string
  queueRevision: number
  timestamp: number
  graph: GraphState
  persisted: boolean
}

export interface RecoveryPersistenceCoordinator extends DisposableCanvasResource {
  readonly canvasId: CanvasId
  readonly queueRevision: Ref<number>
  readonly isPending: Ref<boolean>
  readonly syncState: Ref<RecoveryPersistenceState>
  readonly lastError: ShallowRef<unknown | null>
  readonly isDisposed: Ref<boolean>
  queue(recoveryKey: string, graph: GraphState): number
  flushLatest(): Promise<RecoveryPersistenceAcceptance | null>
}

export interface CreateRecoveryPersistenceCoordinatorOptions {
  canvasId: CanvasId
  transport: RecoveryPersistenceTransport
  debounceMs?: number
  now?: () => number
  onOperationalError?: (
    error: unknown,
    request: Omit<RecoveryPersistenceRequest, 'signal'>,
  ) => void
}

interface QueuedRecovery {
  canvasId: CanvasId
  recoveryKey: string
  queueRevision: number
  timestamp: number
  graph: GraphState
  ownershipToken: number
}

interface InflightRecovery {
  snapshot: QueuedRecovery
  controller: AbortController
  promise: Promise<RecoveryPersistenceAcceptance>
}

interface RecoveryKeyOwnership {
  activeTokens: Set<number>
  committedToken: number
}

export class RecoveryPersistenceCoordinatorDisposedError extends Error {
  constructor(canvasId: CanvasId) {
    super(`Recovery persistence coordinator for canvas '${canvasId}' has been disposed`)
    this.name = 'RecoveryPersistenceCoordinatorDisposedError'
  }
}

let nextOwnershipToken = 0
const ownershipByRecoveryKey = new Map<string, RecoveryKeyOwnership>()
const writeTailByRecoveryKey = new Map<string, Promise<void>>()

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function ownershipFor(recoveryKey: string): RecoveryKeyOwnership {
  let ownership = ownershipByRecoveryKey.get(recoveryKey)
  if (!ownership) {
    ownership = { activeTokens: new Set(), committedToken: 0 }
    ownershipByRecoveryKey.set(recoveryKey, ownership)
  }
  return ownership
}

function registerOwnership(recoveryKey: string): number {
  const token = ++nextOwnershipToken
  ownershipFor(recoveryKey).activeTokens.add(token)
  return token
}

function abandonOwnership(recoveryKey: string, token: number): void {
  const ownership = ownershipByRecoveryKey.get(recoveryKey)
  if (!ownership) return
  ownership.activeTokens.delete(token)
  if (ownership.activeTokens.size === 0) {
    ownershipByRecoveryKey.delete(recoveryKey)
  }
}

function isLatestOwner(recoveryKey: string, token: number): boolean {
  const ownership = ownershipFor(recoveryKey)
  if (!ownership.activeTokens.has(token) || token < ownership.committedToken) {
    return false
  }
  for (const activeToken of ownership.activeTokens) {
    if (activeToken > token) return false
  }
  return true
}

function completeOwnership(
  recoveryKey: string,
  token: number,
  persisted: boolean,
): void {
  const ownership = ownershipFor(recoveryKey)
  if (persisted) {
    ownership.committedToken = Math.max(ownership.committedToken, token)
  }
  ownership.activeTokens.delete(token)
  if (ownership.activeTokens.size === 0) {
    ownershipByRecoveryKey.delete(recoveryKey)
  }
}

function serializeRecoveryKeyWrite<T>(
  recoveryKey: string,
  write: () => Promise<T>,
): Promise<T> {
  const previous = writeTailByRecoveryKey.get(recoveryKey) ?? Promise.resolve()
  const operation = previous.catch(() => {}).then(write)
  const tail = operation.then(() => {}, () => {})
  writeTailByRecoveryKey.set(recoveryKey, tail)
  void tail.finally(() => {
    if (writeTailByRecoveryKey.get(recoveryKey) === tail) {
      writeTailByRecoveryKey.delete(recoveryKey)
    }
  })
  return operation
}

export function createRecoveryPersistenceCoordinator(
  options: CreateRecoveryPersistenceCoordinatorOptions,
): RecoveryPersistenceCoordinator {
  const debounceMs = options.debounceMs ?? 500
  const now = options.now ?? Date.now
  const queueRevision = ref(0)
  const isPending = ref(false)
  const syncState = ref<RecoveryPersistenceState>('idle')
  const lastError = shallowRef<unknown | null>(null)
  const isDisposed = ref(false)

  const latestByKey = new Map<string, QueuedRecovery>()
  let lastAcceptance: RecoveryPersistenceAcceptance | null = null
  let timer: ReturnType<typeof setTimeout> | null = null
  let inflight: InflightRecovery | null = null
  let rejectDisposed!: (reason: RecoveryPersistenceCoordinatorDisposedError) => void
  const disposedPromise = new Promise<never>((_resolve, reject) => {
    rejectDisposed = reject
  })
  void disposedPromise.catch(() => {})

  function assertUsable(): void {
    if (isDisposed.value) {
      throw new RecoveryPersistenceCoordinatorDisposedError(options.canvasId)
    }
  }

  function clearTimer(): void {
    if (timer === null) return
    clearTimeout(timer)
    timer = null
  }

  function queue(recoveryKey: string, graph: GraphState): number {
    assertUsable()
    if (recoveryKey.trim().length === 0) {
      throw new Error('Recovery key must not be empty')
    }
    const existing = latestByKey.get(recoveryKey)
    if (
      existing
      && inflight?.snapshot.ownershipToken !== existing.ownershipToken
    ) {
      abandonOwnership(existing.recoveryKey, existing.ownershipToken)
    }

    const nextRevision = queueRevision.value + 1
    const snapshot: QueuedRecovery = {
      canvasId: options.canvasId,
      recoveryKey,
      queueRevision: nextRevision,
      timestamp: now(),
      graph: cloneJson(graph),
      ownershipToken: registerOwnership(recoveryKey),
    }
    latestByKey.delete(recoveryKey)
    latestByKey.set(recoveryKey, snapshot)
    queueRevision.value = nextRevision
    isPending.value = true
    syncState.value = 'pending'
    lastError.value = null

    clearTimer()
    timer = setTimeout(() => {
      timer = null
      void flushLatest().catch(() => {
        // State and reporting are handled by the active write.
      })
    }, debounceMs)
    return nextRevision
  }

  function nextTarget(): QueuedRecovery | null {
    let target: QueuedRecovery | null = null
    for (const snapshot of latestByKey.values()) {
      if (target === null || snapshot.queueRevision < target.queueRevision) {
        target = snapshot
      }
    }
    return target
  }

  function startWrite(snapshot: QueuedRecovery): InflightRecovery {
    isPending.value = true
    syncState.value = 'pending'
    const controller = new AbortController()
    const request: RecoveryPersistenceRequest = {
      canvasId: snapshot.canvasId,
      recoveryKey: snapshot.recoveryKey,
      queueRevision: snapshot.queueRevision,
      timestamp: snapshot.timestamp,
      graph: cloneJson(snapshot.graph),
      signal: controller.signal,
    }
    const rawWrite = serializeRecoveryKeyWrite(snapshot.recoveryKey, async () => {
      if (isDisposed.value || !isLatestOwner(
        snapshot.recoveryKey,
        snapshot.ownershipToken,
      )) {
        completeOwnership(snapshot.recoveryKey, snapshot.ownershipToken, false)
        return false
      }
      try {
        await options.transport(request)
      } catch (error) {
        if (!isLatestOwner(snapshot.recoveryKey, snapshot.ownershipToken)) {
          completeOwnership(snapshot.recoveryKey, snapshot.ownershipToken, false)
          return false
        }
        throw error
      }
      completeOwnership(snapshot.recoveryKey, snapshot.ownershipToken, true)
      return true
    })
    const promise = Promise.race([rawWrite, disposedPromise])
      .then((persisted): RecoveryPersistenceAcceptance => {
        const acceptance: RecoveryPersistenceAcceptance = {
          canvasId: snapshot.canvasId,
          recoveryKey: snapshot.recoveryKey,
          queueRevision: snapshot.queueRevision,
          timestamp: snapshot.timestamp,
          graph: cloneJson(snapshot.graph),
          persisted,
        }
        if (
          latestByKey.get(snapshot.recoveryKey)?.queueRevision
          === snapshot.queueRevision
        ) {
          latestByKey.delete(snapshot.recoveryKey)
        }
        lastAcceptance = acceptance
        lastError.value = null
        if (nextTarget() === null) {
          isPending.value = false
          syncState.value = 'idle'
        } else {
          isPending.value = true
          syncState.value = 'pending'
        }
        return acceptance
      })
      .catch((error: unknown) => {
        if (isDisposed.value) {
          throw new RecoveryPersistenceCoordinatorDisposedError(options.canvasId)
        }
        const current = latestByKey.get(snapshot.recoveryKey)
        const isCurrent = current?.queueRevision === snapshot.queueRevision
        isPending.value = true
        if (isCurrent) {
          lastError.value = error
          syncState.value = 'error'
          options.onOperationalError?.(error, {
            canvasId: request.canvasId,
            recoveryKey: request.recoveryKey,
            queueRevision: request.queueRevision,
            timestamp: request.timestamp,
            graph: request.graph,
          })
        } else {
          syncState.value = 'pending'
        }
        throw error
      })
      .finally(() => {
        if (inflight?.promise === promise) {
          inflight = null
        }
      })

    const started = { snapshot, controller, promise }
    inflight = started
    return started
  }

  async function flushLatest(): Promise<RecoveryPersistenceAcceptance | null> {
    assertUsable()
    clearTimer()

    while (true) {
      assertUsable()
      const target = nextTarget()
      if (target === null) return lastAcceptance
      const activeWrite = inflight ?? startWrite(target)
      try {
        await activeWrite.promise
      } catch (error) {
        const newer = latestByKey.get(activeWrite.snapshot.recoveryKey)
        if (
          !isDisposed.value
          && newer !== undefined
          && newer.queueRevision > activeWrite.snapshot.queueRevision
        ) {
          abandonOwnership(
            activeWrite.snapshot.recoveryKey,
            activeWrite.snapshot.ownershipToken,
          )
          continue
        }
        throw error
      }
    }
  }

  function dispose(): void {
    if (isDisposed.value) return
    isDisposed.value = true
    clearTimer()
    for (const snapshot of latestByKey.values()) {
      abandonOwnership(snapshot.recoveryKey, snapshot.ownershipToken)
    }
    if (inflight !== null) {
      abandonOwnership(
        inflight.snapshot.recoveryKey,
        inflight.snapshot.ownershipToken,
      )
    }
    latestByKey.clear()
    rejectDisposed(new RecoveryPersistenceCoordinatorDisposedError(options.canvasId))
    inflight?.controller.abort()
    isPending.value = false
    syncState.value = 'idle'
  }

  return {
    canvasId: options.canvasId,
    queueRevision,
    isPending,
    syncState,
    lastError,
    isDisposed,
    queue,
    flushLatest,
    dispose,
  }
}
