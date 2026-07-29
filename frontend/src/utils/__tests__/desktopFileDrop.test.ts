import { afterEach, describe, expect, it, vi } from 'vitest'
import { readDesktopFileDrop } from '../desktopFileDrop'

function desktopBridge() {
  window.pywebview = {
    api: {
      resolve_dropped_paths: vi.fn(),
    } as any,
  }
}

function transfer(files: File[], types: string[] = ['Files']): DataTransfer {
  return {
    files,
    items: [],
    types,
  } as unknown as DataTransfer
}

describe('readDesktopFileDrop', () => {
  afterEach(() => {
    delete window.pywebview
  })

  it('ignores operating-system file payloads in browser mode', () => {
    const file = new File([], 'cells.tif')
    ;(file as File & { path?: string }).path = '/data/cells.tif'

    expect(readDesktopFileDrop(transfer([file]))).toBeNull()
  })

  it('returns local file and folder paths in desktop mode', () => {
    desktopBridge()
    const file = new File([], 'cells.tif')
    ;(file as File & { path?: string }).path = '/data/cells.tif'
    const folder = new File([], 'images')
    ;(folder as File & { path?: string }).path = '/data/images'

    expect(readDesktopFileDrop(transfer([file, folder]))).toEqual({
      paths: ['/data/cells.tif', '/data/images'],
      unresolvedNames: [],
    })
  })

  it('reports dropped items whose native path is unavailable', () => {
    desktopBridge()

    expect(readDesktopFileDrop(transfer([new File([], 'cells.tif')]))).toEqual({
      paths: [],
      unresolvedNames: ['cells.tif'],
    })
  })

  it('ignores non-file drag payloads', () => {
    desktopBridge()

    expect(readDesktopFileDrop(transfer([], ['application/bioimageflow-tool']))).toBeNull()
  })
})
