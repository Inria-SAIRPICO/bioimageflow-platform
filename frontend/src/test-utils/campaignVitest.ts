import { it } from 'vitest'
import { CAMPAIGN_ANNOTATION, type CampaignExclusionReason } from './campaignScope'

const campaignLocal = process.env.BIOIMAGEFLOW_CAMPAIGN_LOCAL === '1'

export function campaignExcluded(reason: CampaignExclusionReason) {
  return (name: string, handler: () => void | Promise<void>) => it(name, async (context) => {
    await context.annotate(reason, CAMPAIGN_ANNOTATION)
    context.skip(campaignLocal, 'Excluded from the local-platform campaign')
    await handler()
  })
}
