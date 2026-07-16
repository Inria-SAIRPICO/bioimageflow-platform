export const CANVAS_LOADING_PANEL_ID = 'canvas-loading'
export const CANVAS_EMPTY_PANEL_ID = 'canvas-empty'

export function workflowPanelId(workflowId: string): string {
  return `workflow:${encodeURIComponent(workflowId)}`
}

export function workflowIdFromPanelId(panelId: string): string | null {
  if (!panelId.startsWith('workflow:')) return null
  return decodeURIComponent(panelId.slice('workflow:'.length))
}

export function subWorkflowPanelId(sessionId: string): string {
  return `sub-workflow:${encodeURIComponent(sessionId)}`
}

export function sessionIdFromSubWorkflowPanelId(panelId: string): string | null {
  if (!panelId.startsWith('sub-workflow:')) return null
  return decodeURIComponent(panelId.slice('sub-workflow:'.length))
}

export function isCanvasPanelId(panelId: string): boolean {
  return workflowIdFromPanelId(panelId) !== null
    || sessionIdFromSubWorkflowPanelId(panelId) !== null
}
