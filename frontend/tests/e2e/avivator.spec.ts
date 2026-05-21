import { test, expect } from '@playwright/test'

const API_BASE = `http://localhost:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}`
const AVIVATOR_ORIGIN = 'https://avivator.gehlenborglab.org'

type SeedImageOutputResponse = {
  node_id: string
  column: string
  filename: string
}

test.describe('Avivator viewer', () => {
  test('opens a converted OME-TIFF image inside the Dockview panel', async ({ page }) => {
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
                document.body.dataset.imageUrl = imageUrl;
                document.body.dataset.status = parsed.searchParams.get('format') === 'ome-tiff' ? 'loaded' : 'failed';
              </script>
            </body>
          </html>
        `,
      })
    })

    const seedResponse = await page.request.post(`${API_BASE}/api/v1/dev/seed-image-output`)
    expect(seedResponse.ok()).toBeTruthy()
    const seed = (await seedResponse.json()) as SeedImageOutputResponse

    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()

    const imageUrl = new URL(
      `/api/v1/nodes/${encodeURIComponent(seed.node_id)}/image/${encodeURIComponent(seed.filename)}`,
      API_BASE,
    )
    imageUrl.searchParams.set('row', '0')
    imageUrl.searchParams.set('col', seed.column)
    imageUrl.searchParams.set('format', 'ome-tiff')

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

    const avivatorUrl = new URL('https://avivator.gehlenborglab.org/')
    avivatorUrl.searchParams.set('image_url', imageUrl.toString())

    await page.evaluate(
      ({ url, imageUrl }) => {
        window.dispatchEvent(new CustomEvent('bioimageflow:open-avivator', {
          detail: { url, imageUrl, title: 'mask.ome.tif' },
        }))
      },
      { url: avivatorUrl.toString(), imageUrl: imageUrl.toString() },
    )

    await expect(page.locator('[data-testid="avivator-panel"]')).toBeVisible()
    await expect(page.locator('[data-testid="avivator-iframe"]')).toBeVisible()
    const iframeBody = page.frameLocator('[data-testid="avivator-iframe"]').locator('body')
    await expect(iframeBody).toHaveAttribute('data-status', 'loaded')
    await expect(iframeBody).toHaveAttribute('data-image-url', imageUrl.toString())
  })
})
