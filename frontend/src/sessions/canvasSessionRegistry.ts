import { readonly, ref, type DeepReadonly, type Ref } from 'vue'

declare const canvasIdBrand: unique symbol

/** Stable canvas identity derived directly from the owning Dockview panel id. */
export type CanvasId = string & { readonly [canvasIdBrand]: 'CanvasId' }

export function canvasIdFromPanelId(panelId: string): CanvasId {
  if (panelId.trim().length === 0) {
    throw new Error('Dockview panel id must not be empty')
  }
  return panelId as CanvasId
}

export interface RootCanvasSessionDescriptor {
  readonly kind: 'root'
  readonly canvasId: CanvasId
  readonly workflowId: string | null
}

export interface NestedCanvasSessionDescriptor {
  readonly kind: 'nested'
  readonly canvasId: CanvasId
  readonly sessionId: string
  readonly parentCanvasId: CanvasId
}

export type CanvasSessionDescriptor =
  | RootCanvasSessionDescriptor
  | NestedCanvasSessionDescriptor

export interface DisposableCanvasResource {
  dispose(): void
}

export interface RegisteredCanvasSession {
  readonly descriptor: CanvasSessionDescriptor
  readonly coordinator: DisposableCanvasResource | null
}

interface MutableCanvasSession {
  descriptor: CanvasSessionDescriptor
  coordinator: DisposableCanvasResource | null
}

/**
 * Owns canvas-scoped resources without inferring activation from access.
 * Dockview activation events are the only callers that should invoke activate().
 */
export class CanvasSessionRegistry {
  private readonly sessions = new Map<CanvasId, MutableCanvasSession>()
  private readonly mutableActiveCanvasId = ref<CanvasId | null>(null)
  private readonly mutableSessionCount = ref(0)

  readonly activeCanvasId: DeepReadonly<Ref<CanvasId | null>> = readonly(
    this.mutableActiveCanvasId,
  )
  readonly sessionCount: DeepReadonly<Ref<number>> = readonly(
    this.mutableSessionCount,
  )

  register(descriptor: CanvasSessionDescriptor): RegisteredCanvasSession {
    const existing = this.sessions.get(descriptor.canvasId)
    if (existing) {
      if (!sameDescriptor(existing.descriptor, descriptor)) {
        throw new Error(`Canvas '${descriptor.canvasId}' is already registered`)
      }
      return sessionView(existing)
    }

    const session: MutableCanvasSession = {
      descriptor: Object.freeze({ ...descriptor }) as CanvasSessionDescriptor,
      coordinator: null,
    }
    this.sessions.set(descriptor.canvasId, session)
    this.mutableSessionCount.value = this.sessions.size
    return sessionView(session)
  }

  get(canvasId: CanvasId): RegisteredCanvasSession | null {
    const session = this.sessions.get(canvasId)
    return session ? sessionView(session) : null
  }

  getOrCreateCoordinator<T extends DisposableCanvasResource>(
    canvasId: CanvasId,
    create: (descriptor: CanvasSessionDescriptor) => T,
  ): T {
    const session = this.sessions.get(canvasId)
    if (!session) {
      throw new Error(`Canvas '${canvasId}' is not registered`)
    }
    if (session.coordinator === null) {
      session.coordinator = create(session.descriptor)
    }
    return session.coordinator as T
  }

  activate(canvasId: CanvasId | null): void {
    if (canvasId !== null && !this.sessions.has(canvasId)) {
      throw new Error(`Canvas '${canvasId}' is not registered`)
    }
    this.mutableActiveCanvasId.value = canvasId
  }

  unregister(canvasId: CanvasId): void {
    const session = this.sessions.get(canvasId)
    if (!session) return
    session.coordinator?.dispose()
    this.sessions.delete(canvasId)
    this.mutableSessionCount.value = this.sessions.size
    if (this.mutableActiveCanvasId.value === canvasId) {
      this.activate(null)
    }
  }

  dispose(): void {
    for (const session of this.sessions.values()) {
      session.coordinator?.dispose()
    }
    this.sessions.clear()
    this.mutableSessionCount.value = 0
    this.activate(null)
  }
}

function sessionView(session: MutableCanvasSession): RegisteredCanvasSession {
  return {
    descriptor: session.descriptor,
    coordinator: session.coordinator,
  }
}

function sameDescriptor(
  left: CanvasSessionDescriptor,
  right: CanvasSessionDescriptor,
): boolean {
  if (left.kind !== right.kind || left.canvasId !== right.canvasId) return false
  if (left.kind === 'root' && right.kind === 'root') {
    return left.workflowId === right.workflowId
  }
  if (left.kind === 'nested' && right.kind === 'nested') {
    return left.sessionId === right.sessionId
      && left.parentCanvasId === right.parentCanvasId
  }
  return false
}
