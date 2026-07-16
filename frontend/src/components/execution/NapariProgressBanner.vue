<script setup lang="ts">
import { computed } from 'vue'
import ProgressBar from 'primevue/progressbar'
import { useNapariStore } from '@/stores/napari'

const napari = useNapariStore()

const headline = computed(() => (
  napari.phase === 'installing' ? 'Installing Napari…' : 'Opening in Napari…'
))
</script>

<template>
  <Transition name="napari-progress">
    <div
      v-if="napari.phase"
      class="napari-progress-banner"
      data-testid="napari-progress-banner"
      aria-live="polite"
    >
      <span
        class="napari-progress-banner__headline"
        data-testid="napari-progress-headline"
      >
        {{ headline }}
      </span>
      <ProgressBar
        mode="indeterminate"
        class="napari-progress-banner__bar"
        data-testid="napari-progress-bar"
      />
    </div>
  </Transition>
</template>

<style scoped>
.napari-progress-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: var(--p-primary-color, #3b82f6);
  color: white;
  font-weight: 500;
}

.napari-progress-banner__headline {
  flex: 0 0 auto;
}

.napari-progress-banner__bar {
  flex: 1;
  height: 0.4rem;
}

.napari-progress-enter-active,
.napari-progress-leave-active {
  transition: opacity 0.15s ease;
}

.napari-progress-enter-from,
.napari-progress-leave-to {
  opacity: 0;
}
</style>
