import { generateNodeId, generateNodeName } from './nodeIdGenerator'

export interface ClipboardNode {
  id: string
  name: string
  tool_name: string
  position: [number, number]
  parameters: Record<string, unknown>
  tool_package?: string
  tool_package_version?: string
  missing?: boolean
}

export interface ClipboardEdge {
  id: string
  source_node: string
  target_node: string
  source_output: string
  target_input: string
}

export interface ClipboardData {
  nodes: ClipboardNode[]
  edges: ClipboardEdge[]
}

const PASTE_OFFSET = 50

/**
 * Serialize only the selected nodes and their internal edges.
 */
export function serializeSelection(
  nodes: ClipboardNode[],
  edges: ClipboardEdge[],
  selectedIds: Set<string>,
): ClipboardData {
  const selectedNodes = nodes.filter(n => selectedIds.has(n.id))
  const selectedEdges = edges.filter(
    e => selectedIds.has(e.source_node) && selectedIds.has(e.target_node),
  )
  return {
    nodes: JSON.parse(JSON.stringify(selectedNodes)),
    edges: JSON.parse(JSON.stringify(selectedEdges)),
  }
}

/**
 * Deserialize clipboard data with new unique IDs, remapped edges, and offset positions.
 */
export function deserializeSelection(
  clipboard: ClipboardData,
  existingIds: string[],
  existingNames: string[],
): ClipboardData {
  const idMap = new Map<string, string>()
  const allIds = [...existingIds]
  const allNames = [...existingNames]

  // Generate new IDs and names for each node
  const newNodes = clipboard.nodes.map(node => {
    const newId = generateNodeId(node.tool_name, allIds)
    allIds.push(newId)
    idMap.set(node.id, newId)

    const newName = generateNodeName(node.tool_name, allNames, node.name)
    allNames.push(newName)

    return {
      ...node,
      id: newId,
      name: newName,
      position: [
        node.position[0] + PASTE_OFFSET,
        node.position[1] + PASTE_OFFSET,
      ] as [number, number],
      parameters: JSON.parse(JSON.stringify(node.parameters)),
    }
  })

  // Remap edges to new node IDs and generate new edge IDs
  let edgeCounter = 0
  const newEdges = clipboard.edges.map(edge => {
    edgeCounter++
    return {
      ...edge,
      id: `pasted_edge_${Date.now()}_${edgeCounter}`,
      source_node: idMap.get(edge.source_node) ?? edge.source_node,
      target_node: idMap.get(edge.target_node) ?? edge.target_node,
    }
  })

  return { nodes: newNodes, edges: newEdges }
}
