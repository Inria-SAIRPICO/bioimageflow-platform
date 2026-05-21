<script setup lang="ts">
import { computed } from 'vue'

export type AvivatorPanelParams = {
  url?: string
  imageUrl?: string
  title?: string
  params?: AvivatorPanelParams
}

const props = defineProps<{
  params?: AvivatorPanelParams
}>()

const panelParams = computed(() => props.params?.url
  ? props.params
  : props.params?.params)
</script>

<template>
  <section class="avivator-panel" data-testid="avivator-panel">
    <iframe
      v-if="panelParams?.url"
      class="avivator-panel__frame"
      data-testid="avivator-iframe"
      :src="panelParams.url"
      :title="panelParams.title ? `Avivator - ${panelParams.title}` : 'Avivator'"
      allow="fullscreen"
    />
    <div
      v-else
      class="avivator-panel__empty"
      data-testid="avivator-empty"
    >
      No image loaded.
    </div>
  </section>
</template>

<style scoped>
.avivator-panel {
  width: 100%;
  height: 100%;
  min-height: 240px;
  background: var(--bif-surface);
  display: flex;
  flex-direction: column;
}

.avivator-panel__frame {
  display: block;
  width: 100%;
  min-height: 0;
  flex: 1 1 auto;
  border: 0;
}

.avivator-panel__empty {
  flex: 1 1 auto;
  display: grid;
  place-items: center;
  padding: 1rem;
  color: var(--p-text-muted-color);
  text-align: center;
}
</style>
