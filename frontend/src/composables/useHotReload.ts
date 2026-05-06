import { watch } from 'vue'

import type { ToolMetadata } from '@/api/types'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useFieldFocusTracker } from '@/composables/useFieldFocusTracker'
import { useGraphSync } from '@/composables/useGraphSync'
import { reconcileOutputTemplates } from '@/utils/outputTemplates'

interface NodeData {
  toolName: string
  tool: ToolMetadata
  status: string
  parameters: Record<string, unknown>
  output_templates?: Record<string, string>
  updatedBadge?: boolean
  toolMissing?: boolean
}

interface CanvasNode {
  id: string
  data: NodeData
}

export interface UseHotReloadOptions {
  toast?: (message: string) => void
}

interface State {
  initialized: boolean
  stop: (() => void) | null
  pendingFlush: boolean
}

function createState(): State {
  return {
    initialized: false,
    stop: null,
    pendingFlush: false,
  }
}

let state: State = createState()

function snapshotByName(tools: ToolMetadata[]): Map<string, ToolMetadata> {
  const out = new Map<string, ToolMetadata>()
  for (const t of tools) out.set(t.name, t)
  return out
}

interface DiffResult {
  changedOrAdded: ToolMetadata[]
  removed: string[]
}

function diffSnapshots(
  prev: Map<string, ToolMetadata>,
  next: Map<string, ToolMetadata>,
): DiffResult {
  const changedOrAdded: ToolMetadata[] = []
  const removed: string[] = []
  for (const [name, meta] of next) {
    const before = prev.get(name)
    if (before === undefined || before !== meta) {
      changedOrAdded.push(meta)
    }
  }
  for (const name of prev.keys()) {
    if (!next.has(name)) removed.push(name)
  }
  return { changedOrAdded, removed }
}

export function useHotReload(options: UseHotReloadOptions = {}) {
  const toolRegistry = useToolRegistryStore()
  const ui = useUIStore()
  const exec = useExecutionStore()
  const focus = useFieldFocusTracker()
  const graphSync = useGraphSync()

  function applyMetadataSwap(
    node: CanvasNode,
    meta: ToolMetadata,
    isExecuting: boolean,
  ): void {
    node.data.tool = meta
    // Drop parameter values for fields that no longer exist on the
    // updated schema. Incompatible-type values for surviving fields are
    // left in place — the backend's graph_validator will flag them on
    // the next flushNow.
    const params = node.data.parameters ?? {}
    const next: Record<string, unknown> = {}
    for (const key of Object.keys(params)) {
      if (Object.prototype.hasOwnProperty.call(meta.inputs, key)) {
        next[key] = params[key]
      }
    }
    node.data.parameters = next
    node.data.output_templates = reconcileOutputTemplates(
      meta,
      node.data.output_templates ?? {},
    )
    node.data.updatedBadge = true
    if (!isExecuting && node.data.status === 'executed') {
      node.data.status = 'out_of_date'
    }
  }

  function processChanged(meta: ToolMetadata, isExecuting: boolean): boolean {
    let touched = false
    const nodes = ui.graphNodes as CanvasNode[]
    for (const node of nodes) {
      if (node.data.toolName !== meta.name) continue
      touched = true
      if (focus.isAnyFocused(node.id)) {
        // Capture the input names that are *removed* by the new schema
        // so we can surface a toast for any focused field that vanishes.
        const removedFields: string[] = []
        for (const fieldName of Object.keys(node.data.tool.inputs)) {
          if (!Object.prototype.hasOwnProperty.call(meta.inputs, fieldName)) {
            removedFields.push(fieldName)
          }
        }
        // Register an onBlurOnce for every input field on this node;
        // the first one that fires applies the swap. The rest no-op.
        const fieldKeys = Object.keys(node.data.tool.inputs).map(
          (f) => `${node.id}.${f}`,
        )
        let applied = false
        for (const fieldKey of fieldKeys) {
          focus.onBlurOnce(fieldKey, () => {
            if (applied) return
            applied = true
            applyMetadataSwap(node, meta, exec.isRunning)
            if (options.toast) {
              const focusedRemoved = removedFields.find((field) =>
                fieldKey.endsWith(`.${field}`),
              )
              if (focusedRemoved !== undefined) {
                options.toast(
                  `Field '${focusedRemoved}' was removed by the tool update.`,
                )
              }
            }
            scheduleFlush()
          })
        }
      } else {
        applyMetadataSwap(node, meta, isExecuting)
      }
    }
    return touched
  }

  function processRemoved(toolName: string): boolean {
    let touched = false
    const nodes = ui.graphNodes as CanvasNode[]
    for (const node of nodes) {
      if (node.data.toolName !== toolName) continue
      touched = true
      node.data.toolMissing = true
    }
    return touched
  }

  function scheduleFlush(): void {
    if (state.pendingFlush) return
    state.pendingFlush = true
    void Promise.resolve().then(() => {
      state.pendingFlush = false
      void graphSync.flushNow()
    })
  }

  function dismissBadge(nodeId: string): void {
    const nodes = ui.graphNodes as CanvasNode[]
    for (const node of nodes) {
      if (node.id === nodeId) {
        node.data.updatedBadge = false
      }
    }
  }

  function start(): void {
    if (state.initialized) return
    state.initialized = true

    let prev = snapshotByName(toolRegistry.tools as ToolMetadata[])
    state.stop = watch(
      () => toolRegistry.tools,
      (newTools) => {
        const next = snapshotByName(newTools as ToolMetadata[])
        const { changedOrAdded, removed } = diffSnapshots(prev, next)
        prev = next

        if (changedOrAdded.length === 0 && removed.length === 0) return

        let touched = false
        const isExecuting = exec.isRunning
        for (const meta of changedOrAdded) {
          if (processChanged(meta, isExecuting)) touched = true
        }
        for (const name of removed) {
          if (processRemoved(name)) touched = true
        }
        if (touched) scheduleFlush()
      },
      { deep: true },
    )
  }

  function stop(): void {
    if (state.stop !== null) {
      state.stop()
      state.stop = null
    }
    state.initialized = false
  }

  start()

  return { dismissBadge, stop }
}

export function __resetForTests(): void {
  if (state.stop !== null) {
    state.stop()
  }
  state = createState()
}
