import { expect, test } from '@playwright/test'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const SELECTED = 'platform-tool-selected'
const OTHER = 'platform-tool-other'

type Identity = {
  name: string; generation_id: string; recipe_hash: string; state: string
  path: string; worker_pids: number[]
}
type Evidence = {
  inventory: Identity[]; recreate_calls: string[]
  retired_worker_pids: number[]; retired_workers_alive: number[]
  unmanaged_sha256: string
}

test('Manage Tools displays a selected force failure, retries, and retains state after reopen', async ({ page }) => {
  // Client projection only: genuine declared fixture metadata, controlled transport,
  // and no prepare/provision. Actual replacement and worker failure have separate proofs.
  const requests: string[] = []
  const recreatePath = `/api/v1/tools/environments/${SELECTED}/recreate`
  const failure = 'Controlled selected environment setup failure'
  await page.route(`**${recreatePath}`, async route => {
    expect(route.request().method()).toBe('POST')
    requests.push(new URL(route.request().url()).pathname)
    await route.fulfill({
      status: requests.length === 1 ? 500 : 200,
      contentType: 'application/json',
      body: JSON.stringify(requests.length === 1
        ? { error: 'environment_setup_failed', detail: failure }
        : { environment: SELECTED, status: 'running' }),
    })
  })
  await page.goto('/')
  await expect(page.locator('#bioimageflow-app')).toBeVisible()
  await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
  await page.getByTestId('manage-tools-btn').click()
  const dialog = page.getByTestId('manage-tools-dialog')
  await expect(dialog).toBeVisible()
  const action = dialog.getByTestId('tool-env-recreate-LifecycleSelected')
  const otherStatus = dialog.getByTestId('tool-env-status-LifecycleOther')
  await expect(action).toBeEnabled()
  await expect(dialog.getByTestId('tool-env-recreate-LifecycleOther')).toBeEnabled()
  const unchangedOtherStatus = (await otherStatus.textContent())!.trim()

  await action.click()
  await expect(page.getByText(failure, { exact: true })).toBeVisible()
  for (const name of ['LifecycleSelected', 'LifecycleSibling']) {
    await expect(dialog.getByTestId(`tool-env-status-${name}`)).toHaveText('failed')
    await expect(dialog.getByTestId(`tool-env-recreate-${name}`)).toBeEnabled()
  }
  await expect(otherStatus).toHaveText(unchangedOtherStatus)
  expect(requests).toEqual([recreatePath])

  await action.click()
  for (const name of ['LifecycleSelected', 'LifecycleSibling']) {
    await expect(dialog.getByTestId(`tool-env-status-${name}`)).toHaveText('running')
    await expect(dialog.getByTestId(`tool-env-recreate-${name}`)).toBeEnabled()
  }
  await expect(otherStatus).toHaveText(unchangedOtherStatus)
  expect(requests).toEqual([recreatePath, recreatePath])
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await page.getByTestId('manage-tools-btn').click()
  await expect(dialog).toBeVisible()
  for (const name of ['LifecycleSelected', 'LifecycleSibling']) {
    await expect(dialog.getByTestId(`tool-env-status-${name}`)).toHaveText('running')
    await expect(dialog.getByTestId(`tool-env-recreate-${name}`)).toBeEnabled()
  }
  await expect(otherStatus).toHaveText(unchangedOtherStatus)
  await expect(dialog.getByTestId('tool-env-recreate-LifecycleOther')).toBeEnabled()
  expect(requests).toEqual([recreatePath, recreatePath])
})

test('Manage Tools force click replaces only its declared real environment', async ({ page }, testInfo) => {
  test.setTimeout(300_000)
  const events: Record<string, unknown>[] = []
  page.on('websocket', socket => socket.on('framereceived', frame => {
    try { events.push(JSON.parse(String(frame.payload))) } catch { /* Non-JSON frames are irrelevant. */ }
  }))
  const posts: string[] = []
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().includes('/tools/environments/')) posts.push(new URL(request.url()).pathname)
  })
  let primary: unknown
  let cleanupFailure: unknown
  let cleanupFailed = false
  let prepared = false
  try {
    prepared = true
    const preparation = await page.request.post(`${API}/dev/e2e/tool-lifecycle/prepare`)
    expect(preparation.ok()).toBeTruthy()
    const before = await preparation.json() as Evidence
    const selected = before.inventory.find(item => item.name === SELECTED)!
    const other = before.inventory.find(item => item.name === OTHER)!
    expect(selected.worker_pids).toHaveLength(1)
    expect(other.worker_pids).toHaveLength(1)
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.getByTestId('manage-tools-btn').click()
    const dialog = page.getByTestId('manage-tools-dialog')
    await expect(dialog).toBeVisible()
    const action = dialog.getByTestId('tool-env-recreate-LifecycleSelected')
    await expect(action).toBeEnabled()
    await expect(action).toHaveAttribute('aria-label', 'Create or recreate environment')
    expect((await page.request.post(`${API}/dev/e2e/tool-lifecycle/arm`)).ok()).toBeTruthy()
    const completed = page.waitForResponse(response =>
      response.url().endsWith(`/tools/environments/${SELECTED}/recreate`) && response.request().method() === 'POST',
      { timeout: 180_000 },
    )
    await action.click()
    for (const name of ['LifecycleSelected', 'LifecycleSibling']) {
      await expect(dialog.getByTestId(`tool-env-recreate-${name}`)).toBeDisabled()
      await expect(dialog.getByTestId(`tool-env-recreate-${name}`)).toContainText('Updating')
      await expect(dialog.getByTestId(`tool-env-toggle-${name}`)).toBeDisabled()
    }
    await expect(dialog.getByTestId('tool-env-recreate-LifecycleOther')).toBeEnabled()
    expect((await page.request.get(`${API}/dev/e2e/tool-lifecycle/release`)).ok()).toBeTruthy()
    const response = await completed
    expect(response.status()).toBe(200)
    expect(await response.json()).toEqual({ environment: SELECTED, status: 'running' })
    await expect(dialog.getByTestId('tool-env-status-LifecycleSelected')).toHaveText('running')
    await expect(dialog.getByTestId('tool-env-status-LifecycleSibling')).toHaveText('running')
    await expect(action).toBeEnabled()
    const afterResponse = await page.request.get(`${API}/dev/e2e/tool-lifecycle/evidence`)
    expect(afterResponse.ok()).toBeTruthy()
    const after = await afterResponse.json() as Evidence
    const replacement = after.inventory.find(item => item.name === SELECTED)!
    expect(replacement.generation_id).not.toBe(selected.generation_id)
    expect(replacement.recipe_hash).toBe(selected.recipe_hash)
    expect(replacement.worker_pids).toHaveLength(1)
    expect(replacement.worker_pids).not.toEqual(selected.worker_pids)
    expect(after.retired_worker_pids).toEqual(selected.worker_pids)
    expect(after.retired_workers_alive).toEqual([])
    expect(after.inventory.find(item => item.name === OTHER)).toEqual(other)
    expect(after.unmanaged_sha256).toBe(before.unmanaged_sha256)
    expect(after.recreate_calls).toEqual([SELECTED])
    expect(posts).toEqual([`/api/v1/tools/environments/${SELECTED}/recreate`])
    expect(events.some(event => event.type === 'environment_status' && event.env_name === SELECTED && event.status === 'updating')).toBeTruthy()
    expect(events.some(event => event.type === 'environment_status' && event.env_name === SELECTED && event.status === 'running')).toBeTruthy()
    await dialog.getByRole('button', { name: 'Close', exact: true }).click()
    await page.locator('.dv-tab').filter({ hasText: 'Logger' }).click()
    await expect(page.getByTestId('panel-logger')).toContainText(`Environment ${SELECTED}`)
    await testInfo.attach('actual-selected-force-evidence', { body: JSON.stringify({ before, after, posts, events }, null, 2), contentType: 'application/json' })
  } catch (error) {
    primary = error
    throw error
  } finally {
    if (prepared) {
      try {
        const cleanup = await page.request.post(`${API}/dev/e2e/tool-lifecycle/close`)
        if (primary === undefined) expect(cleanup.ok()).toBeTruthy()
        else await testInfo.attach('force-cleanup-after-primary', { body: await cleanup.text(), contentType: 'text/plain' })
      } catch (cleanupError) {
        if (primary === undefined) {
          cleanupFailure = cleanupError
          cleanupFailed = true
        } else console.error('Force fixture cleanup failed while preserving the primary:', cleanupError)
      }
    }
  }
  if (cleanupFailed) throw cleanupFailure
})
