export const CANVAS_LOADING_PANEL_ID = 'canvas-loading'
export const CANVAS_EMPTY_PANEL_ID = 'canvas-empty'

export function workflowPanelId(workflowId: string): string {
  return `workflow:${encodeURIComponent(workflowId)}`
}

export function workflowIdFromPanelId(panelId: string): string | null {
  if (!panelId.startsWith('workflow:')) return null
  return decodeURIComponent(panelId.slice('workflow:'.length))
}

export function nestedWorkflowPanelId(sessionId: string): string {
  return `nested-workflow:${encodeURIComponent(sessionId)}`
}

export function sessionIdFromNestedWorkflowPanelId(panelId: string): string | null {
  if (!panelId.startsWith('nested-workflow:')) return null
  return decodeURIComponent(panelId.slice('nested-workflow:'.length))
}

export function isCanvasPanelId(panelId: string): boolean {
  return workflowIdFromPanelId(panelId) !== null
    || sessionIdFromNestedWorkflowPanelId(panelId) !== null
}
