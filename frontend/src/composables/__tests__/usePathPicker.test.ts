import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/utils/nativeDialogs', () => ({
  isDesktop: vi.fn(),
  selectFile: vi.fn(),
  selectFiles: vi.fn(),
  selectFolder: vi.fn(),
}))

import {
  isDesktop,
  selectFile,
  selectFiles,
  selectFolder,
} from '@/utils/nativeDialogs'
import { usePathPicker, BrowserModeUnsupported } from '../usePathPicker'
import { useDatasetsStore } from '@/stores/datasets'

const mockedIsDesktop = vi.mocked(isDesktop)
const mockedSelectFile = vi.mocked(selectFile)
const mockedSelectFiles = vi.mocked(selectFiles)
const mockedSelectFolder = vi.mocked(selectFolder)

describe('usePathPicker.pickFile', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('calls selectFile in desktop mode and returns its result', async () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedSelectFile.mockResolvedValueOnce('/chosen.tif')

    const { pickFile } = usePathPicker()
    const result = await pickFile({ parameterName: 'input', fileTypes: ['*.tif'] })

    expect(result).toBe('/chosen.tif')
    expect(mockedSelectFile).toHaveBeenCalledWith('Select file for: input', ['*.tif'])
  })

  it('returns null when the native dialog returns null', async () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedSelectFile.mockResolvedValueOnce(null)

    const { pickFile } = usePathPicker()
    const result = await pickFile({ parameterName: 'input' })
    expect(result).toBeNull()
  })

  it('opens the Datasets panel picker in browser mode', async () => {
    mockedIsDesktop.mockReturnValue(false)
    const { pickFile } = usePathPicker()
    const store = useDatasetsStore()

    const promise = pickFile({ parameterName: 'input', fileTypes: ['*.tif'] })
    expect(store.picker).toMatchObject({
      parameterName: 'input',
      fileTypes: ['*.tif'],
    })
    expect(store.activationRequest).toBe(1)

    store.finishPicker('/server/path.tif')
    const result = await promise
    expect(result).toBe('/server/path.tif')
  })

  it('resolves null when the panel picker is cancelled', async () => {
    mockedIsDesktop.mockReturnValue(false)
    const { pickFile } = usePathPicker()
    const store = useDatasetsStore()

    const promise = pickFile({ parameterName: 'input' })
    store.finishPicker(null)
    expect(await promise).toBeNull()
  })

  it('re-entry cancels the previous invocation with null and takes over', async () => {
    mockedIsDesktop.mockReturnValue(false)
    const { pickFile } = usePathPicker()
    const store = useDatasetsStore()

    const first = pickFile({ parameterName: 'a' })
    const second = pickFile({ parameterName: 'b' })

    expect(await first).toBeNull()

    store.finishPicker('/p.tif')
    expect(await second).toBe('/p.tif')
  })
})

describe('usePathPicker.pickFiles', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('calls selectFiles in desktop mode and returns every selected path', async () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedSelectFiles.mockResolvedValueOnce(['/chosen/a.tif', '/chosen/b.tif'])

    const { pickFiles } = usePathPicker()
    const result = await pickFiles({ parameterName: 'files', fileTypes: ['*.tif'] })

    expect(result).toEqual(['/chosen/a.tif', '/chosen/b.tif'])
    expect(mockedSelectFiles).toHaveBeenCalledWith(
      'Select files for: files',
      ['*.tif'],
    )
  })

  it('does not open a native dialog in browser mode', async () => {
    mockedIsDesktop.mockReturnValue(false)

    const { pickFiles } = usePathPicker()

    await expect(pickFiles({ parameterName: 'files' })).resolves.toEqual([])
    expect(mockedSelectFiles).not.toHaveBeenCalled()
  })
})

describe('usePathPicker.pickFolder', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('calls selectFolder in desktop mode', async () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedSelectFolder.mockResolvedValueOnce('/chosen/folder')

    const { pickFolder } = usePathPicker()
    const result = await pickFolder({ parameterName: 'output_dir' })
    expect(result).toBe('/chosen/folder')
    expect(mockedSelectFolder).toHaveBeenCalledWith('Select folder for: output_dir')
  })

  it('throws BrowserModeUnsupported in browser mode', async () => {
    mockedIsDesktop.mockReturnValue(false)
    const { pickFolder } = usePathPicker()
    await expect(pickFolder({ parameterName: 'output_dir' })).rejects.toBeInstanceOf(
      BrowserModeUnsupported,
    )
  })
})

describe('usePathPicker.showDatasetsPanel', () => {
  it('requests Datasets panel activation without entering picker mode', () => {
    setActivePinia(createPinia())
    const store = useDatasetsStore()

    usePathPicker().showDatasetsPanel()

    expect(store.activationRequest).toBe(1)
    expect(store.picker).toBeNull()
  })
})
