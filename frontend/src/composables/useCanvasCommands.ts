import type {
  CanvasId,
  CanvasSessionDescriptor,
  DisposableCanvasResource,
} from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from './useGraphSync'

const CANVAS_COMMAND_RESOURCE = 'canvas-commands'

export type CanvasSaveRoute = 'root' | 'nested' | 'legacy' | 'unavailable'

export interface CanvasScopedCommandsOptions {
  descriptor: CanvasSessionDescriptor
  save?: () => void | Promise<void>
  renameNode: (nodeId: string, name: string) => boolean
  setNodeEnabled: (nodeId: string, enabled: boolean) => boolean
  setInputPinned: (nodeId: string, input: string, pinned: boolean) => boolean
  setOutputTemplate: (nodeId: string, output: string, value: string) => boolean
  updateParameter: (nodeId: string, key: string, value: unknown) => boolean
}

export interface CanvasCommandsApi {
  routeSave(): Promise<CanvasSaveRoute>
  renameNode(nodeId: string, name: string): boolean
  setNodeEnabled(nodeId: string, enabled: boolean): boolean
  setInputPinned(nodeId: string, input: string, pinned: boolean): boolean
  setOutputTemplate(nodeId: string, output: string, value: string): boolean
  updateParameter(nodeId: string, key: string, value: unknown): boolean
  dispose(): void
}

interface CanvasCommandResource extends DisposableCanvasResource {
  save?: () => Promise<void>
  renameNode(nodeId: string, name: string): boolean
  setNodeEnabled(nodeId: string, enabled: boolean): boolean
  setInputPinned(nodeId: string, input: string, pinned: boolean): boolean
  setOutputTemplate(nodeId: string, output: string, value: string): boolean
  updateParameter(nodeId: string, key: string, value: unknown): boolean
}

let activeFacade: CanvasCommandsApi | null = null

export function useCanvasCommands(
  options: CanvasScopedCommandsOptions,
): CanvasCommandsApi
export function useCanvasCommands(): CanvasCommandsApi
export function useCanvasCommands(
  options?: CanvasScopedCommandsOptions,
): CanvasCommandsApi {
  if (!options) {
    if (activeFacade === null) activeFacade = createActiveFacade()
    return activeFacade
  }
  graphSyncCanvasSessions.register(options.descriptor)
  if (options.descriptor.kind === 'nested') {
    if (!options.save) throw new Error('Nested canvas Save command is required')
  }
  const resource = graphSyncCanvasSessions.getOrCreateResource(
    options.descriptor.canvasId,
    CANVAS_COMMAND_RESOURCE,
    () => createCommandResource(options),
  )
  return {
    routeSave: async () => {
      if (options.descriptor.kind === 'root') return 'root'
      await resource.save!()
      return 'nested'
    },
    renameNode: (nodeId, name) => resource.renameNode(nodeId, name),
    setNodeEnabled: (nodeId, enabled) => (
      resource.setNodeEnabled(nodeId, enabled)
    ),
    setInputPinned: (nodeId, input, pinned) => (
      resource.setInputPinned(nodeId, input, pinned)
    ),
    setOutputTemplate: (nodeId, output, value) => (
      resource.setOutputTemplate(nodeId, output, value)
    ),
    updateParameter: (nodeId, key, value) => (
      resource.updateParameter(nodeId, key, value)
    ),
    dispose: () => graphSyncCanvasSessions.unregister(options.descriptor.canvasId),
  }
}

export function _resetCanvasCommandsForTest(): void {
  graphSyncCanvasSessions.dispose()
  activeFacade = null
}

function createCommandResource(
  options: CanvasScopedCommandsOptions,
): CanvasCommandResource {
  let disposed = false
  return {
    ...(options.save
      ? {
          save: async () => {
            if (disposed) throw new Error('Canvas commands have been disposed')
            await options.save!()
          },
        }
      : {}),
    renameNode: (nodeId, name) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.renameNode(nodeId, name)
    },
    setNodeEnabled: (nodeId, enabled) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.setNodeEnabled(nodeId, enabled)
    },
    setInputPinned: (nodeId, input, pinned) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.setInputPinned(nodeId, input, pinned)
    },
    setOutputTemplate: (nodeId, output, value) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.setOutputTemplate(nodeId, output, value)
    },
    updateParameter: (nodeId, key, value) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.updateParameter(nodeId, key, value)
    },
    dispose: () => {
      disposed = true
    },
  }
}

function createActiveFacade(): CanvasCommandsApi {
  return {
    routeSave: async () => {
      const activeCanvasId = graphSyncCanvasSessions.activeCanvasId.value
      if (activeCanvasId === null) {
        return graphSyncCanvasSessions.sessionCount.value === 0
          ? 'legacy'
          : 'unavailable'
      }
      const session = graphSyncCanvasSessions.get(activeCanvasId)
      if (session?.descriptor.kind === 'root') return 'root'
      if (session?.descriptor.kind !== 'nested') return 'unavailable'
      const resource = graphSyncCanvasSessions.getResource<CanvasCommandResource>(
        activeCanvasId,
        CANVAS_COMMAND_RESOURCE,
      )
      if (resource?.save === undefined) return 'unavailable'
      await resource.save()
      return 'nested'
    },
    renameNode: (nodeId, name) => (
      activeCommandResource()?.renameNode(nodeId, name) ?? false
    ),
    setNodeEnabled: (nodeId, enabled) => (
      activeCommandResource()?.setNodeEnabled(nodeId, enabled) ?? false
    ),
    setInputPinned: (nodeId, input, pinned) => (
      activeCommandResource()?.setInputPinned(nodeId, input, pinned) ?? false
    ),
    setOutputTemplate: (nodeId, output, value) => (
      activeCommandResource()?.setOutputTemplate(nodeId, output, value) ?? false
    ),
    updateParameter: (nodeId, key, value) => {
      return activeCommandResource()?.updateParameter(nodeId, key, value) ?? false
    },
    dispose: () => {
      const activeCanvasId: CanvasId | null =
        graphSyncCanvasSessions.activeCanvasId.value
      if (activeCanvasId !== null) graphSyncCanvasSessions.unregister(activeCanvasId)
    },
  }
}

function activeCommandResource(): CanvasCommandResource | undefined {
  const activeCanvasId = graphSyncCanvasSessions.activeCanvasId.value
  if (activeCanvasId === null) return undefined
  return graphSyncCanvasSessions.getResource<CanvasCommandResource>(
    activeCanvasId,
    CANVAS_COMMAND_RESOURCE,
  ) ?? undefined
}
