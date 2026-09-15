import { test, expect } from '@playwright/test'

const API_BASE = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const AVIVATOR_ORIGIN = 'https://avivator.gehlenborglab.org'

function deriveWorkflowId(value: string): string {
  return value
    .trim()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/_+/g, '_')
    .toLowerCase()
}

test.describe('Avivator viewer', () => {
  test('opens a converted OME-TIFF image inside the Dockview panel', async ({ page }) => {
    const displayName = `Image result ${test.info().project.name} ${Date.now()}`
    const workflowName = deriveWorkflowId(displayName)
    await page.route('https://avivator.gehlenborglab.org/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: String.raw`
          <!doctype html>
          <html>
            <body data-status="loading">
              <script>
                const imageUrl = new URL(window.location.href).searchParams.get('image_url');
                const parsed = new URL(imageUrl);
                const offsets = new URL(parsed.toString());
                offsets.pathname = offsets.pathname.replace(/\.ome\.tiff?$/i, '.offsets.json');
                document.body.dataset.imageUrl = imageUrl;
                document.body.dataset.offsetsUrl = offsets.toString();
                document.body.dataset.status = parsed.searchParams.get('format') === 'ome-tiff' ? 'loaded' : 'failed';
              </script>
            </body>
          </html>
        `,
      })
    })

    // Thumbnail environment provisioning is a separate external acceptance
    // boundary. Keep this journey focused on the real result/image endpoints
    // while still requiring a readable, non-placeholder GUI preview.
    await page.route('**/api/v1/nodes/*/thumbnail?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'image/png',
        headers: { 'X-Thumbnail-Status': 'ready' },
        body: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
          'base64',
        ),
      })
    })

    expect((await page.request.post(`${API_BASE}/api/v1/dev/seed`)).ok()).toBeTruthy()
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.getByRole('menuitem', { name: 'Workflow', exact: true }).click()
    await page.getByRole('menuitem', { name: 'New', exact: true }).click()
    await page.getByTestId('workflow-display-name-input').fill(displayName)
    await page.getByTestId('workflow-dialog-submit').click()
    await expect(page.getByTestId('workflow-title')).toContainText(displayName)

    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.getByTestId('tool-search').fill('ImageResultFixture')
    const tool = page.getByTestId('tool-item-ImageResultFixture')
    await expect(tool).toBeVisible()
    const draftResponse = page.waitForResponse(response => (
      response.url().includes(`/api/v1/workflow-drafts/${workflowName}`)
      && response.request().method() === 'PUT'
      && response.status() === 200
    ))
    await tool.dblclick()
    await draftResponse
    const node = page.locator('.vue-flow__node').filter({ hasText: 'Image Result Fixture' })
    await expect(node).toBeVisible()
    const nodeId = await node.getAttribute('data-id')
    expect(nodeId).toBeTruthy()

    const runResponse = page.waitForResponse(response => (
      response.url().endsWith('/api/v1/execution/run')
      && response.request().method() === 'POST'
    ))
    await page.getByTestId('run-workflow-button').click()
    expect((await runResponse).status()).toBe(202)
    await expect(page.getByTestId('execution-banner-headline')).toHaveText(
      'Execution complete',
      { timeout: 30_000 },
    )

    await node.click()
    await page.locator('.dv-tab').filter({ hasText: /^Node Data$/ }).click()
    const table = page.getByTestId('merged-data-table')
    await expect(table).toBeVisible()
    await expect(table.getByTestId('image-thumbnail')).toHaveAttribute('src', /^blob:/)
    const displayedPaths = table.getByTestId('path-display')
    await expect(displayedPaths).toHaveCount(2)
    await expect(table.getByText('mask.png', { exact: true })).toBeVisible()
    await expect(table.getByText('measurements.txt', { exact: true })).toBeVisible()

    const resultResponse = await page.request.post(
      `${API_BASE}/api/v1/nodes/${encodeURIComponent(nodeId!)}/data/query`,
      { data: { workflow_name: workflowName } },
    )
    expect(resultResponse.ok()).toBeTruthy()
    const result = await resultResponse.json() as {
      columns: string[]
      rows: Array<{ mask: string, report: string }>
    }
    expect(result.columns).toEqual(['mask', 'report'])
    expect(result.rows).toHaveLength(1)
    await expect(displayedPaths.nth(0)).toHaveAttribute('title', result.rows[0].mask)
    await expect(displayedPaths.nth(1)).toHaveAttribute('title', result.rows[0].report)

    const imageUrl = new URL(
      `/api/v1/nodes/${encodeURIComponent(nodeId!)}/image/mask.ome.tif`,
      API_BASE,
    )
    imageUrl.searchParams.set('row', '0')
    imageUrl.searchParams.set('col', 'mask')
    imageUrl.searchParams.set('format', 'ome-tiff')
    imageUrl.searchParams.set('workflow_name', workflowName)

    const preflight = await page.request.fetch(imageUrl.toString(), {
      method: 'OPTIONS',
      headers: {
        Origin: AVIVATOR_ORIGIN,
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'range',
        'Access-Control-Request-Private-Network': 'true',
      },
    })
    expect(preflight.ok()).toBeTruthy()
    expect(preflight.headers()['access-control-allow-private-network']).toBe('true')

    const imageResponse = await page.request.get(imageUrl.toString(), {
      headers: {
        Origin: AVIVATOR_ORIGIN,
        Range: 'bytes=0-8191',
      },
    })
    expect(imageResponse.status(), await imageResponse.text()).toBeLessThan(400)
    expect(imageResponse.headers()['content-type']).toContain('image/tiff')
    const bytes = new Uint8Array(await imageResponse.body())
    expect(Array.from(bytes.slice(0, 4))).toEqual([0x49, 0x49, 0x2a, 0x00])
    expect(new TextDecoder('utf-8', { fatal: false }).decode(bytes)).toContain('OME')

    const offsetsUrl = new URL(imageUrl.toString())
    offsetsUrl.pathname = offsetsUrl.pathname.replace(/\.ome\.tiff?$/i, '.offsets.json')
    const offsetsResponse = await page.request.get(offsetsUrl.toString(), {
      headers: {
        Origin: AVIVATOR_ORIGIN,
      },
    })
    expect(offsetsResponse.status(), await offsetsResponse.text()).toBeLessThan(400)
    expect(offsetsResponse.headers()['content-type']).toContain('application/json')
    const offsets = (await offsetsResponse.json()) as number[]
    expect(Array.isArray(offsets)).toBeTruthy()
    expect(offsets.length).toBeGreaterThan(0)
    expect(offsets.every((offset) => Number.isInteger(offset) && offset > 0)).toBeTruthy()

    await expect(table.locator('.p-datatable-mask')).toHaveCount(0)
    await table.getByTestId('open-avivator-0-mask').click()

    await expect(page.locator('[data-testid="avivator-panel"]')).toBeVisible()
    await expect(page.locator('[data-testid="avivator-iframe"]')).toBeVisible()
    const iframeBody = page.frameLocator('[data-testid="avivator-iframe"]').locator('body')
    await expect(iframeBody).toHaveAttribute('data-status', 'loaded')
    await expect(iframeBody).toHaveAttribute('data-image-url', imageUrl.toString())
    await expect(iframeBody).toHaveAttribute('data-offsets-url', offsetsUrl.toString())

    await page.request.delete(`${API_BASE}/api/v1/workflows/${workflowName}`)
  })
})
