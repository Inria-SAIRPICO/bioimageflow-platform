import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'

// Hoisted mock for useGraphSync because the composable imports the
// singleton via `import { useGraphSync } from '@/composables/useGraphSync'`.
const flushNow = vi.fn(async () => {})

vi.mock('@/composables/useGraphSync', () => {
  return {
    useGraphSync: () => ({ flushNow }),
  }
})

// Mock @/api/client so toolRegistry's fetchTools doesn't hit the network.
vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import {
  useFieldFocusTracker,
  __resetForTests as __resetFocusForTests,
} from '@/composables/useFieldFocusTracker'
import { useHotReload, __resetForTests as __resetHotReloadForTests } from '@/composables/useHotReload'
import type { ToolMetadata } from '@/api/types'

const baseTool: ToolMetadata = {
  name: 'GaussianSmooth',
  display_name: 'Gaussian Smooth',
  package: 'dummy',
  package_version: '1.0.0',
  tool_type: 'ProcessingTool',
  documentation: '',
  tags: [],
  categories: [],
  inputs: {
    diameter: { type: 'float', required: true, connectable: 'not_by_default' },
  },
  outputs: { result: { type: 'string' } },
  environment: null,
}

function makeNode(id: string, toolName: string, status = 'unexecuted') {
  return {
    id,
    data: {
      name: id,
      toolName,
      tool: { ...baseTool, name: toolName },
      status,
      parameters: { diameter: 1.0 },
      collapsed: false,
      enabled: true,
      connectedInputs: {},
      pinnedInputs: {},
      output_templates: {},
    },
  }
}

describe('useHotReload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    flushNow.mockClear()
    __resetFocusForTests()
    __resetHotReloadForTests()
  })

  it('non-focused node gets immediate metadata swap, badge, and flushNow', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const node = makeNode('cellpose_1', 'GaussianSmooth')
    ui.setGraphNodes([node])

    // Seed the registry with the original tool.
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()

    useHotReload()

    const updated: ToolMetadata = {
      ...baseTool,
      inputs: {
        ...baseTool.inputs,
        truncate: { type: 'float', required: false, connectable: 'never' },
      },
    }
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: updated,
    })
    await nextTick()
    // Wait for any debounced flush.
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(node.data.tool).toEqual(updated)
    expect(node.data.updatedBadge).toBe(true)
    expect(flushNow).toHaveBeenCalledTimes(1)
  })

  it('focused field defers the metadata swap until blur', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const focus = useFieldFocusTracker()
    const node = makeNode('cellpose_1', 'GaussianSmooth')
    ui.setGraphNodes([node])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()

    focus.trackFocus('cellpose_1.diameter')

    useHotReload()

    const updated: ToolMetadata = {
      ...baseTool,
      inputs: {
        diameter: { type: 'float', required: true, connectable: 'not_by_default' },
        truncate: { type: 'float', required: false, connectable: 'never' },
      },
    }
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: updated,
    })
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    // Schema not yet swapped because the field is focused.
    expect(node.data.tool).toEqual(baseTool)

    // Blur the field — the deferred swap should now apply.
    focus.trackBlur('cellpose_1.diameter')
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(node.data.tool).toEqual(updated)
  })

  it('focused field that is removed by the update emits a toast on blur', async () => {
    const toast = vi.fn()
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const focus = useFieldFocusTracker()
    const node = makeNode('cellpose_1', 'GaussianSmooth')
    ui.setGraphNodes([node])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()

    focus.trackFocus('cellpose_1.diameter')

    useHotReload({ toast })

    // Reload removes "diameter" entirely.
    const updated: ToolMetadata = {
      ...baseTool,
      inputs: {
        sigma: { type: 'float', required: true, connectable: 'not_by_default' },
      },
    }
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: updated,
    })
    await nextTick()

    focus.trackBlur('cellpose_1.diameter')
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(toast).toHaveBeenCalled()
    const message = String(toast.mock.calls[0][0])
    expect(message).toContain('diameter')
    expect(message).toContain('removed')
  })

  it('removed tool flags toolMissing on every node using it', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const a = makeNode('a', 'GaussianSmooth')
    const b = makeNode('b', 'GaussianSmooth')
    const c = makeNode('c', 'OtherTool')
    ui.setGraphNodes([a, b, c])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()

    useHotReload()

    reg.applyToolRemoved({ type: 'tool_removed', tool_name: 'GaussianSmooth' })
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(a.data.toolMissing).toBe(true)
    expect(b.data.toolMissing).toBe(true)
    expect((c.data as Record<string, unknown>).toolMissing).toBeUndefined()
    expect(flushNow).toHaveBeenCalledTimes(1)
  })

  it('coalesces multiple reloads in the same tick to one flushNow', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    ui.setGraphNodes([makeNode('a', 'GaussianSmooth')])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()

    useHotReload()

    for (let i = 0; i < 3; i++) {
      reg.applyToolReload({
        type: 'tool_reload',
        tool_name: 'GaussianSmooth',
        tool_metadata: { ...baseTool, documentation: `v${i}` },
      })
    }
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(flushNow).toHaveBeenCalledTimes(1)
  })

  it('executed node optimistically transitions to out_of_date', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const node = makeNode('a', 'GaussianSmooth', 'executed')
    ui.setGraphNodes([node])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()

    useHotReload()

    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: { ...baseTool, documentation: 'updated' },
    })
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(node.data.status).toBe('out_of_date')
  })

  it('unexecuted node keeps its status', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const node = makeNode('a', 'GaussianSmooth', 'unexecuted')
    ui.setGraphNodes([node])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()

    useHotReload()

    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: { ...baseTool, documentation: 'updated' },
    })
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(node.data.status).toBe('unexecuted')
  })

  it('tool_reload for an unused tool does not call flushNow', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    ui.setGraphNodes([makeNode('a', 'OtherTool')])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'OtherTool',
      tool_metadata: { ...baseTool, name: 'OtherTool' },
    })
    await nextTick()

    useHotReload()

    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    expect(flushNow).not.toHaveBeenCalled()
  })

  it('skips status mutations during execution but still sets badges', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const exec = useExecutionStore()
    const node = makeNode('a', 'GaussianSmooth', 'executed')
    ui.setGraphNodes([node])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()
    // Mark the workflow as running.
    exec.$patch({ state: 'running' })

    useHotReload()

    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: { ...baseTool, documentation: 'updated' },
    })
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))

    // status not flipped while running.
    expect(node.data.status).toBe('executed')
    // But the badge does appear so the user sees the signal.
    expect(node.data.updatedBadge).toBe(true)
  })

  it('dismissBadge clears the badge without other side effects', async () => {
    const ui = useUIStore()
    const reg = useToolRegistryStore()
    const node = makeNode('a', 'GaussianSmooth', 'unexecuted')
    ui.setGraphNodes([node])
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: baseTool,
    })
    await nextTick()
    const hr = useHotReload()
    reg.applyToolReload({
      type: 'tool_reload',
      tool_name: 'GaussianSmooth',
      tool_metadata: { ...baseTool, documentation: 'updated' },
    })
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 5))
    expect(node.data.updatedBadge).toBe(true)
    const beforeStatus = node.data.status

    hr.dismissBadge('a')
    expect(node.data.updatedBadge).toBe(false)
    expect(node.data.status).toBe(beforeStatus)
  })
})
