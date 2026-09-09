import { readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'
import type { Reporter, TestModule } from 'vitest/reporters'
import {
  auditCampaignCollection,
  CAMPAIGN_ANNOTATION,
  loadCampaignExclusions,
  type CollectedCampaignCase,
} from '../src/test-utils/campaignScope'

export default class CampaignVitestReporter implements Reporter {
  onTestRunEnd(modules: ReadonlyArray<TestModule>): void {
    const cases: CollectedCampaignCase[] = []
    for (const module of modules) {
      const file = relative(resolve(import.meta.dirname, '..'), module.moduleId).replaceAll('\\', '/')
      for (const testCase of module.children.allTests()) {
        const annotations = testCase.annotations().filter(annotation => annotation.type === CAMPAIGN_ANNOTATION)
        cases.push({
          nodeid: `${file}::${testCase.fullName}`,
          reason: annotations.length === 1 ? annotations[0]?.message : annotations.length ? annotations.map(item => item.message) : undefined,
        })
      }
    }
    const manifestPath = resolve(import.meta.dirname, '../../tests/campaign-local-scope.json')
    const manifestDocument: unknown = JSON.parse(readFileSync(manifestPath, 'utf8'))
    const manifest = loadCampaignExclusions(manifestDocument, 'frontend-unit', 'vitest')
    const result = auditCampaignCollection('frontend-unit', cases, manifest)
    console.log(`Campaign frontend-unit scope: ${result.selected.length} selected, ${result.excluded.length} excluded.`)
  }
}
