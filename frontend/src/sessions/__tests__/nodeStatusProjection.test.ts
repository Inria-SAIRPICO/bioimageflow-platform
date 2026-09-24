import { describe, expect, it } from 'vitest'

import type { NodeStatus } from '@/api/types'
import {
  projectNodeStatus,
  type NodeStatusProjectionInput,
} from '@/sessions/nodeStatusProjection'

function status(
  nodeId: string,
  value: NodeStatus['status'],
  extra: Partial<NodeStatus> = {},
): NodeStatus {
  return {
    node_id: nodeId,
    status: value,
    cached: false,
    ...extra,
  }
}

function input(
  overrides: Partial<NodeStatusProjectionInput> = {},
): NodeStatusProjectionInput {
  return {
    nodeId: 'same',
    enabled: true,
    semanticOverride: null,
    semanticPresentationStatus: null,
    executionStatus: null,
    executionPhase: 'idle',
    validationStatus: null,
    validationErrors: [],
    executionOriginMatches: false,
    executionDraftRevision: null,
    acceptedDraftRevision: null,
    ...overrides,
  }
}

describe('projectNodeStatus', () => {
  it.each([
    {
      name: 'local semantic status wins while retaining its stable presentation',
      value: input({
        semanticOverride: status('same', 'unexecuted'),
        semanticPresentationStatus: 'executed',
        executionStatus: status('same', 'executed'),
        validationStatus: status('same', 'failed'),
        executionOriginMatches: true,
        executionDraftRevision: 4,
        acceptedDraftRevision: 4,
      }),
      expected: {
        status: 'unexecuted',
        presentationStatus: 'executed',
        source: 'semantic',
      },
    },
    {
      name: 'exact contextual execution wins over validation',
      value: input({
        executionStatus: status('same', 'running'),
        executionPhase: 'running',
        validationStatus: status('same', 'unexecuted'),
        executionOriginMatches: true,
        executionDraftRevision: 4,
        acceptedDraftRevision: 4,
      }),
      expected: { status: 'running', presentationStatus: 'running', source: 'execution' },
    },
    {
      name: 'mismatched execution revision falls back to validation',
      value: input({
        executionStatus: status('same', 'executed'),
        validationStatus: status('same', 'out_of_date'),
        executionOriginMatches: true,
        executionDraftRevision: 3,
        acceptedDraftRevision: 4,
      }),
      expected: {
        status: 'out_of_date',
        presentationStatus: 'out_of_date',
        source: 'validation',
      },
    },
    {
      name: 'contextual execution with unavailable revision is rejected',
      value: input({
        executionStatus: status('same', 'executed'),
        validationStatus: status('same', 'unexecuted'),
        executionOriginMatches: true,
        executionDraftRevision: null,
        acceptedDraftRevision: 4,
      }),
      expected: {
        status: 'unexecuted',
        presentationStatus: 'unexecuted',
        source: 'validation',
      },
    },
    {
      name: 'execution without an accepted revision never applies',
      value: input({
        executionStatus: status('same', 'running'),
        validationStatus: status('same', 'unexecuted'),
        executionOriginMatches: true,
      }),
      expected: { status: 'unexecuted', presentationStatus: 'unexecuted', source: 'validation' },
    },
    {
      name: 'unowned contextless execution never applies',
      value: input({
        executionStatus: status('same', 'running'),
        validationStatus: status('same', 'unexecuted'),
        executionOriginMatches: false,
      }),
      expected: {
        status: 'unexecuted',
        presentationStatus: 'unexecuted',
        source: 'validation',
      },
    },
    {
      name: 'validation wins when there is no admissible overlay',
      value: input({ validationStatus: status('same', 'failed') }),
      expected: { status: 'failed', presentationStatus: 'failed', source: 'validation' },
    },
    {
      name: 'disabled is the default for a disabled node',
      value: input({ enabled: false }),
      expected: { status: 'disabled', presentationStatus: 'disabled', source: 'default' },
    },
    {
      name: 'unexecuted is the default for an enabled node',
      value: input(),
      expected: {
        status: 'unexecuted',
        presentationStatus: 'unexecuted',
        source: 'default',
      },
    },
  ])('$name', ({ value, expected }) => {
    expect(projectNodeStatus(value)).toMatchObject(expected)
  })

  it('does not let a terminal execution repaint a semantic edit', () => {
    const semanticEdit = projectNodeStatus(input({
      semanticOverride: status('same', 'unexecuted'),
      semanticPresentationStatus: 'executed',
      executionStatus: status('same', 'executed'),
      validationStatus: status('same', 'executed'),
      executionOriginMatches: true,
      executionDraftRevision: 7,
      acceptedDraftRevision: 7,
    }))
    const acceptedEdit = projectNodeStatus(input({
      executionStatus: status('same', 'executed'),
      validationStatus: status('same', 'unexecuted'),
      executionOriginMatches: true,
      executionDraftRevision: 7,
      acceptedDraftRevision: 8,
    }))

    expect(semanticEdit).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(acceptedEdit).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'unexecuted',
      source: 'validation',
    })
  })

  it.each([
    { nodeId: 'source', errorNode: 'source' },
    { nodeId: 'parent', errorNode: 'parent/internal' },
  ])('shows idle cache corruption for $nodeId over a retained success', ({ nodeId, errorNode }) => {
    expect(projectNodeStatus(input({
      nodeId,
      executionStatus: status(nodeId, 'executed'),
      validationStatus: status(nodeId, 'failed'),
      validationErrors: [{ type: 'cache_corrupt', node: errorNode, detail: 'bad record' }],
      executionOriginMatches: true,
      executionDraftRevision: 4,
      acceptedDraftRevision: 4,
    }))).toMatchObject({ status: 'failed', source: 'validation' })
  })

  it('keeps active execution and ordinary terminal failures ahead of cache diagnostics', () => {
    const corrupt = [{ type: 'cache_corrupt' as const, node: 'source', detail: 'bad record' }]
    for (const executionPhase of ['starting', 'running', 'stopping'] as const) {
      expect(projectNodeStatus(input({
        executionStatus: status('same', 'running'),
        executionPhase,
        validationStatus: status('same', 'failed'),
        validationErrors: [{ ...corrupt[0]!, node: 'same' }],
        executionOriginMatches: true,
        executionDraftRevision: 4,
        acceptedDraftRevision: 4,
      }))).toMatchObject({ status: 'running', source: 'execution' })
    }
    expect(projectNodeStatus(input({
      executionStatus: status('same', 'failed'),
      validationStatus: status('same', 'failed'),
      validationErrors: [{ type: 'parameter_invalid', node: 'same', detail: 'bad input' }],
      executionOriginMatches: true,
      executionDraftRevision: 4,
      acceptedDraftRevision: 4,
    }))).toMatchObject({ status: 'failed', source: 'execution' })
  })

  it('does not transfer a sibling or similarly prefixed corrupt path', () => {
    for (const errorNode of ['sibling', 'same_other', 'other/same']) {
      expect(projectNodeStatus(input({
        executionStatus: status('same', 'executed'),
        validationStatus: status('same', 'failed'),
        validationErrors: [{ type: 'cache_corrupt', node: errorNode, detail: 'bad record' }],
        executionOriginMatches: true,
        executionDraftRevision: 4,
        acceptedDraftRevision: 4,
      }))).toMatchObject({ status: 'executed', source: 'execution' })
    }
  })
})
