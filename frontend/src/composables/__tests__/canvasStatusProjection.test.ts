import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

import type { NodeStatus, ValidationResult } from '@/api/types'
import {
  useCanvasStatusProjection,
  type CanvasStatusNode,
} from '@/composables/useCanvasStatusProjection'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'

function node(id: string, enabled = true): CanvasStatusNode {
  return { id, enabled }
}

function status(
  nodeId: string,
  value: NodeStatus['status'],
  extra: Partial<NodeStatus> = {},
): NodeStatus {
  return { node_id: nodeId, status: value, cached: false, ...extra }
}

function validation(statuses: Record<string, NodeStatus>): ValidationResult {
  return { valid: true, node_statuses: statuses, errors: [] }
}

describe('canvas status projection resource', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
  })

  it('isolates identical node ids and an exact execution overlay by fixed canvas', () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const nodesA = ref([node('same')])
    const nodesB = ref([node('same')])
    const validationA = ref<ValidationResult | null>(
      validation({ same: status('same', 'unexecuted') }),
    )
    const validationB = ref<ValidationResult | null>(
      validation({ same: status('same', 'out_of_date') }),
    )
    const revisionA = ref<number | null>(4)
    const revisionB = ref<number | null>(4)
    const projectionA = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'wf_a' },
      nodes: nodesA,
      validationResult: validationA,
      acceptedDraftRevision: revisionA,
    })
    const projectionB = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'wf_b' },
      nodes: nodesB,
      validationResult: validationB,
      acceptedDraftRevision: revisionB,
    })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'wf_a', 'Workflow A')
    ui.setCanvasWorkflow(canvasB, 'wf_b', 'Workflow B')
    const execution = useExecutionStore()

    execution.applyStatusSnapshot({
      execution_id: 'exec-a',
      workflow_id: 'wf_a',
      draft_revision: 4,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: { same: status('same', 'running') },
    })

    expect(projectionA.statusForNode('same')).toMatchObject({
      status: 'running',
      source: 'execution',
    })
    expect(projectionB.statusForNode('same')).toMatchObject({
      status: 'out_of_date',
      source: 'validation',
    })
  })

  it('projects validation received before nodes mount and execution received afterward', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const nodes = ref<CanvasStatusNode[]>([])
    const acceptedDraftRevision = ref<number | null>(2)
    const projection = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId, workflowId: 'wf_a' },
      nodes,
      validationResult: ref(validation({ same: status('same', 'executed') })),
      acceptedDraftRevision,
    })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')

    expect(projection.statusForNode('same')).toBeNull()
    nodes.value = [node('same')]
    expect(projection.statusForNode('same')).toMatchObject({ status: 'executed' })

    useExecutionStore().applyStatusSnapshot({
      execution_id: 'exec-a',
      workflow_id: 'wf_a',
      draft_revision: 2,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: { same: status('same', 'running') },
    })
    expect(projection.statusForNode('same')).toMatchObject({ status: 'running' })
  })

  it('projects owned scoped statuses without admitting unrelated execution keys', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const projection = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId, workflowId: 'wf_a' },
      nodes: ref([node('parent')]),
      validationResult: ref(validation({
        'parent/validated': status('parent/validated', 'out_of_date'),
      })),
      acceptedDraftRevision: ref(3),
    })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')

    useExecutionStore().applyStatusSnapshot({
      execution_id: 'exec-a',
      workflow_id: 'wf_a',
      draft_revision: 3,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {
        'parent/child': status('parent/child', 'executed'),
        'other/child': status('other/child', 'failed'),
      },
    })

    expect(projection.statusForNode('parent/child')).toMatchObject({
      status: 'executed',
      source: 'execution',
    })
    expect(projection.statuses.value['parent/child']).toMatchObject({
      status: 'executed',
      source: 'execution',
    })
    expect(projection.statuses.value['parent/validated']).toMatchObject({
      status: 'out_of_date',
      source: 'validation',
    })
    expect(projection.statusForNode('other/child')).toBeNull()
    expect(projection.statuses.value['other/child']).toBeUndefined()

    projection.markAllProvisional()

    expect(projection.statuses.value['parent/child']).toMatchObject({
      status: 'executed',
      provisional: true,
    })
    expect(projection.statuses.value['parent/validated']).toMatchObject({
      status: 'out_of_date',
      provisional: true,
    })
  })

  it('keeps a provisional edit synchronous and clears only covered ids on validation', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const nextValidation = ref<ValidationResult | null>(null)
    const projection = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId, workflowId: 'wf_a' },
      nodes: ref([node('a'), node('b')]),
      validationResult: nextValidation,
      acceptedDraftRevision: ref(7),
    })

    projection.markProvisional('a', status('a', 'unexecuted'))
    projection.markProvisional('b', status('b', 'out_of_date'))
    expect(projection.statusForNode('a')).toMatchObject({
      status: 'unexecuted',
      provisional: true,
    })

    nextValidation.value = validation({ a: status('a', 'executed') })

    expect(projection.statusForNode('a')).toMatchObject({
      status: 'executed',
      provisional: false,
    })
    expect(projection.statusForNode('b')).toMatchObject({
      status: 'out_of_date',
      provisional: true,
    })
  })

  it('rejects a contextless overlay instead of assigning it to an active canvas', () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const projectionA = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'wf_a' },
      nodes: ref([node('same')]),
      validationResult: ref(null),
      acceptedDraftRevision: ref(4),
    })
    const projectionB = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'wf_b' },
      nodes: ref([node('same')]),
      validationResult: ref(null),
      acceptedDraftRevision: ref(4),
    })
    canvasSessionRegistry.activate(canvasA)

    const execution = useExecutionStore()
    execution.applyNodeState({
      node_id: 'same',
      status: 'running',
      cached: false,
    } as never)

    expect(execution.nodeStatuses.same).toBeUndefined()
    expect(projectionA.statusForNode('same')).toMatchObject({ status: 'unexecuted' })
    expect(projectionB.statusForNode('same')).toMatchObject({ status: 'unexecuted' })
  })

  it('never applies a contextual root overlay to a nested canvas', () => {
    const rootId = canvasIdFromPanelId('workflow:a')
    const nestedId = canvasIdFromPanelId('subworkflow:a')
    useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: rootId, workflowId: 'wf_a' },
      nodes: ref([node('same')]),
      validationResult: ref(null),
      acceptedDraftRevision: ref(4),
    })
    const nested = useCanvasStatusProjection({
      descriptor: {
        kind: 'nested',
        canvasId: nestedId,
        sessionId: 'session-a',
        parentCanvasId: rootId,
      },
      nodes: ref([node('same')]),
      validationResult: ref(validation({ same: status('same', 'out_of_date') })),
      acceptedDraftRevision: ref(null),
    })
    useUIStore().setCanvasWorkflow(rootId, 'wf_a', 'Workflow A')

    useExecutionStore().applyStatusSnapshot({
      execution_id: 'exec-a',
      workflow_id: 'wf_a',
      draft_revision: 4,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: { same: status('same', 'running') },
    })

    expect(nested.statusForNode('same')).toMatchObject({
      status: 'out_of_date',
      source: 'validation',
    })
  })

  it('never applies a contextless overlay to a registered nested canvas', () => {
    const rootId = canvasIdFromPanelId('workflow:a')
    const nestedId = canvasIdFromPanelId('subworkflow:a')
    const nested = useCanvasStatusProjection({
      descriptor: {
        kind: 'nested',
        canvasId: nestedId,
        sessionId: 'session-a',
        parentCanvasId: rootId,
      },
      nodes: ref([node('same')]),
      validationResult: ref(validation({ same: status('same', 'out_of_date') })),
      acceptedDraftRevision: ref(null),
    })

    useExecutionStore().applyNodeState({
      node_id: 'same',
      status: 'running',
      cached: false,
    } as never)

    expect(nested.statusForNode('same')).toMatchObject({
      status: 'out_of_date',
      source: 'validation',
    })
  })

  it('does not activate canvases and disposal leaves another resource intact', () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const projectionA = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'wf_a' },
      nodes: ref([node('same')]),
      validationResult: ref(null),
      acceptedDraftRevision: ref(1),
    })
    const projectionB = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'wf_b' },
      nodes: ref([node('same')]),
      validationResult: ref(null),
      acceptedDraftRevision: ref(1),
    })

    expect(canvasSessionRegistry.activeCanvasId.value).toBeNull()
    canvasSessionRegistry.unregister(canvasA)

    expect(projectionA.statusForNode('same')).toBeNull()
    expect(projectionB.statusForNode('same')).toMatchObject({ status: 'unexecuted' })
  })
})
