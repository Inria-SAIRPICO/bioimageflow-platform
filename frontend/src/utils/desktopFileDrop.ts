import { isDesktop } from '@/utils/nativeDialogs'

type LocalPathFile = File & { path?: string }

export interface DesktopFileDrop {
  paths: string[]
  unresolvedNames: string[]
}

function filePayload(transfer: DataTransfer): File[] {
  const files = Array.from(transfer.files ?? [])
  if (files.length > 0) return files
  return Array.from(transfer.items ?? []).flatMap(item => {
    if (item.kind !== 'file') return []
    const file = item.getAsFile()
    return file ? [file] : []
  })
}

/** Read native local paths from a desktop operating-system file drop. */
export function readDesktopFileDrop(
  transfer: DataTransfer | null | undefined,
): DesktopFileDrop | null {
  if (!isDesktop() || !transfer) return null
  const hasFileType = transfer.types.includes('Files')
  const files = filePayload(transfer)
  if (!hasFileType && files.length === 0) return null

  const paths: string[] = []
  const unresolvedNames: string[] = []
  for (const file of files) {
    const path = (file as LocalPathFile).path
    if (typeof path === 'string' && path.length > 0) {
      paths.push(path)
    } else {
      unresolvedNames.push(file.name || 'unnamed item')
    }
  }
  return { paths, unresolvedNames }
}
