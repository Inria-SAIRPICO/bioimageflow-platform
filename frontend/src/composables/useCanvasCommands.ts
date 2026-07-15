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
  updateParameter: (nodeId: string, key: string, value: unknown) => boolean
}

export interface CanvasCommandsApi {
  routeSave(): Promise<CanvasSaveRoute>
  updateParameter(nodeId: string, key: string, value: unknown): boolean
  dispose(): void
}

interface CanvasCommandResource extends DisposableCanvasResource {
  save?: () => Promise<void>
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
    updateParameter: (nodeId, key, value) => {
      const activeCanvasId = graphSyncCanvasSessions.activeCanvasId.value
      if (activeCanvasId === null) return false
      const resource = graphSyncCanvasSessions.getResource<CanvasCommandResource>(
        activeCanvasId,
        CANVAS_COMMAND_RESOURCE,
      )
      return resource?.updateParameter(nodeId, key, value) ?? false
    },
    dispose: () => {
      const activeCanvasId: CanvasId | null =
        graphSyncCanvasSessions.activeCanvasId.value
      if (activeCanvasId !== null) graphSyncCanvasSessions.unregister(activeCanvasId)
    },
  }
}
