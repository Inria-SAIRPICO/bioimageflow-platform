import { expect, test, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, relative, resolve } from 'node:path'
import type { PackageInfo } from '../../src/api/types'

const API = `http://127.0.0.1:${process.env.BIOIMAGEFLOW_E2E_BACKEND_PORT ?? '8000'}/api/v1`
const PACKAGE = 'e2e_local_package_tools'
const VERSIONS = ['1.0', '1.0.0'] as const

function sourceMembers(root: string): Record<string, string> {
  const hashes: Record<string, string> = {}
  function visit(directory: string) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === '__pycache__') continue
      const path = join(directory, entry.name)
      if (entry.isDirectory()) visit(path)
      else {
        expect(entry.isFile(), 'Installed source members must be ordinary files.').toBeTruthy()
        hashes[relative(root, path)] = createHash('sha256').update(readFileSync(path)).digest('hex')
      }
    }
  }
  visit(root)
  return hashes
}

async function packages(page: Page): Promise<PackageInfo[]> {
  const response = await page.request.get(`${API}/tools/packages`)
  expect(response.ok()).toBeTruthy()
  return await response.json() as PackageInfo[]
}

test('local package install retries, version switching cancels, and uninstall preserves the other version', async ({ page }, testInfo) => {
  const fixture = process.env.BIOIMAGEFLOW_HOT_RELOAD_FIXTURE
  expect(fixture, 'Playwright must provide its actual isolated installed fixture path.').toBeTruthy()
  const unrelatedVersion = dirname(dirname(fixture!))
  const toolStore = dirname(dirname(unrelatedVersion))
  const packageRoot = join(toolStore, PACKAGE)
  const archives = mkdtempSync(join(tmpdir(), 'platform-package-source-'))
  const sentinel = join(archives, 'unmanaged-sentinel')
  const uses: string[] = []
  const deletions: string[] = []
  const importPath = '/api/v1/tools/packages/import-archive'
  let release: (() => void) | undefined
  let mainFailed = false
  let ownsPackage = false
  const cleanupErrors: unknown[] = []
  page.on('request', request => {
    const url = new URL(request.url())
    if (request.method() === 'POST' && url.pathname === `/api/v1/tools/packages/${PACKAGE}/use`) {
      uses.push((request.postDataJSON() as { version: string }).version)
    }
    if (request.method() === 'DELETE' && url.pathname === `/api/v1/tools/packages/${PACKAGE}`) {
      deletions.push(url.search)
    }
  })

  try {
    writeFileSync(sentinel, 'Unrelated package lifecycle bytes\n', { flag: 'wx' })
    const sentinelBytes = readFileSync(sentinel)
    const unrelatedBefore = sourceMembers(unrelatedVersion)
    const before = await packages(page)
    expect(before.some(item => item.name === PACKAGE)).toBeFalsy()
    expect(existsSync(packageRoot)).toBeFalsy()
    ownsPackage = true
    for (const version of VERSIONS) {
      execFileSync(resolve('../backend/.venv/bin/python'), [
        resolve('../backend/tests/fixtures/package_source_archive.py'),
        '--output', join(archives, `${version}.zip`), '--version', version,
      ])
    }
    await page.goto('/')
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.getByTestId('manage-tools-btn').click()
    const dialog = page.getByTestId('manage-tools-dialog')
    await expect(dialog).toBeVisible()
    const input = dialog.getByTestId('package-install-archive-input')
    const install = dialog.getByTestId('package-install-button')
    const importResponse = () => page.waitForResponse(response =>
      new URL(response.url()).pathname === importPath && response.request().method() === 'POST',
    )

    // This is a real public suffix refusal, followed by a real local pip retry.
    await input.setInputFiles({ name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from('not a ZIP') })
    const refusedResponse = importResponse()
    await install.click()
    const refused = await refusedResponse
    expect(refused.status()).toBe(400)
    expect(await refused.json()).toMatchObject({ error: 'bad_request', detail: 'Tool package archive must be a .zip file' })
    await expect(page.locator('.p-toast')).toContainText('Package install failed')
    await expect(page.locator('.p-toast')).toContainText('Tool package archive must be a .zip file')
    expect(await packages(page)).toEqual(before)
    expect(existsSync(packageRoot)).toBeFalsy()
    expect(sourceMembers(unrelatedVersion)).toEqual(unrelatedBefore)
    expect(readFileSync(sentinel)).toEqual(sentinelBytes)

    for (const version of VERSIONS) {
      await input.setInputFiles(join(archives, `${version}.zip`))
      // Hold only the outgoing browser request; the real route and pip run
      // after release. No workspace-mutating release endpoint is involved.
      let entered!: () => void
      const started = new Promise<void>(resolveStarted => { entered = resolveStarted })
      const gate = new Promise<void>(resolveGate => { release = resolveGate })
      const handler = async (route: import('@playwright/test').Route) => {
        entered()
        await gate
        await route.continue()
      }
      await page.route(`**${importPath}`, handler)
      const completed = importResponse()
      await install.click()
      await started
      await expect(dialog.getByTestId('package-install-busy')).toBeVisible()
      await expect(dialog.getByTestId('package-install-archive-button')).toBeDisabled()
      await expect(dialog.getByTestId('package-install-url')).toBeDisabled()
      release!()
      release = undefined
      const installed = await completed
      expect(installed.status(), await installed.text()).toBe(200)
      expect(await installed.json()).toEqual({ status: 'installed', package: PACKAGE, version })
      await page.unroute(`**${importPath}`, handler)
      await expect(dialog.getByTestId('package-install-busy')).toHaveCount(0)
      await expect(install).toBeDisabled()
      const catalog = await packages(page)
      const pkg = catalog.find(item => item.name === PACKAGE)!
      expect(pkg.installed_versions).toContain(version)
      expect(pkg.load_errors).toEqual({})
      expect(pkg.tools[version]).toContain('LocalPackageNumbers')
      expect(existsSync(join(packageRoot, version, PACKAGE, '__init__.py'))).toBeTruthy()
      expect(existsSync(join(packageRoot, version, `${PACKAGE}-${version}.dist-info`, 'RECORD'))).toBeTruthy()
    }

    const both = (await packages(page)).find(item => item.name === PACKAGE)!
    expect(both.installed_versions).toEqual([...VERSIONS])
    const survivingBytes = sourceMembers(join(packageRoot, '1.0.0'))
    expect(Object.keys(survivingBytes).some(path => path.endsWith('/METADATA'))).toBeTruthy()
    async function openVersions() {
      const list = dialog.getByTestId(`version-list-${PACKAGE}`)
      if (!await list.isVisible()) await dialog.getByTestId(`version-toggle-${PACKAGE}`).click()
      await expect(list).toBeVisible()
    }
    await openVersions()
    const alternate = both.active_version === '1.0' ? '1.0.0' : '1.0'
    await dialog.getByTestId(`set-current-version-${PACKAGE}-${alternate}`).click()
    const confirmation = page.getByRole('alertdialog', { name: 'Change Package Version' })
    await expect(confirmation).toBeVisible()
    await confirmation.getByRole('button', { name: 'Cancel', exact: true }).click()
    await expect(confirmation).not.toBeVisible()
    expect(uses).toEqual([])
    expect((await packages(page)).find(item => item.name === PACKAGE)).toEqual(both)
    expect(sourceMembers(join(packageRoot, '1.0.0'))).toEqual(survivingBytes)

    async function choose(version: string) {
      await openVersions()
      await dialog.getByTestId(`set-current-version-${PACKAGE}-${version}`).click()
      await expect(confirmation).toBeVisible()
      const switched = page.waitForResponse(response =>
        new URL(response.url()).pathname === `/api/v1/tools/packages/${PACKAGE}/use`
        && response.request().method() === 'POST',
      )
      await confirmation.getByRole('button', { name: 'Set current', exact: true }).click()
      const response = await switched
      expect(response.status()).toBe(200)
      expect(await response.json()).toEqual({ package: PACKAGE, version, status: 'active' })
      await openVersions()
      await expect(dialog.getByTestId(`current-version-${PACKAGE}-${version}`)).toBeVisible()
    }
    await choose(alternate)
    if (alternate !== '1.0.0') await choose('1.0.0')
    expect(uses).toEqual(alternate === '1.0.0' ? [alternate] : [alternate, '1.0.0'])

    const removedResponse = page.waitForResponse(response =>
      new URL(response.url()).pathname === `/api/v1/tools/packages/${PACKAGE}`
      && response.request().method() === 'DELETE',
    )
    await dialog.getByTestId(`uninstall-version-${PACKAGE}-1.0`).click()
    const removed = await removedResponse
    expect(removed.status()).toBe(200)
    expect(await removed.json()).toEqual({ status: 'uninstalled' })
    expect(deletions).toEqual(['?version=1.0'])
    expect(existsSync(join(packageRoot, '1.0'))).toBeFalsy()
    expect(sourceMembers(join(packageRoot, '1.0.0'))).toEqual(survivingBytes)
    expect(sourceMembers(unrelatedVersion)).toEqual(unrelatedBefore)
    expect(readFileSync(sentinel)).toEqual(sentinelBytes)
    const surviving = (await packages(page)).find(item => item.name === PACKAGE)!
    expect(surviving.installed_versions).toEqual(['1.0.0'])
    expect(surviving.active_version).toBe('1.0.0')
    expect(surviving.tools['1.0.0']).toContain('LocalPackageNumbers')
    expect(surviving.load_errors).toEqual({})
    await expect(dialog.getByTestId(`uninstall-version-${PACKAGE}-1.0`)).toHaveCount(0)
    await expect(dialog.getByTestId(`current-version-${PACKAGE}-1.0.0`)).toBeVisible()
    await dialog.getByRole('button', { name: 'Close', exact: true }).click()
    await page.getByTestId('manage-tools-btn').click()
    await expect(dialog.getByTestId(`version-toggle-${PACKAGE}`)).toContainText('1.0.0')
    await page.reload()
    await expect(page.locator('#bioimageflow-app')).toBeVisible()
    await page.locator('.dv-tab').filter({ hasText: 'Tools' }).click()
    await page.getByTestId('manage-tools-btn').click()
    await dialog.getByTestId(`version-toggle-${PACKAGE}`).click()
    await expect(dialog.getByTestId(`current-version-${PACKAGE}-1.0.0`)).toBeVisible()
    await expect(dialog.getByTestId(`uninstall-version-${PACKAGE}-1.0`)).toHaveCount(0)
    expect((await packages(page)).find(item => item.name === PACKAGE)).toEqual(surviving)
    expect(sourceMembers(join(packageRoot, '1.0.0'))).toEqual(survivingBytes)
    expect(sourceMembers(unrelatedVersion)).toEqual(unrelatedBefore)
    expect(readFileSync(sentinel)).toEqual(sentinelBytes)
    const evidence = testInfo.outputPath('package-lifecycle.json')
    writeFileSync(evidence, JSON.stringify({ uses, deletions, before: both, after: surviving, survivingBytes, unrelatedBefore }, null, 2))
    await testInfo.attach('actual-local-package-lifecycle', { path: evidence, contentType: 'application/json' })
  } catch (error) {
    mainFailed = true
    throw error
  } finally {
    release?.()
    async function cleanup(operation: () => Promise<unknown>) {
      try { await operation() } catch (error) { cleanupErrors.push(error) }
    }
    await cleanup(() => page.unrouteAll({ behavior: 'wait' }))
    await cleanup(() => page.goto('about:blank'))
    for (const version of VERSIONS) {
      await cleanup(async () => {
        if (!ownsPackage) return
        if (!existsSync(join(packageRoot, version))) return
        const response = await page.request.delete(`${API}/tools/packages/${PACKAGE}`, { params: { version } })
        expect(response.status()).toBe(200)
        expect(existsSync(join(packageRoot, version))).toBeFalsy()
      })
    }
    await cleanup(async () => { rmSync(archives, { recursive: true }) })
    if (cleanupErrors.length) {
      await cleanup(() => testInfo.attach('package-cleanup-errors', { body: cleanupErrors.map(String).join('\n'), contentType: 'text/plain' }))
    }
  }
  if (!mainFailed && cleanupErrors.length) throw cleanupErrors[0]
})
