import type { GraphState } from '@/api/types'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
  type CanvasId,
  type NestedCanvasSessionDescriptor,
  type RootCanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'
import { useUIStore } from '@/stores/ui'
import { makeGraph } from './graphFixtures'

export interface RootCanvasFixtureOptions {
  panelId?: string
  displayName?: string
  activate?: boolean
  present?: boolean
}

export interface RegisteredRootCanvas {
  readonly canvasId: CanvasId
  readonly descriptor: RootCanvasSessionDescriptor
  dispose(): void
}

export function rootCanvasId(
  workflowId: string,
  panelId = `workflow:${encodeURIComponent(workflowId)}`,
): CanvasId {
  return canvasIdFromPanelId(panelId)
}

export function makeRootCanvasDescriptor(
  workflowId: string,
  panelId?: string,
): RootCanvasSessionDescriptor {
  return {
    kind: 'root',
    canvasId: rootCanvasId(workflowId, panelId),
    workflowId,
  }
}

export function registerRootCanvas(
  workflowId: string,
  options: RootCanvasFixtureOptions = {},
): RegisteredRootCanvas {
  const descriptor = makeRootCanvasDescriptor(workflowId, options.panelId)
  canvasSessionRegistry.register(descriptor)
  if (options.present !== false) {
    useUIStore().setCanvasWorkflow(
      descriptor.canvasId,
      workflowId,
      options.displayName ?? workflowId,
    )
  }
  if (options.activate !== false) {
    canvasSessionRegistry.activate(descriptor.canvasId)
  }
  return {
    canvasId: descriptor.canvasId,
    descriptor,
    dispose: () => canvasSessionRegistry.unregister(descriptor.canvasId),
  }
}

export interface NestedCanvasFixtureOptions {
  sessionId: string
  parentCanvasId: CanvasId
  workflowId: string
  panelId?: string
  displayName?: string
  activate?: boolean
  present?: boolean
}

export interface RegisteredNestedCanvas {
  readonly canvasId: CanvasId
  readonly descriptor: NestedCanvasSessionDescriptor
  dispose(): void
}

export function registerNestedCanvas(
  options: NestedCanvasFixtureOptions,
): RegisteredNestedCanvas {
  const descriptor: NestedCanvasSessionDescriptor = {
    kind: 'nested',
    canvasId: canvasIdFromPanelId(
      options.panelId ?? `sub-workflow:${encodeURIComponent(options.sessionId)}`,
    ),
    sessionId: options.sessionId,
    parentCanvasId: options.parentCanvasId,
  }
  canvasSessionRegistry.register(descriptor)
  if (options.present !== false) {
    useUIStore().setCanvasWorkflow(
      descriptor.canvasId,
      options.workflowId,
      options.displayName ?? options.workflowId,
    )
  }
  if (options.activate !== false) {
    canvasSessionRegistry.activate(descriptor.canvasId)
  }
  return {
    canvasId: descriptor.canvasId,
    descriptor,
    dispose: () => canvasSessionRegistry.unregister(descriptor.canvasId),
  }
}

export interface RootCanvasParamsOptions {
  panelId?: string
  displayName?: string
  graph?: GraphState
  dirty?: boolean
}

/** Dockview parameters for a resolved root canvas, avoiding startup recovery in tests. */
export function rootCanvasParams(
  workflowId: string,
  options: RootCanvasParamsOptions = {},
) {
  return {
    panelId: options.panelId ?? `workflow:${encodeURIComponent(workflowId)}`,
    workflowName: workflowId,
    workflowDisplayName: options.displayName ?? workflowId,
    graph: options.graph ?? makeGraph(),
    dirty: options.dirty ?? false,
  }
}
