import { describe, expect, it } from 'vitest'
import { makeGraph, makeValidationResult } from '@/test-utils/graphFixtures'
import {
  CanvasSessionRegistry,
  canvasIdFromPanelId,
} from '../canvasSessionRegistry'
import {
  NestedWorkflowApplyCoordinator,
  nestedWorkflowApplyGuard,
  type NestedWorkflowApplyOutcome,
} from '../nestedWorkflowApplyCoordinator'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((accept) => { resolve = accept })
  return { promise, resolve }
}

describe('nested workflow apply coordinator', () => {
  it('refuses changed parent/session/registrations/effects and a new lock at confirmation', () => {
    const registry = new CanvasSessionRegistry()
    const nestedCanvasId = canvasIdFromPanelId('nested:guard')
    const parentCanvasId = canvasIdFromPanelId('root:guard')
    const parent = registry.register({ kind: 'root', canvasId: parentCanvasId, workflowId: 'parent' })
    const nested = registry.register({
      kind: 'nested', canvasId: nestedCanvasId, sessionId: 'session', parentCanvasId,
    })
    const session = {}
    const graph = makeGraph({ name: 'parent' })
    const effects = {
      inputIds: ['input'], outputIds: [], edgeIds: ['edge'], bindingIds: [],
      enclosingInputIds: [], enclosingOutputIds: [],
    }
    const baseline = {
      expectedSession: session,
      currentSession: session,
      expectedParentRegistrationToken: parent.registrationToken,
      currentParentRegistrationToken: parent.registrationToken,
      expectedNestedRegistrationToken: nested.registrationToken,
      currentNestedRegistrationToken: nested.registrationToken,
      expectedParentGraph: graph,
      currentParentGraph: graph,
      expectedEffects: effects,
      currentEffects: effects,
      locked: false,
    }
    expect(nestedWorkflowApplyGuard(baseline)).toBeNull()
    expect(nestedWorkflowApplyGuard({ ...baseline, currentSession: {} })).toEqual({
      status: 'conflict', reason: 'parent_changed',
    })
    expect(nestedWorkflowApplyGuard({
      ...baseline, currentParentRegistrationToken: null,
    })).toEqual({ status: 'conflict', reason: 'parent_changed' })
    expect(nestedWorkflowApplyGuard({
      ...baseline, currentNestedRegistrationToken: null,
    })).toEqual({ status: 'conflict', reason: 'parent_changed' })
    expect(nestedWorkflowApplyGuard({
      ...baseline, currentParentGraph: makeGraph({ name: 'changed' }),
    })).toEqual({ status: 'conflict', reason: 'parent_changed' })
    expect(nestedWorkflowApplyGuard({
      ...baseline, currentEffects: { ...effects, edgeIds: [] },
    })).toEqual({ status: 'conflict', reason: 'parent_changed' })
    expect(nestedWorkflowApplyGuard({ ...baseline, locked: true })).toEqual({
      status: 'rejected', reason: 'locked',
    })
  })

  it('coalesces concurrent saves around the first exact accepted private revision', async () => {
    const registry = new CanvasSessionRegistry()
    const nestedCanvasId = canvasIdFromPanelId('nested:a')
    const parentCanvasId = canvasIdFromPanelId('root:a')
    const nested = registry.register({
      kind: 'nested', canvasId: nestedCanvasId, sessionId: 'session', parentCanvasId,
    })
    const sessionIdentity = {}
    const graphA = makeGraph({ name: 'a' })
    const graphB = makeGraph({ name: 'b' })
    const pending = deferred<NestedWorkflowApplyOutcome>()
    const coordinator = new NestedWorkflowApplyCoordinator()
    let calls = 0
    const run = () => { calls += 1; return pending.promise }

    const first = coordinator.run({
      sessionId: 'session', sessionIdentity, nestedCanvasId,
      nestedRegistrationToken: nested.registrationToken,
      acceptedGraph: graphA, acceptedRevision: 2,
      acceptedValidation: makeValidationResult(),
    }, run)
    const second = coordinator.run({
      sessionId: 'session', sessionIdentity, nestedCanvasId,
      nestedRegistrationToken: nested.registrationToken,
      acceptedGraph: graphB, acceptedRevision: 3,
      acceptedValidation: makeValidationResult(),
    }, run)

    expect(second).toBe(first)
    expect(calls).toBe(1)
    pending.resolve({ status: 'applied' })
    registry.unregister(nestedCanvasId)
    const remounted = registry.register({
      kind: 'nested', canvasId: nestedCanvasId, sessionId: 'session', parentCanvasId,
    })
    const resolved = await first
    expect(resolved).toMatchObject({
      capture: { acceptedGraph: graphA, acceptedRevision: 2 },
      outcome: { status: 'applied' },
    })
    expect(resolved.capture.nestedRegistrationToken).not.toBe(remounted.registrationToken)
  })

  it('retains a failed parent apply for retry while adopting a remounted canvas token', async () => {
    const registry = new CanvasSessionRegistry()
    const nestedCanvasId = canvasIdFromPanelId('nested:a')
    const parentCanvasId = canvasIdFromPanelId('root:a')
    const firstRegistration = registry.register({
      kind: 'nested', canvasId: nestedCanvasId, sessionId: 'session', parentCanvasId,
    })
    const sessionIdentity = {}
    const graphA = makeGraph({ name: 'a' })
    const graphB = makeGraph({ name: 'b' })
    const coordinator = new NestedWorkflowApplyCoordinator()
    let parentWrites = 0
    const first = await coordinator.run({
      sessionId: 'session', sessionIdentity, nestedCanvasId,
      nestedRegistrationToken: firstRegistration.registrationToken,
      acceptedGraph: graphA, acceptedRevision: 2,
      acceptedValidation: makeValidationResult(),
    }, async (capture) => {
      parentWrites += 1
      capture.parent = {
        canvasId: parentCanvasId,
        registrationToken: firstRegistration.registrationToken,
        graphBefore: makeGraph({ name: 'parent' }),
        graphApplied: makeGraph({ name: 'parent-applied' }),
        effects: {
          inputIds: [], outputIds: [], edgeIds: [], bindingIds: [],
          enclosingInputIds: [], enclosingOutputIds: [],
        },
      }
      return { status: 'rejected', reason: 'persistence_failed' }
    })
    expect(first.outcome).toEqual({ status: 'rejected', reason: 'persistence_failed' })

    registry.unregister(nestedCanvasId)
    const remounted = registry.register({
      kind: 'nested', canvasId: nestedCanvasId, sessionId: 'session', parentCanvasId,
    })
    const retried = await coordinator.run({
      sessionId: 'session', sessionIdentity, nestedCanvasId,
      nestedRegistrationToken: remounted.registrationToken,
      acceptedGraph: graphB, acceptedRevision: 3,
      acceptedValidation: makeValidationResult(),
    }, async (capture) => {
      parentWrites += 1
      if (capture.retrying) return { status: 'applied' }
      return { status: 'rejected', reason: 'persistence_failed' }
    })

    expect(retried.capture).toMatchObject({
      retrying: true,
      acceptedGraph: graphA,
      acceptedRevision: 2,
      nestedRegistrationToken: remounted.registrationToken,
    })
    expect(retried.capture.parent).not.toBeNull()
    expect(retried.outcome).toEqual({ status: 'applied' })
    expect(parentWrites).toBe(2)
  })
})
