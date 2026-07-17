import { expect, test } from '@playwright/test'

test.describe('Datasets panel', () => {
  test('uploads, organizes, renames, and snapshots managed files', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'New', exact: true }).click()
    await page.getByTestId('workflow-display-name-input').fill(`Dataset test ${Date.now()}`)
    await page.getByTestId('workflow-dialog-submit').click()
    await expect(page.getByTestId('workflow-title')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: /^Datasets$/ }).click()

    await expect(page.getByRole('button', { name: 'Upload files' })).toBeVisible()
    await expect(page.getByPlaceholder('Search files and folders')).toBeVisible()
    await expect(page.getByText('Datasets root', { exact: true })).toHaveCount(0)

    await page.locator('.datasets-panel input[type="file"]').setInputFiles({
      name: 'cells.tif',
      mimeType: 'image/tiff',
      buffer: Buffer.from('fake-tiff'),
    })
    await expect(page.locator('.upload-message.success')).toContainText('cells.tif')
    await expect(page.locator('.dataset-tree')).toContainText('cells.tif')

    const fileRow = page.locator('.dataset-node-label').filter({ hasText: /^cells\.tif$/ })
    const datasetId = await fileRow.getAttribute('data-dataset-id')
    expect(datasetId).toBeTruthy()
    await expect(page.getByTestId('dataset-selection-summary')).toHaveAttribute('data-selected-ids', datasetId!)
    await expect(page.getByTestId('dataset-selection-summary')).toHaveText('1 item selected')
    await page.getByRole('button', { name: 'Rename' }).click()
    const renameDialog = page.getByRole('dialog', { name: 'Rename' })
    await renameDialog.getByRole('textbox').fill('Control image')
    await renameDialog.getByRole('button', { name: 'Save' }).click()
    await expect(page.locator('.dataset-tree')).toContainText('Control image')

    await page.getByRole('button', { name: 'Add folder' }).click()
    const folderDialog = page.getByRole('dialog', { name: 'Add folder' })
    await folderDialog.getByRole('textbox').fill('Experiment A')
    await folderDialog.getByRole('button', { name: 'Save' }).click()
    await expect(page.locator('.dataset-tree')).toContainText('Experiment A')

    await page.getByRole('button', { name: 'Create Files node', exact: true }).click()
    await expect(page.locator('.vue-flow__node').filter({ hasText: 'Files' })).toHaveCount(1)
  })
})
