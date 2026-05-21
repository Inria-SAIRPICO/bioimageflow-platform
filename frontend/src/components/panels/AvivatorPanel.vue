<script setup lang="ts">
type AvivatorPanelParams = {
  url?: string
  imageUrl?: string
  title?: string
}

const props = defineProps<{
  params?: AvivatorPanelParams
}>()
</script>

<template>
  <section class="avivator-panel" data-testid="avivator-panel">
    <iframe
      v-if="params?.url"
      class="avivator-panel__frame"
      data-testid="avivator-iframe"
      :src="params.url"
      :title="params.title ? `Avivator - ${params.title}` : 'Avivator'"
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
