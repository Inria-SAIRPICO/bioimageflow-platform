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

export const GRAPH_SYNC_RESOURCE = 'graph-sync'

export interface RegisteredCanvasSession {
  readonly descriptor: CanvasSessionDescriptor
  readonly coordinator: DisposableCanvasResource | null
}

interface MutableCanvasSession {
  descriptor: CanvasSessionDescriptor
  resources: Map<string, DisposableCanvasResource>
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
      resources: new Map(),
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
    return this.getOrCreateResource(canvasId, GRAPH_SYNC_RESOURCE, create)
  }

  getResource<T extends DisposableCanvasResource>(
    canvasId: CanvasId,
    name: string,
  ): T | null {
    return (this.sessions.get(canvasId)?.resources.get(name) as T | undefined)
      ?? null
  }

  getOrCreateResource<T extends DisposableCanvasResource>(
    canvasId: CanvasId,
    name: string,
    create: (descriptor: CanvasSessionDescriptor) => T,
  ): T {
    const session = this.sessions.get(canvasId)
    if (!session) {
      throw new Error(`Canvas '${canvasId}' is not registered`)
    }
    const existing = session.resources.get(name)
    if (existing) {
      return existing as T
    }
    const resource = create(session.descriptor)
    session.resources.set(name, resource)
    return resource
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
    this.sessions.delete(canvasId)
    this.mutableSessionCount.value = this.sessions.size
    if (this.mutableActiveCanvasId.value === canvasId) {
      this.mutableActiveCanvasId.value = null
    }
    disposeSessionResources(session)
  }

  dispose(): void {
    const sessions = [...this.sessions.values()]
    this.sessions.clear()
    this.mutableSessionCount.value = 0
    this.mutableActiveCanvasId.value = null
    for (const session of sessions) disposeSessionResources(session)
  }
}

/** Shared registry used by canvas-scoped frontend resources and active-canvas facades. */
export const canvasSessionRegistry = new CanvasSessionRegistry()

function sessionView(session: MutableCanvasSession): RegisteredCanvasSession {
  return {
    descriptor: session.descriptor,
    get coordinator() {
      return session.resources.get(GRAPH_SYNC_RESOURCE) ?? null
    },
  }
}

function disposeSessionResources(session: MutableCanvasSession): void {
  const resources = new Set(session.resources.values())
  session.resources.clear()
  for (const resource of resources) resource.dispose()
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
