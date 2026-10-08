import { expect, test, type Page, type Route } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'
import type { Dataset, DatasetFolder } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`

async function catalog(page: Page): Promise<Dataset[]> {
  const response = await page.request.get(`${API}/datasets`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return await response.json() as Dataset[]
}

async function folderCatalog(page: Page): Promise<DatasetFolder[]> {
  const response = await page.request.get(`${API}/datasets/folders`)
  expect(response.ok(), await response.text()).toBeTruthy()
  return await response.json() as DatasetFolder[]
}

function namedDataset(records: Dataset[], filename: string): Dataset {
  const matches = records.filter(record => record.original_filename === filename)
  expect(matches, `Exactly one stored dataset must own ${filename}`).toHaveLength(1)
  return matches[0]!
}

async function cleanOwnedDatasets(page: Page, filenames: string[], folderName?: string) {
  let failed = false
  let failure: unknown
  const actions = filenames.map(filename => async () => {
    for (const record of (await catalog(page)).filter(item => item.original_filename === filename)) {
      const response = await page.request.delete(`${API}/datasets/${record.id}`)
      expect([204, 404]).toContain(response.status())
    }
  })
  if (folderName) actions.push(async () => {
    const folders = await folderCatalog(page)
    for (const folder of folders.filter(item => item.name === folderName)) {
      const selection = { dataset_ids: [], folder_ids: [folder.id] }
      const preview = await page.request.post(`${API}/datasets/actions/delete-preview`, { data: selection })
      expect(preview.ok()).toBeTruthy()
      const deleted = await page.request.post(`${API}/datasets/actions/delete`, {
        data: { ...selection, expected_revision: (await preview.json()).revision },
      })
      expect(deleted.ok()).toBeTruthy()
      expect((await deleted.json()).errors).toEqual([])
    }
  })
  for (const action of actions) {
    try { await action() } catch (error) {
      if (!failed) { failed = true; failure = error }
    }
  }
  if (failed) throw failure
}

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
    const editActions = page.locator('.dataset-toolbar')
    await expect(editActions.getByRole('button')).toHaveCount(3)
    for (const name of ['Add folder', 'Rename', 'Delete']) {
      const button = editActions.getByRole('button', { name, exact: true })
      await expect(button).toHaveAttribute('title', name)
      await expect(button.locator('.p-button-label')).toHaveCount(0)
    }
    const selectionActions = page.locator('.dataset-selection-actions')
    const unselectAll = selectionActions.getByRole('button', { name: 'Unselect all' })
    await expect(unselectAll).toBeVisible()
    await expect(unselectAll.locator('.p-button-label')).toHaveText('Unselect all')
    await expect(unselectAll.locator('.p-button-icon')).toHaveCount(0)

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

    const renamedFileContent = page.locator('.p-tree-node-content').filter({
      has: page.locator('.dataset-node-label').filter({ hasText: new RegExp(`^${renamedName}$`) }),
    })
    const canvas = page.locator('.canvas-view')
    const canvasBox = await canvas.boundingBox()
    expect(canvasBox).not.toBeNull()
    const targetPosition = {
      x: Math.round(canvasBox!.width * 0.6),
      y: Math.round(canvasBox!.height * 0.4),
    }

    await renamedFileContent.dragTo(canvas, { targetPosition })

    const filesNode = page.locator('.vue-flow__node').filter({ hasText: 'Files' })
    await expect(filesNode).toHaveCount(1)
    const nodeBox = await filesNode.boundingBox()
    expect(nodeBox).not.toBeNull()
    expect(Math.abs(nodeBox!.x - (canvasBox!.x + targetPosition.x))).toBeLessThan(40)
    expect(Math.abs(nodeBox!.y - (canvasBox!.y + targetPosition.y))).toBeLessThan(40)

    await filesNode.click()
    const summary = page.getByTestId('dataset-selection-summary')
    const createFiles = page.getByTestId('dataset-create-files-node')
    const setFiles = page.getByTestId('dataset-set-files-node')
    await expect(setFiles).toBeVisible()
    const [summaryBox, createFilesBox, setFilesBox] = await Promise.all([
      summary.boundingBox(),
      createFiles.boundingBox(),
      setFiles.boundingBox(),
    ])
    expect(summaryBox).not.toBeNull()
    expect(createFilesBox).not.toBeNull()
    expect(setFilesBox).not.toBeNull()
    expect(summaryBox!.y + summaryBox!.height).toBeLessThan(createFilesBox!.y)
    expect(summaryBox!.y + summaryBox!.height).toBeLessThan(setFilesBox!.y)
    const actionGap = Math.max(
      setFilesBox!.x - (createFilesBox!.x + createFilesBox!.width),
      createFilesBox!.x - (setFilesBox!.x + setFilesBox!.width),
      setFilesBox!.y - (createFilesBox!.y + createFilesBox!.height),
      createFilesBox!.y - (setFilesBox!.y + setFilesBox!.height),
    )
    expect(actionGap).toBeGreaterThanOrEqual(4)
  })

  test('cancels a file dropped on the canvas while its upload is active', async ({ page }) => {
    const suffix = `${Date.now()}`
    const slowName = `slow-${suffix}.tif`
    const failedName = `retry-${suffix}.tif`
    const siblingName = `accepted-${suffix}.tif`
    const slowBytes = Buffer.from('slow upload')
    const failedBytes = Buffer.from('retry file bytes')
    const siblingBytes = Buffer.from('accepted sibling bytes')
    const uploadPattern = '**/api/v1/datasets/upload'
    let markUploadStarted!: () => void
    let releaseUpload!: () => void
    let markUploadSettled!: () => void
    let holdStarted = false
    const uploadStarted = new Promise<void>(resolve => { markUploadStarted = resolve })
    const uploadRelease = new Promise<void>(resolve => { releaseUpload = resolve })
    const uploadSettled = new Promise<void>(resolve => { markUploadSettled = resolve })
    const holdUpload = async (route: Route) => {
      holdStarted = true
      markUploadStarted()
      try {
        await uploadRelease
        await route.abort().catch(() => undefined)
      } finally { markUploadSettled() }
    }
    let controlledFailures = 0
    const failOneUpload = async (route: Route) => {
      const body = route.request().postDataBuffer()
      if (body?.includes(Buffer.from(failedName)) && controlledFailures === 0) {
        controlledFailures += 1
        // This is a controlled client per-file error, not a filesystem fault.
        await route.fulfill({ json: { uploaded: [], errors: [{
          filename: failedName, error: 'storage_error', detail: 'Controlled per-file upload failure',
        }] } })
      } else await route.continue()
    }
    let primaryOccurred = false
    let cleanupFailed = false
    let cleanupFailure: unknown
    try {
      await page.route(uploadPattern, holdUpload)
      await page.goto('/')
      await page.evaluate(name => {
        const transfer = new DataTransfer()
        transfer.items.add(new File(['slow upload'], name, { type: 'image/tiff' }))
        window.dispatchEvent(new DragEvent('drop', {
          bubbles: true, cancelable: true, dataTransfer: transfer,
        }))
      }, slowName)
      await uploadStarted
      await expect(page.getByTestId('upload-cancel-all')).toBeVisible()
      await page.getByTestId('upload-cancel-all').click()
      const slowRow = page.locator('.upload-message').filter({ hasText: slowName })
      await expect(slowRow).toHaveClass(/cancelled/)
      await expect(slowRow).toContainText(`${slowName} — Cancelled`)
      await expect(slowRow.getByRole('button', { name: 'Retry' })).toBeVisible()
      releaseUpload()
      await uploadSettled
      await page.unroute(uploadPattern, holdUpload)
      expect((await catalog(page)).filter(item => item.original_filename === slowName)).toEqual([])
      await slowRow.getByRole('button', { name: 'Retry' }).click()
      await expect(slowRow).toHaveClass(/success/)
      const first = namedDataset(await catalog(page), slowName)
      expect(readFileSync(first.path)).toEqual(slowBytes)

      await page.route(uploadPattern, failOneUpload)
      await page.locator('.datasets-panel input[type="file"]').setInputFiles([
        { name: failedName, mimeType: 'image/tiff', buffer: failedBytes },
        { name: siblingName, mimeType: 'image/tiff', buffer: siblingBytes },
      ])
      const failedRow = page.locator('.upload-message').filter({ hasText: failedName })
      const siblingRow = page.locator('.upload-message').filter({ hasText: siblingName })
      await expect(failedRow).toHaveClass(/error/)
      await expect(failedRow).toContainText('Controlled per-file upload failure')
      await expect(siblingRow).toHaveClass(/success/)
      const beforeRetry = await catalog(page)
      expect(beforeRetry.filter(item => item.original_filename === failedName)).toEqual([])
      const sibling = namedDataset(beforeRetry, siblingName)
      expect(readFileSync(sibling.path)).toEqual(siblingBytes)
      await failedRow.getByRole('button', { name: 'Retry' }).click()
      await expect(failedRow).toHaveClass(/success/)
      expect(controlledFailures).toBe(1)
      const accepted = namedDataset(await catalog(page), failedName)
      expect(readFileSync(accepted.path)).toEqual(failedBytes)
      expect(namedDataset(await catalog(page), siblingName)).toEqual(sibling)
      await page.unroute(uploadPattern, failOneUpload)
      await page.reload()
      await page.locator('.dv-tab').filter({ hasText: /^Datasets$/ }).click()
      for (const [record, bytes] of [[first, slowBytes], [accepted, failedBytes], [sibling, siblingBytes]] as const) {
        await expect(page.locator('.dataset-tree')).toContainText(record.display_name)
        expect(namedDataset(await catalog(page), record.original_filename)).toEqual(record)
        expect(readFileSync(record.path)).toEqual(bytes)
      }
    } catch (error) {
      primaryOccurred = true
      throw error
    } finally {
      releaseUpload()
      const actions = [
        async () => { if (holdStarted) await uploadSettled },
        async () => { await page.unroute(uploadPattern, holdUpload); await page.unroute(uploadPattern, failOneUpload) },
        async () => { await page.goto('about:blank') },
        async () => { await cleanOwnedDatasets(page, [slowName, failedName, siblingName]) },
      ]
      for (const action of actions) {
        try { await action() } catch (error) {
          if (primaryOccurred) console.error('Upload cleanup failed while preserving primary:', error)
          else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
        }
      }
    }
    if (cleanupFailed) throw cleanupFailure
  })

  test('moves checked items together and keeps hierarchical selection visible', async ({ page }, testInfo) => {
    const suffix = `${testInfo.project.name}-${testInfo.repeatEachIndex}`
    const firstName = `alpha-${suffix}.tif`
    const secondName = `zulu-${suffix}.tif`
    const folderName = `Batch ${suffix}`
    const unrelatedName = `preserved-${suffix}.txt`
    const unrelatedBytes = Buffer.from('unrelated managed file')
    let primaryOccurred = false
    let cleanupFailed = false
    let cleanupFailure: unknown
    try {
      let completedMoves = 0
      page.on('response', response => {
        if (
          response.request().method() === 'PATCH'
          && /\/api\/v1\/datasets\/[^/]+$/.test(new URL(response.url()).pathname)
        ) completedMoves += 1
      })

      await page.goto('/')
      await page.locator('.dv-tab').filter({ hasText: /^Datasets$/ }).click()
      await page.locator('.datasets-panel input[type="file"]').setInputFiles([
        { name: firstName, mimeType: 'image/tiff', buffer: Buffer.from('alpha') },
        { name: secondName, mimeType: 'image/tiff', buffer: Buffer.from('zulu') },
      ])
      await expect(page.locator('.upload-message.success')).toHaveCount(2)

      await page.getByRole('button', { name: 'Add folder' }).click()
      const folderDialog = page.getByRole('dialog', { name: 'Add folder' })
      await folderDialog.getByRole('textbox').fill(folderName)
      await folderDialog.getByRole('button', { name: 'Save' }).click()
      await expect(folderDialog).toBeHidden()

      const contentFor = (label: string) => page.locator('.p-tree-node-content').filter({
        has: page.locator('.dataset-node-label').filter({ hasText: new RegExp(`^${label}$`) }),
      })
      const folderContent = contentFor(folderName)
      await contentFor(firstName).dragTo(folderContent)
      await expect.poll(() => completedMoves).toBe(2)

      const folderItem = page.locator('.p-tree-node').filter({
        has: page.locator('.dataset-node-label').filter({ hasText: new RegExp(`^${folderName}$`) }),
      }).first()
      await folderItem.locator(':scope > .p-tree-node-content .p-tree-node-toggle-button').click()
      await expect(folderItem.getByText(firstName, { exact: true })).toBeVisible()
      await expect(folderItem.getByText(secondName, { exact: true })).toBeVisible()

      await contentFor(firstName).dragTo(contentFor(secondName))
      await expect(folderItem.getByText(firstName, { exact: true })).toBeVisible()
      await expect(folderItem.getByText(secondName, { exact: true })).toBeVisible()
      expect(completedMoves).toBe(2)

      await page.getByRole('button', { name: 'Unselect all' }).click()
      const folderCheckbox = page.getByTestId(`dataset-checkbox-${await folderItem.locator('.dataset-node-label').first().getAttribute('data-dataset-id')}`)
      const firstCheckbox = page.getByRole('checkbox', { name: `Select ${firstName}` })
      const secondCheckbox = page.getByRole('checkbox', { name: `Select ${secondName}` })
      await folderCheckbox.locator('input').click()
      await expect(folderCheckbox.locator('input')).toBeChecked()
      await expect(firstCheckbox).toBeChecked()
      await expect(secondCheckbox).toBeChecked()

      await firstCheckbox.click()
      await expect(folderCheckbox).toHaveAttribute('data-p-indeterminate', 'true')
      await expect(folderCheckbox.locator('input')).not.toBeChecked()
      await expect(firstCheckbox).not.toBeChecked()
      await expect(secondCheckbox).toBeChecked()

      // Clear the selected child first so this upload belongs to the root,
      // rather than inheriting the selected child's folder.
      await page.getByRole('button', { name: 'Unselect all' }).click()
      await page.locator('.datasets-panel input[type="file"]').setInputFiles({
        name: unrelatedName, mimeType: 'text/plain', buffer: unrelatedBytes,
      })
      await expect(page.locator('.upload-message.success').filter({ hasText: unrelatedName })).toBeVisible()
      await page.getByRole('button', { name: 'Unselect all' }).click()
      await folderCheckbox.locator('input').click()
      const before = await catalog(page)
      const foldersBefore = await folderCatalog(page)
      const selected = [namedDataset(before, firstName), namedDataset(before, secondName)]
      const unrelated = namedDataset(before, unrelatedName)
      expect(unrelated.folder_id).toBeNull()
      const folderId = await folderItem.locator('.dataset-node-label').first().getAttribute('data-dataset-id')
      expect(folderId).toBeTruthy()
      const snapshots = selected.map(item => ({ record: item, bytes: readFileSync(item.path) }))
      expect(readFileSync(unrelated.path)).toEqual(unrelatedBytes)
      let deletes = 0
      page.on('request', request => {
        if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/datasets/actions/delete') deletes += 1
      })
      const openPreview = async () => {
        const preview = page.waitForResponse(response => response.request().method() === 'POST'
          && new URL(response.url()).pathname === '/api/v1/datasets/actions/delete-preview')
        await page.locator('.dataset-toolbar').getByRole('button', { name: 'Delete', exact: true }).click()
        const response = await preview
        expect(response.ok(), await response.text()).toBeTruthy()
        const body = await response.json()
        expect(body).toMatchObject({ dataset_count: 2, folder_count: 1, revision: expect.any(Number) })
        return body
      }
      const dialog = page.getByRole('dialog', { name: 'Delete selected datasets' })
      await openPreview()
      await expect(dialog).toContainText('Delete 2 file(s) and 1 folder(s)?')
      await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(deletes).toBe(0)
      expect(await catalog(page)).toEqual(before)
      expect(await folderCatalog(page)).toEqual(foldersBefore)
      for (const { record, bytes } of snapshots) expect(readFileSync(record.path)).toEqual(bytes)

      const stale = await openPreview()
      const renamed = await page.request.patch(`${API}/datasets/${unrelated.id}`, {
        data: { display_name: `Preserved after catalog change ${suffix}` },
      })
      expect(renamed.ok(), await renamed.text()).toBeTruthy()
      const preserved = await renamed.json() as Dataset
      const afterRename = await catalog(page)
      const staleResponse = page.waitForResponse(response => response.request().method() === 'POST'
        && new URL(response.url()).pathname === '/api/v1/datasets/actions/delete')
      await dialog.getByRole('button', { name: 'Delete', exact: true }).click()
      const refused = await staleResponse
      expect(refused.status(), await refused.text()).toBe(409)
      expect(await refused.json()).toMatchObject({ error: 'catalog_conflict', detail: 'dataset catalog changed', field: null })
      expect(refused.request().postDataJSON().expected_revision).toBe(stale.revision)
      await expect(dialog.locator('.action-error')).toContainText('dataset catalog changed')
      expect(await catalog(page)).toEqual(afterRename)
      expect(await folderCatalog(page)).toEqual(foldersBefore)
      for (const { record, bytes } of snapshots) expect(readFileSync(record.path)).toEqual(bytes)
      expect(readFileSync(preserved.path)).toEqual(unrelatedBytes)
      await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
      await expect(dialog).toBeHidden()
      const fresh = await openPreview()
      expect(fresh.revision).toBeGreaterThan(stale.revision)
      const acceptedResponse = page.waitForResponse(response => response.request().method() === 'POST'
        && new URL(response.url()).pathname === '/api/v1/datasets/actions/delete')
      await dialog.getByRole('button', { name: 'Delete', exact: true }).click()
      const accepted = await acceptedResponse
      expect(accepted.ok(), await accepted.text()).toBeTruthy()
      const result = await accepted.json()
      expect(result.deleted_dataset_ids.sort()).toEqual(selected.map(item => item.id).sort())
      expect(result.deleted_folder_ids).toEqual([folderId])
      expect(result.errors).toEqual([])
      expect(accepted.request().postDataJSON().expected_revision).toBe(fresh.revision)
      expect(deletes).toBe(2)
      await expect(dialog).toBeHidden()
      for (const item of selected) expect(existsSync(item.path)).toBe(false)
      const remaining = afterRename.filter(item => !selected.some(deleted => item.id === deleted.id))
      expect(await catalog(page)).toEqual(remaining)
      const remainingFolders = foldersBefore.filter(item => item.id !== folderId)
      expect(await folderCatalog(page)).toEqual(remainingFolders)
      expect(namedDataset(remaining, unrelatedName)).toEqual(preserved)
      expect(readFileSync(preserved.path)).toEqual(unrelatedBytes)
      await page.reload()
      await page.locator('.dv-tab').filter({ hasText: /^Datasets$/ }).click()
      await expect(page.locator('.dataset-tree')).not.toContainText(folderName)
      await expect(page.locator('.dataset-tree')).not.toContainText(firstName)
      await expect(page.locator('.dataset-tree')).not.toContainText(secondName)
      await expect(page.locator('.dataset-tree')).toContainText(preserved.display_name)
      expect(await catalog(page)).toEqual(remaining)
      expect(await folderCatalog(page)).toEqual(remainingFolders)
      expect(readFileSync(preserved.path)).toEqual(unrelatedBytes)
    } catch (error) {
      primaryOccurred = true
      throw error
    } finally {
      for (const action of [
        async () => { await page.goto('about:blank') },
        async () => { await cleanOwnedDatasets(page, [firstName, secondName, unrelatedName], folderName) },
      ]) {
        try { await action() } catch (error) {
          if (primaryOccurred) console.error('Dataset cleanup failed while preserving primary:', error)
          else if (!cleanupFailed) { cleanupFailed = true; cleanupFailure = error }
        }
      }
    }
    if (cleanupFailed) throw cleanupFailure
  })
})
