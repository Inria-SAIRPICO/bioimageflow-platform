import { expect, test } from '@playwright/test'

test.describe('Datasets panel', () => {
  test('uploads, organizes, renames, and snapshots managed files', async ({ page }, testInfo) => {
    const suffix = `${testInfo.project.name}-${testInfo.repeatEachIndex}`
    const workflowName = `Dataset test ${suffix}`
    const fileName = `dataset-${suffix}.tif`
    const renamedName = `Control image ${suffix}`
    const folderName = `Experiment ${suffix}`

    await page.goto('/')
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'New', exact: true }).click()
    await page.getByTestId('workflow-display-name-input').fill(workflowName)
    await page.getByTestId('workflow-dialog-submit').click()
    await expect(page.getByTestId('workflow-title')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: /^Datasets$/ }).click()

    await expect(page.getByRole('button', { name: 'Upload files' })).toBeVisible()
    await expect(page.getByPlaceholder('Search files and folders')).toBeVisible()
    await expect(page.getByText('Datasets root', { exact: true })).toHaveCount(0)
    await expect(page.locator('.dataset-tree')).toHaveCSS('padding', '0px')

    await page.locator('.datasets-panel input[type="file"]').setInputFiles({
      name: fileName,
      mimeType: 'image/tiff',
      buffer: Buffer.from('fake-tiff'),
    })
    await expect(page.locator('.upload-message.success')).toContainText(fileName)
    await expect(page.locator('.dataset-tree')).toContainText(fileName)
    await expect(page.locator('.dataset-tree .p-tree-node-content').first()).toHaveCSS(
      'padding',
      '1.6px 2.4px',
    )
    await page.getByTestId('upload-clear-completed').click()
    await expect(page.locator('.upload-message')).toHaveCount(0)

    const fileRow = page.locator('.dataset-node-label').filter({ hasText: new RegExp(`^dataset-${suffix}\\.tif$`) })
    const datasetId = await fileRow.getAttribute('data-dataset-id')
    expect(datasetId).toBeTruthy()
    await expect(page.getByTestId('dataset-selection-summary')).toHaveAttribute('data-selected-ids', datasetId!)
    await expect(page.getByTestId('dataset-selection-summary')).toHaveText('1 item selected')
    await page.getByRole('button', { name: 'Rename' }).click()
    const renameDialog = page.getByRole('dialog', { name: 'Rename' })
    await renameDialog.getByRole('textbox').fill(renamedName)
    await renameDialog.getByRole('button', { name: 'Save' }).click()
    await expect(renameDialog).toBeHidden()
    await expect(page.locator('.dataset-tree')).toContainText(renamedName)

    await page.getByRole('button', { name: 'Add folder' }).click()
    const folderDialog = page.getByRole('dialog', { name: 'Add folder' })
    await folderDialog.getByRole('textbox').fill(folderName)
    await folderDialog.getByRole('button', { name: 'Save' }).click()
    await expect(folderDialog).toBeHidden()
    await expect(page.locator('.dataset-tree')).toContainText(folderName)

    await page.getByRole('button', { name: 'Create Files node', exact: true }).click()
    await expect(page.locator('.vue-flow__node').filter({ hasText: 'Files' })).toHaveCount(1)
  })

  test('cancels a file dropped on the canvas while its upload is active', async ({ page }) => {
    let markUploadStarted!: () => void
    let releaseUpload!: () => void
    const uploadStarted = new Promise<void>(resolve => { markUploadStarted = resolve })
    const uploadRelease = new Promise<void>(resolve => { releaseUpload = resolve })
    await page.route('**/api/v1/datasets/upload', async route => {
      markUploadStarted()
      await uploadRelease
      await route.abort().catch(() => undefined)
    })
    await page.goto('/')

    await page.evaluate(() => {
      const transfer = new DataTransfer()
      transfer.items.add(new File(['slow upload'], 'slow.tif', { type: 'image/tiff' }))
      window.dispatchEvent(new DragEvent('drop', {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }))
    })
    await uploadStarted
    await expect(page.getByTestId('upload-cancel-all')).toBeVisible()

    await page.getByTestId('upload-cancel-all').click()
    await expect(page.locator('.upload-message.cancelled')).toContainText('slow.tif — Cancelled')
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
    releaseUpload()
  })
})
