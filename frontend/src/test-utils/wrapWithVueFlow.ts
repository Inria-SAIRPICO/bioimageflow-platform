import { defineComponent, h } from 'vue'
import { VueFlow } from '@vue-flow/core'

export function wrapWithVueFlow(component: any, props?: Record<string, any>) {
  return defineComponent({
    setup() {
      return () =>
        h(VueFlow, { nodes: [], edges: [] }, {
          default: () => h(component, props),
        })
    },
  })
}
