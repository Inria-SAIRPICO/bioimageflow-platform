import { readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'
import type { FullConfig, FullResult, Reporter, Suite } from '@playwright/test/reporter'
import {
  auditCampaignCollection,
  CAMPAIGN_ANNOTATION,
  loadCampaignExclusions,
  type CollectedCampaignCase,
} from '../src/test-utils/campaignScope'

export default class CampaignPlaywrightReporter implements Reporter {
  private auditError: Error | undefined

  onBegin(config: FullConfig, suite: Suite): void {
    try {
      const frontendRoot = resolve(import.meta.dirname, '..')
      const casesByProject = new Map<string, CollectedCampaignCase[]>()
      for (const testCase of suite.allTests()) {
        const annotations = testCase.annotations.filter(annotation => annotation.type === CAMPAIGN_ANNOTATION)
        const project = testCase.titlePath()[1] ?? 'unknown-project'
        const cases = casesByProject.get(project) ?? []
        cases.push({
          nodeid: `${relative(frontendRoot, testCase.location.file).replaceAll('\\', '/')}::${testCase.titlePath().slice(3).join(' > ')}`,
          reason: annotations.length === 1 ? annotations[0]?.description : annotations.length ? annotations.map(item => item.description) : undefined,
        })
        casesByProject.set(project, cases)
      }
      const manifestPath = resolve(import.meta.dirname, '../../tests/campaign-local-scope.json')
      const manifestDocument: unknown = JSON.parse(readFileSync(manifestPath, 'utf8'))
      const manifest = loadCampaignExclusions(manifestDocument, 'browser', 'playwright')
      for (const [project, cases] of casesByProject) {
        const result = auditCampaignCollection(`browser (${project})`, cases, manifest)
        console.log(`Campaign browser scope (${project}): ${result.selected.length} selected, ${result.excluded.length} excluded.`)
      }
    } catch (error) {
      this.auditError = error instanceof Error ? error : new Error(String(error))
      console.error(this.auditError.message)
    }
  }

  onEnd(_result: FullResult): { status?: FullResult['status'] } | undefined {
    return this.auditError ? { status: 'failed' } : undefined
  }
}
