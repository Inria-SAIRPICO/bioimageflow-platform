import { computed, ref, shallowRef, watch } from 'vue'
import { api } from '@/api/client'
import type { GraphState, OutputPlanningReport, OutputTemplateCheckResponse } from '@/api/types'
import { useExecutionStore } from '@/stores/execution'
import { useSettingsStore } from '@/stores/settings'
import { useCanvasCommands } from '@/composables/useCanvasCommands'
import { getRootCanvasPersistenceResource } from '@/composables/useCanvasPersistence'
import { useExecutionLock } from '@/composables/useExecutionLock'
import { canvasSessionRegistry, type CanvasId, type CanvasSessionRegistrationToken } from '@/sessions/canvasSessionRegistry'
import { graphDocumentsEqual } from '@/sessions/graphDocument'
import { apiErrorMessage } from '@/utils/apiError'

interface RecoveryOwner {
  canvasId: CanvasId
  registration: CanvasSessionRegistrationToken
  executionId: string
  workflowId: string
  draftRevision: number
  workspace: string | null
  graph: GraphState
  nodes: string[] | undefined
}

const DISMISSED_KEY = 'bioimageflow.output-planning-dismissed'

function dismissedRuns(): string[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(DISMISSED_KEY) ?? '[]')
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
  } catch { return [] }
}

function rememberDismissal(executionId: string): void {
  try {
    sessionStorage.setItem(DISMISSED_KEY, JSON.stringify([...new Set([...dismissedRuns(), executionId])].slice(-32)))
  } catch { /* Storage can be unavailable; the component still withdraws its dialog. */ }
}

function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T }

/** Recovery is an ordinary accepted canvas edit followed by an ordinary new Run. */
export function useOutputPlanningRecovery() {
  const exec = useExecutionStore()
  const settings = useSettingsStore()
  const commands = useCanvasCommands()
  const { lockForExecution } = useExecutionLock()
  const owner = shallowRef<RecoveryOwner | null>(null)
  const report = shallowRef<OutputPlanningReport | null>(null)
  const busy = ref(false)
  const error = ref<string | null>(null)
  const validationReports = ref<OutputPlanningReport[]>([])
  const applied = ref(false)
  const withdrawn = new Set<string>()
  const workspace = computed(() => settings.settings?.workspace_path ?? null)
  const resource = computed(() => owner.value ? getRootCanvasPersistenceResource(owner.value.canvasId) : null)

  function sameIdentity(captured: RecoveryOwner): boolean {
    const session = canvasSessionRegistry.get(captured.canvasId)
    return canvasSessionRegistry.activeCanvasId.value === captured.canvasId
      && session?.registrationToken === captured.registration
      && session.descriptor.kind === 'root'
      && exec.executionId === captured.executionId
      && exec.state === 'idle'
      && workspace.value === captured.workspace
      && resource.value?.workflowId.value === captured.workflowId
  }

  function current(captured: RecoveryOwner): boolean {
    return sameIdentity(captured)
      && resource.value?.acceptedDraftRevision.value === captured.draftRevision
      && graphDocumentsEqual(resource.value.currentGraph.value, captured.graph)
  }

  function dismiss(): void {
    if (busy.value) return
    if (owner.value) {
      withdrawn.add(owner.value.executionId)
      rememberDismissal(owner.value.executionId)
    }
    owner.value = null
    report.value = null
    error.value = null
    validationReports.value = []
    applied.value = false
  }

  watch(() => [
    exec.state, exec.executionId, exec.lastResult,
    canvasSessionRegistry.activeCanvasId.value, canvasSessionRegistry.sessionCount.value,
    resource.value?.currentGraph.value, resource.value?.acceptedDraftRevision.value,
    workspace.value, busy.value,
  ], () => {
    if (busy.value) return
    if (owner.value) {
      if (applied.value ? !sameIdentity(owner.value) : !current(owner.value)) dismiss()
      return
    }
    const candidate = exec.lastResult?.output_planning_reports?.[0]
    const executionId = exec.executionId
    if (exec.state !== 'idle' || !candidate || !executionId || withdrawn.has(executionId) || dismissedRuns().includes(executionId)) return
    const canvasId = canvasSessionRegistry.activeCanvasId.value
    if (canvasId === null || exec.originCanvasId !== canvasId) return
    const session = canvasSessionRegistry.get(canvasId)
    const persistence = getRootCanvasPersistenceResource(canvasId)
    if (!session || session.descriptor.kind !== 'root' || !persistence
      || persistence.workflowId.value !== exec.executionWorkflowId
      || persistence.acceptedDraftRevision.value !== exec.executionDraftRevision
      || exec.executionWorkflowId === null || exec.executionDraftRevision === null) return
    if (exec.originGraph !== null && !graphDocumentsEqual(exec.originGraph, persistence.currentGraph.value)) return
    owner.value = {
      canvasId, registration: session.registrationToken, executionId,
      workflowId: exec.executionWorkflowId, draftRevision: exec.executionDraftRevision,
      workspace: workspace.value, graph: clone(persistence.currentGraph.value),
      nodes: exec.requestedNodes === null ? undefined : [...exec.requestedNodes],
    }
    report.value = clone(candidate)
  }, { immediate: true, flush: 'sync' })

  const correctionUnavailableReason = computed(() => applied.value
    ? 'The template change remains in your workflow. Start execution again after resolving the reported problem.'
    : null)
  const reports = computed(() => exec.lastResult?.output_planning_reports ?? [])

  function selectReport(nodeId: string): void {
    if (busy.value || applied.value || !owner.value || !current(owner.value)) return
    const selected = reports.value.find(candidate => candidate.node_id === nodeId)
    if (!selected) return
    report.value = clone(selected)
    validationReports.value = []
    error.value = null
  }

  async function submit(templates: Record<string, string>): Promise<void> {
    const captured = owner.value
    const originalReport = report.value
    if (busy.value || !captured || !originalReport || !current(captured) || !originalReport.correction_available || applied.value) return
    busy.value = true
    error.value = null
    validationReports.value = []
    let edited = false
    try {
      const persistence = resource.value!
      if (!await persistence.ensureFreshForCriticalOperation() || !current(captured)) {
        throw new Error('The workflow changed. Resolve its draft changes before correcting these templates.')
      }
      const { data } = await api.post<OutputTemplateCheckResponse>('/api/v1/execution/output-templates/check', {
        execution_id: captured.executionId, workflow_id: captured.workflowId,
        draft_revision: captured.draftRevision, node_id: originalReport.node_id, templates,
      })
      if (!current(captured)) throw new Error('The workflow or execution changed while the templates were checked.')
      if (!data.valid) {
        validationReports.value = data.reports ?? []
        error.value = data.reports?.[0]?.detail ?? 'These templates still produce conflicting destinations.'
        return
      }
      if (!commands.setOutputTemplates(originalReport.node_id, templates, captured.canvasId)) {
        throw new Error('The template correction could not be applied. Check the node and close any enclosing nested editor.')
      }
      edited = true
      const correctedGraph = clone(persistence.currentGraph.value)
      await persistence.flush()
      applied.value = true
      if (!sameIdentity(captured) || !graphDocumentsEqual(persistence.currentGraph.value, correctedGraph)) {
        throw new Error('The workflow changed after the template edit; execution was not restarted.')
      }
      const revision = persistence.acceptedDraftRevision.value
      if (revision === null) throw new Error('The template change has no accepted draft revision.')
      const started = await lockForExecution({
        graph: correctedGraph, nodes: captured.nodes,
        validationResult: persistence.validationResult.value,
        workflowName: captured.workflowId, canvasId: captured.canvasId,
        acceptedDraftRevision: revision,
        isTargetActive: () => sameIdentity(captured) && graphDocumentsEqual(persistence.currentGraph.value, correctedGraph),
      })
      if (!started) throw new Error('The template was updated, but the workflow is no longer active.')
      withdrawn.add(captured.executionId)
      rememberDismissal(captured.executionId)
      report.value = null
      owner.value = null
    } catch (cause) {
      const detail = apiErrorMessage(cause)
      error.value = edited ? `The template change was kept in your canvas, but execution did not restart. ${detail}` : detail
      if (edited) applied.value = true
    } finally {
      busy.value = false
    }
  }

  return { report, reports, busy, error, validationReports, correctionUnavailableReason, dismiss, submit, selectReport }
}
