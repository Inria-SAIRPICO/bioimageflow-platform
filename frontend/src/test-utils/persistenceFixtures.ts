import { vi } from 'vitest'
import type { GraphState } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import type { CanvasPersistenceTransports } from '@/composables/useCanvasPersistence'
import type { AutoSaveEntry } from '@/composables/useAutoSave'
import { makeGraph, makeValidationResult } from './graphFixtures'

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function makeWorkflowDraft(
  overrides: Partial<WorkflowDraftResponse> = {},
): WorkflowDraftResponse {
  return {
    draft_version: 1,
    workflow_id: 'workflow-a',
    base_saved_revision: 'sha256:test-base',
    draft_revision: 1,
    updated_at: '2026-01-01T00:00:00Z',
    updated_by: 'frontend',
    dirty_against_saved: false,
    graph: makeGraph(),
    validation: makeValidationResult(),
    ...overrides,
  }
}

export interface InMemoryCanvasPersistence {
  readonly transports: CanvasPersistenceTransports
  readonly fetchDraft: ReturnType<typeof vi.fn<CanvasPersistenceTransports['fetchDraft']>>
  readonly putDraft: ReturnType<typeof vi.fn<CanvasPersistenceTransports['putDraft']>>
  readonly writeRecovery: ReturnType<typeof vi.fn<CanvasPersistenceTransports['writeRecovery']>>
  currentDraft(): WorkflowDraftResponse
  recoveryEntries(): AutoSaveEntry[]
}

/** A revision-checking persistence fake for canvas integration tests. */
export function createInMemoryCanvasPersistence(
  initialDraft: WorkflowDraftResponse = makeWorkflowDraft(),
): InMemoryCanvasPersistence {
  let current = clone(initialDraft)
  const recoveries: AutoSaveEntry[] = []
  const fetchDraft = vi.fn<CanvasPersistenceTransports['fetchDraft']>(
    async (workflowId) => {
      if (workflowId !== current.workflow_id) throw new Error('Workflow not found')
      return clone(current)
    },
  )
  const putDraft = vi.fn<CanvasPersistenceTransports['putDraft']>(
    async (workflowId, body) => {
      if (workflowId !== current.workflow_id) throw new Error('Workflow not found')
      if (body.expected_revision !== current.draft_revision) {
        throw {
          response: {
            status: 409,
            data: { current_revision: current.draft_revision },
          },
        }
      }
      current = makeWorkflowDraft({
        ...current,
        draft_revision: current.draft_revision + 1,
        dirty_against_saved: true,
        graph: clone(body.graph as GraphState),
      })
      return clone(current)
    },
  )
  const writeRecovery = vi.fn<CanvasPersistenceTransports['writeRecovery']>(
    async (entry) => {
      recoveries.push(clone(entry))
    },
  )
  return {
    transports: { fetchDraft, putDraft, writeRecovery },
    fetchDraft,
    putDraft,
    writeRecovery,
    currentDraft: () => clone(current),
    recoveryEntries: () => clone(recoveries),
  }
}
