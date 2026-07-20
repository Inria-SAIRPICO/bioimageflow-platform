import type {
  CanvasId,
  CanvasSessionDescriptor,
  DisposableCanvasResource,
} from '@/sessions/canvasSessionRegistry'
import { graphSyncCanvasSessions } from './useGraphSync'

const CANVAS_COMMAND_RESOURCE = 'canvas-commands'

export type CanvasSaveRoute = 'root' | 'nested' | 'unavailable'

export type CanvasInterfaceRejectionReason =
  | 'duplicate_name'
  | 'empty_name'
  | 'locked'
  | 'not_found'
  | 'not_exposable'
  | 'unavailable'

export type CanvasInterfaceCommandResult =
  | { status: 'changed' }
  | { status: 'unchanged' }
  | {
      status: 'rejected'
      reason: CanvasInterfaceRejectionReason
      name?: string
    }

export interface CanvasScopedCommandsOptions {
  descriptor: CanvasSessionDescriptor
  save?: () => void | Promise<void>
  addToolNode?: (toolName: string, parameters?: Record<string, unknown>) => string | null
  renameNode: (nodeId: string, name: string) => boolean
  setNodeEnabled: (nodeId: string, enabled: boolean) => boolean
  setInputPinned: (nodeId: string, input: string, pinned: boolean) => boolean
  setOutputTemplate: (nodeId: string, output: string, value: string) => boolean
  toggleWorkflowInput: (
    nodeId: string,
    input: string,
  ) => CanvasInterfaceCommandResult
  toggleWorkflowOutput: (
    nodeId: string,
    output: string,
  ) => CanvasInterfaceCommandResult
  renameWorkflowInput: (
    nodeId: string,
    input: string,
    name: string,
  ) => CanvasInterfaceCommandResult
  renameWorkflowOutput: (
    nodeId: string,
    output: string,
    name: string,
  ) => CanvasInterfaceCommandResult
  updateParameter: (nodeId: string, key: string, value: unknown) => boolean
}

export interface CanvasCommandsApi {
  routeSave(): Promise<CanvasSaveRoute>
  addToolNode(toolName: string, parameters?: Record<string, unknown>): string | null
  renameNode(nodeId: string, name: string): boolean
  setNodeEnabled(nodeId: string, enabled: boolean): boolean
  setInputPinned(nodeId: string, input: string, pinned: boolean): boolean
  setOutputTemplate(nodeId: string, output: string, value: string): boolean
  toggleWorkflowInput(nodeId: string, input: string): CanvasInterfaceCommandResult
  toggleWorkflowOutput(nodeId: string, output: string): CanvasInterfaceCommandResult
  renameWorkflowInput(
    nodeId: string,
    input: string,
    name: string,
  ): CanvasInterfaceCommandResult
  renameWorkflowOutput(
    nodeId: string,
    output: string,
    name: string,
  ): CanvasInterfaceCommandResult
  updateParameter(nodeId: string, key: string, value: unknown): boolean
  dispose(): void
}

interface CanvasCommandResource extends DisposableCanvasResource {
  save?: () => Promise<void>
  addToolNode(toolName: string, parameters?: Record<string, unknown>): string | null
  renameNode(nodeId: string, name: string): boolean
  setNodeEnabled(nodeId: string, enabled: boolean): boolean
  setInputPinned(nodeId: string, input: string, pinned: boolean): boolean
  setOutputTemplate(nodeId: string, output: string, value: string): boolean
  toggleWorkflowInput(nodeId: string, input: string): CanvasInterfaceCommandResult
  toggleWorkflowOutput(nodeId: string, output: string): CanvasInterfaceCommandResult
  renameWorkflowInput(
    nodeId: string,
    input: string,
    name: string,
  ): CanvasInterfaceCommandResult
  renameWorkflowOutput(
    nodeId: string,
    output: string,
    name: string,
  ): CanvasInterfaceCommandResult
  updateParameter(nodeId: string, key: string, value: unknown): boolean
}

// Shell panels use this state-free adapter to follow Dockview activation.
// It delegates exclusively to a registered canvas resource.
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
    addToolNode: (toolName, parameters) => resource.addToolNode(toolName, parameters),
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
    toggleWorkflowInput: (nodeId, input) => (
      resource.toggleWorkflowInput(nodeId, input)
    ),
    toggleWorkflowOutput: (nodeId, output) => (
      resource.toggleWorkflowOutput(nodeId, output)
    ),
    renameWorkflowInput: (nodeId, input, name) => (
      resource.renameWorkflowInput(nodeId, input, name)
    ),
    renameWorkflowOutput: (nodeId, output, name) => (
      resource.renameWorkflowOutput(nodeId, output, name)
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
    addToolNode: (toolName, parameters) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.addToolNode?.(toolName, parameters) ?? null
    },
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
    toggleWorkflowInput: (nodeId, input) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.toggleWorkflowInput(nodeId, input)
    },
    toggleWorkflowOutput: (nodeId, output) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.toggleWorkflowOutput(nodeId, output)
    },
    renameWorkflowInput: (nodeId, input, name) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.renameWorkflowInput(nodeId, input, name)
    },
    renameWorkflowOutput: (nodeId, output, name) => {
      if (disposed) throw new Error('Canvas commands have been disposed')
      return options.renameWorkflowOutput(nodeId, output, name)
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
      if (activeCanvasId === null) return 'unavailable'
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
    addToolNode: (toolName, parameters) => (
      activeCommandResource()?.addToolNode(toolName, parameters) ?? null
    ),
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
    toggleWorkflowInput: (nodeId, input) => (
      activeCommandResource()?.toggleWorkflowInput(nodeId, input)
      ?? workflowInterfaceUnavailable()
    ),
    toggleWorkflowOutput: (nodeId, output) => (
      activeCommandResource()?.toggleWorkflowOutput(nodeId, output)
      ?? workflowInterfaceUnavailable()
    ),
    renameWorkflowInput: (nodeId, input, name) => (
      activeCommandResource()?.renameWorkflowInput(nodeId, input, name)
      ?? workflowInterfaceUnavailable()
    ),
    renameWorkflowOutput: (nodeId, output, name) => (
      activeCommandResource()?.renameWorkflowOutput(nodeId, output, name)
      ?? workflowInterfaceUnavailable()
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

function workflowInterfaceUnavailable(): CanvasInterfaceCommandResult {
  return { status: 'rejected', reason: 'unavailable' }
}
