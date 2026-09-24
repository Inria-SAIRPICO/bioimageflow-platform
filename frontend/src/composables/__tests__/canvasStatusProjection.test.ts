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
import { useNestedWorkflowSessionsStore, type NestedWorkflowSession } from '@/stores/nestedWorkflowSessions'
import { emptyGraph } from '@/sessions/graphDocument'
import { resolveNestedExecutionScope, scopedExecutionNodeId } from '@/sessions/nestedExecutionScope'

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

    projection.stageCurrentSemanticStatuses()

    expect(projection.statuses.value['parent/child']).toMatchObject({
      status: 'executed',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(projection.statuses.value['parent/validated']).toMatchObject({
      status: 'out_of_date',
      presentationStatus: 'out_of_date',
      source: 'semantic',
    })
  })

  it('keeps a semantic edit synchronous and clears only covered ids on validation', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const nextValidation = ref<ValidationResult | null>(null)
    const projection = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId, workflowId: 'wf_a' },
      nodes: ref([node('a'), node('b')]),
      validationResult: nextValidation,
      acceptedDraftRevision: ref(7),
    })

    projection.stageSemanticStatus('a', status('a', 'unexecuted'), 'executed')
    projection.stageSemanticStatus('b', status('b', 'out_of_date'), 'executed')
    expect(projection.statusForNode('a')).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'executed',
      source: 'semantic',
    })

    nextValidation.value = validation({ a: status('a', 'out_of_date') })

    expect(projection.statusForNode('a')).toMatchObject({
      status: 'out_of_date',
      presentationStatus: 'out_of_date',
      source: 'validation',
    })
    expect(projection.statusForNode('b')).toMatchObject({
      status: 'out_of_date',
      presentationStatus: 'executed',
      source: 'semantic',
    })
  })

  it('retains the accepted presentation across consecutive semantic edits', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const validationResult = ref<ValidationResult | null>(
      validation({ a: status('a', 'executed') }),
    )
    const projection = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId, workflowId: 'wf_a' },
      nodes: ref([node('a')]),
      validationResult,
      acceptedDraftRevision: ref(7),
    })

    projection.stageCurrentSemanticStatuses()
    projection.stageSemanticStatus('a', status('a', 'unexecuted'), 'executed')
    projection.stageCurrentSemanticStatuses()
    projection.stageSemanticStatus(
      'a',
      status('a', 'unexecuted'),
      projection.statusForNode('a')?.presentationStatus,
    )

    expect(projection.statusForNode('a')).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'executed',
      source: 'semantic',
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
    const nestedId = canvasIdFromPanelId('nested-workflow:a')
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
    const nestedId = canvasIdFromPanelId('nested-workflow:a')
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

  it('projects each nested instance from its own scoped root results', () => {
    const rootId = canvasIdFromPanelId('workflow:a')
    const root = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: rootId, workflowId: 'wf_a' },
      nodes: ref([node('first'), node('second')]),
      validationResult: ref(null),
      acceptedDraftRevision: ref(4),
    })
    useUIStore().setCanvasWorkflow(rootId, 'wf_a', 'Workflow A')
    const sessions = useNestedWorkflowSessionsStore()
    const graph = emptyGraph('child', 'Child')
    function session(id: string, parentNodeId: string): NestedWorkflowSession {
      return {
        id,
        owner: { kind: 'root', canvas_id: rootId, workflow_id: 'wf_a' },
        parentCanvasId: rootId,
        parentWorkflowName: 'wf_a',
        parentSourceWorkflowName: null,
        parentNodeId,
        parentNodeName: parentNodeId,
        draft: structuredClone(graph),
        savedSnapshot: structuredClone(graph),
        acceptedSnapshot: structuredClone(graph),
        parentApplyConflict: null,
        snapshotRevision: 0,
        updatedAt: '2026-01-01T00:00:00Z',
        validation: validation({}),
      }
    }
    sessions.sessions = [session('session-first', 'first'), session('session-second', 'second')]
    sessions.sessions.push({
      ...session('session-deep', 'inner'),
      owner: { kind: 'nested', session_id: 'session-first' },
      parentCanvasId: canvasIdFromPanelId('nested:session-first'),
    })
    function childProjection(id: string) {
      return useCanvasStatusProjection({
        descriptor: {
          kind: 'nested',
          canvasId: canvasIdFromPanelId(`nested:${id}`),
          sessionId: id,
          parentCanvasId: rootId,
        },
        nodes: ref([node('shared')]),
        validationResult: ref(validation({ shared: status('shared', 'unexecuted') })),
        acceptedDraftRevision: ref(null),
      })
    }
    const first = childProjection('session-first')
    const second = childProjection('session-second')
    expect(resolveNestedExecutionScope('session-first', sessions.sessions)?.path).toEqual(['first'])
    expect(scopedExecutionNodeId(
      resolveNestedExecutionScope('session-deep', sessions.sessions), 'leaf',
    )).toBe('first/inner/leaf')

    useExecutionStore().applyStatusSnapshot({
      execution_id: 'exec-a',
      workflow_id: 'wf_a',
      draft_revision: 4,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {
        'first/shared': status('first/shared', 'executed'),
        'second/shared': status('second/shared', 'failed'),
      },
    })
    expect(first.statusForNode('shared')).toMatchObject({ status: 'executed', source: 'execution' })
    expect(second.statusForNode('shared')).toMatchObject({ status: 'failed', source: 'execution' })
    expect(root.statusForNode('first/shared')?.status).toBe('executed')

    sessions.sessions[0]!.draft.display_name = 'Edited child'
    expect(first.statusForNode('shared')).toMatchObject({ status: 'unexecuted', source: 'validation' })
    expect(second.statusForNode('shared')).toMatchObject({ status: 'failed', source: 'execution' })
  })

  it('shows idle corrupt validation in either arrival order and releases it after Clear', () => {
    const canvasId = canvasIdFromPanelId('workflow:corrupt')
    const accepted = ref<ValidationResult | null>({
      valid: false,
      node_statuses: {
        source: status('source', 'failed'),
        dependent: status('dependent', 'out_of_date'),
        sibling: status('sibling', 'executed'),
      },
      errors: [{ type: 'cache_corrupt', node: 'source', detail: 'bad record' }],
    })
    const projection = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId, workflowId: 'wf_corrupt' },
      nodes: ref([node('source'), node('dependent'), node('sibling')]),
      validationResult: accepted,
      acceptedDraftRevision: ref(4),
    })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_corrupt', 'Corrupt')
    const execution = useExecutionStore()
    execution.applyStatusSnapshot({
      execution_id: 'exec-corrupt',
      workflow_id: 'wf_corrupt',
      draft_revision: 4,
      state: 'idle',
      last_result: null,
      progress: null,
      node_statuses: {
        source: status('source', 'executed'),
        dependent: status('dependent', 'executed'),
        sibling: status('sibling', 'executed'),
      },
    })
    expect(projection.statusForNode('source')).toMatchObject({ status: 'failed', source: 'validation' })
    expect(projection.statusForNode('sibling')).toMatchObject({ status: 'executed', source: 'execution' })

    accepted.value = validation({
      source: status('source', 'executed'),
      dependent: status('dependent', 'executed'),
      sibling: status('sibling', 'executed'),
    })
    expect(projection.statusForNode('source')).toMatchObject({ status: 'executed', source: 'execution' })
    accepted.value = {
      valid: false,
      node_statuses: { ...accepted.value.node_statuses, source: status('source', 'failed') },
      errors: [{ type: 'cache_corrupt', node: 'source', detail: 'bad record' }],
    }
    expect(projection.statusForNode('source')).toMatchObject({ status: 'failed', source: 'validation' })

    execution.applyStatusSnapshot({
      execution_id: 'exec-corrupt',
      workflow_id: 'wf_corrupt',
      draft_revision: 4,
      state: 'idle',
      last_result: null,
      progress: null,
      node_statuses: {
        source: status('source', 'unexecuted'),
        dependent: status('dependent', 'out_of_date'),
        sibling: status('sibling', 'executed'),
      },
    })
    accepted.value = validation({
      source: status('source', 'unexecuted'),
      dependent: status('dependent', 'out_of_date'),
      sibling: status('sibling', 'executed'),
    })
    expect(projection.statusForNode('source')).toMatchObject({ status: 'unexecuted' })
    expect(projection.statusForNode('dependent')).toMatchObject({ status: 'out_of_date' })
    expect(projection.statusForNode('sibling')).toMatchObject({ status: 'executed' })
  })

  it('projects an idle corrupt descendant through its aggregate and applied nested canvas', () => {
    const rootId = canvasIdFromPanelId('workflow:aggregate')
    const root = useCanvasStatusProjection({
      descriptor: { kind: 'root', canvasId: rootId, workflowId: 'wf_aggregate' },
      nodes: ref([node('parent'), node('sibling')]),
      validationResult: ref({
        valid: false,
        node_statuses: {
          parent: status('parent', 'failed'),
          'parent/leaf': status('parent/leaf', 'failed'),
          sibling: status('sibling', 'executed'),
        },
        errors: [{ type: 'cache_corrupt', node: 'parent/leaf', detail: 'bad record' }],
      }),
      acceptedDraftRevision: ref(4),
    })
    useUIStore().setCanvasWorkflow(rootId, 'wf_aggregate', 'Aggregate')
    const graph = emptyGraph('child', 'Child')
    useNestedWorkflowSessionsStore().sessions = [{
      id: 'session-corrupt',
      owner: { kind: 'root', canvas_id: rootId, workflow_id: 'wf_aggregate' },
      parentCanvasId: rootId,
      parentWorkflowName: 'wf_aggregate',
      parentSourceWorkflowName: null,
      parentNodeId: 'parent',
      parentNodeName: 'parent',
      draft: structuredClone(graph),
      savedSnapshot: structuredClone(graph),
      acceptedSnapshot: structuredClone(graph),
      parentApplyConflict: null,
      snapshotRevision: 0,
      updatedAt: '2026-01-01T00:00:00Z',
      validation: validation({}),
    }]
    const nested = useCanvasStatusProjection({
      descriptor: {
        kind: 'nested',
        canvasId: canvasIdFromPanelId('nested:session-corrupt'),
        sessionId: 'session-corrupt',
        parentCanvasId: rootId,
      },
      nodes: ref([node('leaf')]),
      validationResult: ref(validation({ leaf: status('leaf', 'unexecuted') })),
      acceptedDraftRevision: ref(null),
    })
    useExecutionStore().applyStatusSnapshot({
      execution_id: 'exec-aggregate',
      workflow_id: 'wf_aggregate',
      draft_revision: 4,
      state: 'idle',
      last_result: null,
      progress: null,
      node_statuses: {
        parent: status('parent', 'executed'),
        'parent/leaf': status('parent/leaf', 'executed'),
        sibling: status('sibling', 'executed'),
      },
    })
    expect(root.statusForNode('parent')).toMatchObject({ status: 'failed', source: 'validation' })
    expect(root.statusForNode('parent/leaf')).toMatchObject({ status: 'failed', source: 'validation' })
    expect(root.statusForNode('sibling')).toMatchObject({ status: 'executed', source: 'execution' })
    expect(nested.statusForNode('leaf')).toMatchObject({ status: 'failed', source: 'validation' })
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
