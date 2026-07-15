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
}

export interface CanvasCommandsApi {
  routeSave(): Promise<CanvasSaveRoute>
  dispose(): void
}

interface CanvasCommandResource extends DisposableCanvasResource {
  save(): Promise<void>
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
  let resource: CanvasCommandResource | null = null
  if (options.descriptor.kind === 'nested') {
    if (!options.save) throw new Error('Nested canvas Save command is required')
    resource = graphSyncCanvasSessions.getOrCreateResource(
      options.descriptor.canvasId,
      CANVAS_COMMAND_RESOURCE,
      () => createCommandResource(options.save!),
    )
  }
  return {
    routeSave: async () => {
      if (options.descriptor.kind === 'root') return 'root'
      await resource!.save()
      return 'nested'
    },
    dispose: () => graphSyncCanvasSessions.unregister(options.descriptor.canvasId),
  }
}

export function _resetCanvasCommandsForTest(): void {
  graphSyncCanvasSessions.dispose()
  activeFacade = null
}

function createCommandResource(
  save: () => void | Promise<void>,
): CanvasCommandResource {
  let disposed = false
  return {
    save: async () => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      await save()
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
      if (resource === null) return 'unavailable'
      await resource.save()
      return 'nested'
    },
    dispose: () => {
      const activeCanvasId: CanvasId | null =
        graphSyncCanvasSessions.activeCanvasId.value
      if (activeCanvasId !== null) graphSyncCanvasSessions.unregister(activeCanvasId)
    },
  }
}
