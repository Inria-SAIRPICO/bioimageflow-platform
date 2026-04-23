import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  isDesktop,
  selectFile,
  selectFiles,
  selectFolder,
  saveFile,
  setTitle,
  updateWindowTitle,
  revealPath,
} from '../nativeDialogs'

function mockPywebviewApi() {
  return {
    select_file: vi.fn(),
    select_files: vi.fn(),
    select_folder: vi.fn(),
    save_file: vi.fn(),
    set_title: vi.fn(),
    reveal_path: vi.fn(),
  }
}

describe('isDesktop', () => {
  afterEach(() => {
    delete window.pywebview
  })

  it('returns false when pywebview is not present', () => {
    expect(isDesktop()).toBe(false)
  })

  it('returns true when pywebview.api is present', () => {
    window.pywebview = { api: mockPywebviewApi() as any }
    expect(isDesktop()).toBe(true)
  })
})

describe('selectFile', () => {
  afterEach(() => {
    delete window.pywebview
    vi.restoreAllMocks()
  })

  it('calls pywebview api when available', async () => {
    const api = mockPywebviewApi()
    api.select_file.mockResolvedValue('/chosen/file.tif')
    window.pywebview = { api: api as any }

    const result = await selectFile('Pick', ['*.tif'])

    expect(result).toBe('/chosen/file.tif')
    expect(api.select_file).toHaveBeenCalledWith('Pick', ['*.tif'])
  })

  it('falls back to prompt in browser mode', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('/typed/path')

    const result = await selectFile('Pick')

    expect(result).toBe('/typed/path')
  })

  it('returns null when prompt is cancelled', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue(null)

    const result = await selectFile()

    expect(result).toBeNull()
  })
})

describe('selectFiles', () => {
  afterEach(() => {
    delete window.pywebview
  })

  it('calls pywebview api when available', async () => {
    const api = mockPywebviewApi()
    api.select_files.mockResolvedValue(['/a.tif', '/b.tif'])
    window.pywebview = { api: api as any }

    const result = await selectFiles('Pick', ['*.tif'])

    expect(result).toEqual(['/a.tif', '/b.tif'])
    expect(api.select_files).toHaveBeenCalledWith('Pick', ['*.tif'])
  })

  it('returns empty array in browser mode', async () => {
    const result = await selectFiles()

    expect(result).toEqual([])
  })
})

describe('selectFolder', () => {
  afterEach(() => {
    delete window.pywebview
    vi.restoreAllMocks()
  })

  it('calls pywebview api when available', async () => {
    const api = mockPywebviewApi()
    api.select_folder.mockResolvedValue('/chosen/folder')
    window.pywebview = { api: api as any }

    const result = await selectFolder('Pick folder')

    expect(result).toBe('/chosen/folder')
    expect(api.select_folder).toHaveBeenCalledWith('Pick folder')
  })

  it('falls back to prompt in browser mode', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('/typed/folder')

    const result = await selectFolder()

    expect(result).toBe('/typed/folder')
  })
})

describe('saveFile', () => {
  afterEach(() => {
    delete window.pywebview
    vi.restoreAllMocks()
  })

  it('calls pywebview api when available', async () => {
    const api = mockPywebviewApi()
    api.save_file.mockResolvedValue('/save/path.tif')
    window.pywebview = { api: api as any }

    const result = await saveFile('Save', ['*.tif'], 'output.tif')

    expect(result).toBe('/save/path.tif')
    expect(api.save_file).toHaveBeenCalledWith('Save', ['*.tif'], 'output.tif')
  })

  it('falls back to prompt in browser mode', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('/typed/save')

    const result = await saveFile('Save', [], 'default.tif')

    expect(result).toBe('/typed/save')
  })

  it('returns null when prompt is cancelled', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue(null)

    const result = await saveFile()

    expect(result).toBeNull()
  })
})

describe('setTitle', () => {
  afterEach(() => {
    delete window.pywebview
  })

  it('calls pywebview api when available', async () => {
    const api = mockPywebviewApi()
    api.set_title.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await setTitle('New Title')

    expect(api.set_title).toHaveBeenCalledWith('New Title')
  })

  it('does not throw in browser mode', async () => {
    await expect(setTitle('Title')).resolves.toBeUndefined()
  })
})

describe('updateWindowTitle', () => {
  afterEach(() => {
    delete window.pywebview
  })

  it('sets title to "BioImageFlow" when no workflow name', async () => {
    const api = mockPywebviewApi()
    api.set_title.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await updateWindowTitle()

    expect(api.set_title).toHaveBeenCalledWith('BioImageFlow')
  })

  it('sets title to "BioImageFlow" when workflow name is null', async () => {
    const api = mockPywebviewApi()
    api.set_title.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await updateWindowTitle(null)

    expect(api.set_title).toHaveBeenCalledWith('BioImageFlow')
  })

  it('includes workflow name in title', async () => {
    const api = mockPywebviewApi()
    api.set_title.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await updateWindowTitle('My Workflow')

    expect(api.set_title).toHaveBeenCalledWith('BioImageFlow \u2014 My Workflow')
  })

  it('appends * when there are unsaved changes', async () => {
    const api = mockPywebviewApi()
    api.set_title.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await updateWindowTitle('My Workflow', true)

    expect(api.set_title).toHaveBeenCalledWith('BioImageFlow \u2014 My Workflow *')
  })

  it('does not append * when hasUnsavedChanges is false', async () => {
    const api = mockPywebviewApi()
    api.set_title.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await updateWindowTitle('My Workflow', false)

    expect(api.set_title).toHaveBeenCalledWith('BioImageFlow \u2014 My Workflow')
  })

  it('ignores unsaved changes flag when no workflow name', async () => {
    const api = mockPywebviewApi()
    api.set_title.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await updateWindowTitle(undefined, true)

    expect(api.set_title).toHaveBeenCalledWith('BioImageFlow')
  })

  it('silently skipped in browser mode (no pywebview)', async () => {
    await expect(updateWindowTitle('My Workflow', true)).resolves.toBeUndefined()
  })
})

describe('revealPath', () => {
  afterEach(() => {
    delete window.pywebview
  })

  it('calls pywebview api when available', async () => {
    const api = mockPywebviewApi()
    api.reveal_path.mockResolvedValue(undefined)
    window.pywebview = { api: api as any }

    await revealPath('/some/path')

    expect(api.reveal_path).toHaveBeenCalledWith('/some/path')
  })

  it('does not throw in browser mode', async () => {
    await expect(revealPath('/some/path')).resolves.toBeUndefined()
  })
})
