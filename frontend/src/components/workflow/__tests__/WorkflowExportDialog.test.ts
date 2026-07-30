import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'
import PrimeVue from 'primevue/config'
import WorkflowExportDialog from '../WorkflowExportDialog.vue'
import { useWorkflowStore } from '@/stores/workflow'
import { revealPath, selectFolder } from '@/utils/nativeDialogs'

const toastAdd = vi.hoisted(() => vi.fn())

vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: toastAdd }),
}))

vi.mock('@/utils/nativeDialogs', () => ({
  selectFolder: vi.fn(),
  revealPath: vi.fn(),
}))

function mountDialog(options: {
  desktop?: boolean
  workflowExportsDisabled?: boolean
  prepareWorkflowExport?: (name: string) => Promise<string | null>
} = {}) {
  return mount(WorkflowExportDialog, {
    props: {
      visible: true,
      workflowName: 'folder/wf',
      workflowDisplayName: 'Cell segmentation',
      desktop: options.desktop ?? false,
      workflowExportsDisabled: options.workflowExportsDisabled ?? false,
      prepareWorkflowExport: options.prepareWorkflowExport,
    },
    global: {
      plugins: [PrimeVue],
      stubs: {
        Dialog: {
          props: ['visible', 'header'],
          emits: ['update:visible'],
          template: '<section v-if="visible"><h2>{{ header }}</h2><slot /><slot name="footer" /></section>',
        },
      },
    },
  })
}

function conflictError(): AxiosError {
  return new AxiosError(
    'Destination exists',
    '409',
    undefined,
    undefined,
    {
      status: 409,
      statusText: 'Conflict',
      headers: {},
      config: {} as never,
      data: {
        detail: {
          error: 'export_destination_exists',
          detail: 'Destination already exists',
        },
      },
    },
  )
}

describe('WorkflowExportDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    toastAdd.mockReset()
    vi.mocked(selectFolder).mockReset()
    vi.mocked(revealPath).mockReset()
  })

  it('explains the distinction between mixed latest outputs and one successful run', () => {
    const wrapper = mountDialog()

    expect(wrapper.text()).toContain('Workflow only')
    expect(wrapper.text()).toContain('Latest results')
    expect(wrapper.text()).toContain('may come from different workflow runs')
    expect(wrapper.text()).toContain('one latest successful run')
    expect(wrapper.find('[data-testid="export-latest-results-folder"]').exists()).toBe(false)
  })

  it('downloads latest results without crossing the workflow save barrier', async () => {
    const prepare = vi.fn().mockResolvedValue('folder/wf')
    const store = useWorkflowStore()
    const exportLatestResults = vi
      .spyOn(store, 'exportLatestResults')
      .mockResolvedValue(undefined)
    const wrapper = mountDialog({ prepareWorkflowExport: prepare })

    await wrapper.get('[data-testid="export-latest-results"]').trigger('click')
    await flushPromises()

    expect(prepare).not.toHaveBeenCalled()
    expect(exportLatestResults).toHaveBeenCalledWith(
      'folder/wf',
      expect.any(AbortSignal),
    )
    expect(wrapper.emitted('update:visible')).toContainEqual([false])
  })

  it('prepares workflow-containing exports before downloading them', async () => {
    const prepare = vi.fn().mockResolvedValue('folder/wf')
    const store = useWorkflowStore()
    const exportWorkflow = vi.spyOn(store, 'exportWorkflow').mockResolvedValue(undefined)
    const exportWorkflowRunBundle = vi
      .spyOn(store, 'exportWorkflowRunBundle')
      .mockResolvedValue(undefined)
    const wrapper = mountDialog({ prepareWorkflowExport: prepare })

    await wrapper.get('[data-testid="export-workflow-only"]').trigger('click')
    await flushPromises()

    expect(prepare).toHaveBeenCalledWith('folder/wf')
    expect(exportWorkflow).toHaveBeenCalledWith('folder/wf', expect.any(AbortSignal))

    await wrapper.setProps({ visible: true })
    await wrapper.get('[data-testid="export-workflow-with-results"]').trigger('click')
    await flushPromises()

    expect(exportWorkflowRunBundle).toHaveBeenCalledWith(
      'folder/wf',
      expect.any(AbortSignal),
    )
  })

  it('keeps results-only exports available while workflow mutation is locked', () => {
    const wrapper = mountDialog({ workflowExportsDisabled: true })

    expect(wrapper.get('[data-testid="export-workflow-only"]').attributes('disabled')).toBeDefined()
    expect(
      wrapper.get('[data-testid="export-workflow-with-results"]').attributes('disabled'),
    ).toBeDefined()
    expect(wrapper.get('[data-testid="export-latest-results"]').attributes('disabled'))
      .toBeUndefined()
    expect(wrapper.text()).toContain('Results-only exports remain available')
  })

  it('uses the selected folder as a parent and retries replacement only after a conflict', async () => {
    vi.mocked(selectFolder).mockResolvedValue('/exports')
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const store = useWorkflowStore()
    const folderExport = vi
      .spyOn(store, 'exportLatestResultsToFolder')
      .mockRejectedValueOnce(conflictError())
      .mockResolvedValueOnce({
        destination: '/exports/wf-latest-results',
        exported_items: 3,
      })
    const wrapper = mountDialog({ desktop: true })

    await wrapper.get('[data-testid="export-latest-results-folder"]').trigger('click')
    await flushPromises()

    expect(selectFolder).toHaveBeenCalledWith('Choose where to export latest results')
    expect(folderExport).toHaveBeenNthCalledWith(
      1,
      'folder/wf',
      '/exports',
      false,
      expect.any(AbortSignal),
    )
    expect(window.confirm).toHaveBeenCalledOnce()
    expect(folderExport).toHaveBeenNthCalledWith(
      2,
      'folder/wf',
      '/exports',
      true,
      expect.any(AbortSignal),
    )
    expect(wrapper.get('[data-testid="workflow-export-folder-success"]').text())
      .toContain('/exports/wf-latest-results')
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({
      summary: 'Latest results exported',
    }))

    await wrapper.get('[data-testid="workflow-export-reveal"]').trigger('click')
    expect(revealPath).toHaveBeenCalledWith('/exports/wf-latest-results')
  })

  it('treats folder picker dismissal as cancellation without calling the backend', async () => {
    vi.mocked(selectFolder).mockResolvedValue(null)
    const store = useWorkflowStore()
    const folderExport = vi.spyOn(store, 'exportLatestResultsToFolder')
    const wrapper = mountDialog({ desktop: true })

    await wrapper.get('[data-testid="export-latest-results-folder"]').trigger('click')
    await flushPromises()

    expect(folderExport).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="workflow-export-error"]').exists()).toBe(false)
  })

  it('does not offer replacement for non-destination conflicts', async () => {
    vi.mocked(selectFolder).mockResolvedValue('/exports')
    const confirm = vi.spyOn(window, 'confirm')
    const store = useWorkflowStore()
    vi.spyOn(store, 'exportLatestResultsToFolder').mockRejectedValueOnce(new AxiosError(
      'No results',
      '409',
      undefined,
      undefined,
      {
        status: 409,
        statusText: 'Conflict',
        headers: {},
        config: {} as never,
        data: {
          detail: {
            error: 'results_not_available',
            detail: 'Run at least one node before exporting latest results.',
          },
        },
      },
    ))
    const wrapper = mountDialog({ desktop: true })

    await wrapper.get('[data-testid="export-latest-results-folder"]').trigger('click')
    await flushPromises()

    expect(confirm).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="workflow-export-error"]').text())
      .toContain('Run at least one node')
  })

  it('shows the backend empty-run detail and cancels an in-flight request', async () => {
    const store = useWorkflowStore()
    let signal: AbortSignal | undefined
    vi.spyOn(store, 'exportWorkflowRunBundle').mockImplementation(async (_name, requestSignal) => {
      signal = requestSignal
      throw new AxiosError(
        'No run',
        '404',
        undefined,
        undefined,
        {
          status: 409,
          statusText: 'Conflict',
          headers: {},
          config: {} as never,
          data: new Blob([JSON.stringify({
            detail: {
              error: 'results_not_available',
              detail: 'Run the complete workflow successfully before exporting a bundle.',
            },
          })], { type: 'application/json' }),
        },
      )
    })
    const wrapper = mountDialog()

    await wrapper.get('[data-testid="export-workflow-with-results"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="workflow-export-error"]').text())
      .toContain('Run the complete workflow successfully')

    vi.spyOn(store, 'exportLatestResults').mockImplementation(async (_name, requestSignal) => {
      signal = requestSignal
      await new Promise(() => {})
    })
    await wrapper.get('[data-testid="export-latest-results"]').trigger('click')
    expect(wrapper.get('[data-testid="workflow-export-progress"]').text())
      .toContain('latest-results archive')
    await wrapper.get('[data-testid="workflow-export-cancel"]').trigger('click')

    expect(signal?.aborted).toBe(true)
    expect(wrapper.emitted('update:visible')).toContainEqual([false])
  })
})
