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
    provisionalOverride: null,
    executionStatus: null,
    validationStatus: null,
    executionOriginMatches: false,
    executionIsContextless: false,
    allowContextlessLegacyExecution: false,
    executionDraftRevision: null,
    acceptedDraftRevision: null,
    ...overrides,
  }
}

describe('projectNodeStatus', () => {
  it.each([
    {
      name: 'local provisional wins over exact execution and validation',
      value: input({
        provisionalOverride: status('same', 'unexecuted'),
        executionStatus: status('same', 'executed'),
        validationStatus: status('same', 'failed'),
        executionOriginMatches: true,
        executionDraftRevision: 4,
        acceptedDraftRevision: 4,
      }),
      expected: { status: 'unexecuted', provisional: true, source: 'provisional' },
    },
    {
      name: 'exact contextual execution wins over validation',
      value: input({
        executionStatus: status('same', 'running'),
        validationStatus: status('same', 'unexecuted'),
        executionOriginMatches: true,
        executionDraftRevision: 4,
        acceptedDraftRevision: 4,
      }),
      expected: { status: 'running', provisional: false, source: 'execution' },
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
      expected: { status: 'out_of_date', provisional: false, source: 'validation' },
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
      expected: { status: 'unexecuted', provisional: false, source: 'validation' },
    },
    {
      name: 'explicitly owned contextless legacy execution remains compatible',
      value: input({
        executionStatus: status('same', 'running'),
        validationStatus: status('same', 'unexecuted'),
        executionOriginMatches: true,
        executionIsContextless: true,
        allowContextlessLegacyExecution: true,
      }),
      expected: { status: 'running', provisional: false, source: 'execution' },
    },
    {
      name: 'unowned contextless execution never applies',
      value: input({
        executionStatus: status('same', 'running'),
        validationStatus: status('same', 'unexecuted'),
        executionOriginMatches: false,
        executionIsContextless: true,
        allowContextlessLegacyExecution: true,
      }),
      expected: { status: 'unexecuted', provisional: false, source: 'validation' },
    },
    {
      name: 'validation wins when there is no admissible overlay',
      value: input({ validationStatus: status('same', 'failed') }),
      expected: { status: 'failed', provisional: false, source: 'validation' },
    },
    {
      name: 'disabled is the default for a disabled node',
      value: input({ enabled: false }),
      expected: { status: 'disabled', provisional: false, source: 'default' },
    },
    {
      name: 'unexecuted is the default for an enabled node',
      value: input(),
      expected: { status: 'unexecuted', provisional: false, source: 'default' },
    },
  ])('$name', ({ value, expected }) => {
    expect(projectNodeStatus(value)).toMatchObject(expected)
  })

  it('does not let a terminal execution repaint a semantic edit', () => {
    const provisional = projectNodeStatus(input({
      provisionalOverride: status('same', 'unexecuted'),
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

    expect(provisional).toMatchObject({ status: 'unexecuted', provisional: true })
    expect(acceptedEdit).toMatchObject({
      status: 'unexecuted',
      provisional: false,
      source: 'validation',
    })
  })
})
