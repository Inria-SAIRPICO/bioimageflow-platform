import type { GraphState, ValidationResult } from '@/api/types'
import type {
  CanvasId,
  CanvasSessionRegistrationToken,
} from './canvasSessionRegistry'
import { graphDocumentsEqual, jsonDocumentsEqual } from './graphDocument'

export interface NestedWorkflowApplyEffects {
  inputIds: string[]
  outputIds: string[]
  edgeIds: string[]
  bindingIds: string[]
  enclosingInputIds: string[]
  enclosingOutputIds: string[]
}

export interface NestedWorkflowParentApplyCapture {
  canvasId: CanvasId
  registrationToken: CanvasSessionRegistrationToken
  graphBefore: GraphState
  graphApplied: GraphState | null
  effects: NestedWorkflowApplyEffects
}

export interface NestedWorkflowApplyCapture {
  sessionId: string
  sessionIdentity: object
  nestedCanvasId: CanvasId
  nestedRegistrationToken: CanvasSessionRegistrationToken
  acceptedGraph: GraphState
  acceptedRevision: number
  acceptedValidation: ValidationResult
  retrying: boolean
  parent: NestedWorkflowParentApplyCapture | null
}

export type NestedWorkflowApplyOutcome =
  | { status: 'applied' }
  | { status: 'cancelled' }
  | { status: 'conflict'; reason: 'parent_missing' | 'parent_changed' }
  | { status: 'rejected'; reason: 'locked' | 'persistence_failed' }

export function nestedWorkflowApplyGuard(input: {
  expectedSession: object
  currentSession: object | null
  expectedParentRegistrationToken: CanvasSessionRegistrationToken
  currentParentRegistrationToken: CanvasSessionRegistrationToken | null
  expectedNestedRegistrationToken: CanvasSessionRegistrationToken
  currentNestedRegistrationToken: CanvasSessionRegistrationToken | null
  expectedParentGraph: GraphState
  currentParentGraph: GraphState | null
  expectedEffects: NestedWorkflowApplyEffects
  currentEffects: NestedWorkflowApplyEffects | null
  locked: boolean
}): NestedWorkflowApplyOutcome | null {
  if (
    input.currentSession !== input.expectedSession
    || input.currentParentRegistrationToken !== input.expectedParentRegistrationToken
    || input.currentNestedRegistrationToken !== input.expectedNestedRegistrationToken
    || input.currentParentGraph === null
    || !graphDocumentsEqual(input.currentParentGraph, input.expectedParentGraph)
    || input.currentEffects === null
    || !jsonDocumentsEqual(input.currentEffects, input.expectedEffects)
  ) return { status: 'conflict', reason: 'parent_changed' }
  return input.locked ? { status: 'rejected', reason: 'locked' } : null
}

type ApplyRunner = (
  capture: NestedWorkflowApplyCapture,
) => Promise<NestedWorkflowApplyOutcome>

interface ApplyState {
  capture: NestedWorkflowApplyCapture
  promise: Promise<{ capture: NestedWorkflowApplyCapture; outcome: NestedWorkflowApplyOutcome }> | null
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export class NestedWorkflowApplyCoordinator {
  private readonly states = new Map<string, ApplyState>()

  run(
    requested: Omit<NestedWorkflowApplyCapture, 'retrying' | 'parent'>,
    runner: ApplyRunner,
  ): Promise<{ capture: NestedWorkflowApplyCapture; outcome: NestedWorkflowApplyOutcome }> {
    const existing = this.states.get(requested.sessionId)
    if (existing?.promise) return existing.promise

    const retry = existing?.capture
    const capture: NestedWorkflowApplyCapture = retry
      && retry.sessionIdentity === requested.sessionIdentity
      ? {
          ...retry,
          nestedCanvasId: requested.nestedCanvasId,
          nestedRegistrationToken: requested.nestedRegistrationToken,
          retrying: true,
        }
      : {
          ...requested,
          acceptedGraph: cloneJson(requested.acceptedGraph),
          acceptedValidation: cloneJson(requested.acceptedValidation),
          retrying: false,
          parent: null,
        }
    const state: ApplyState = { capture, promise: null }
    const promise = runner(capture).then((outcome) => {
      if (outcome.status !== 'rejected' || outcome.reason !== 'persistence_failed') {
        if (this.states.get(capture.sessionId) === state) this.states.delete(capture.sessionId)
      }
      return { capture, outcome }
    }).catch((error) => {
      if (this.states.get(capture.sessionId) === state) this.states.delete(capture.sessionId)
      throw error
    }).finally(() => {
      if (state.promise === promise) state.promise = null
    })
    state.promise = promise
    this.states.set(capture.sessionId, state)
    return promise
  }

  clear(sessionId: string): void {
    this.states.delete(sessionId)
  }

  reset(): void {
    this.states.clear()
  }
}

export const nestedWorkflowApplyCoordinator = new NestedWorkflowApplyCoordinator()
