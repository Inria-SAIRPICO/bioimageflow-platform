<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue'
import Button from 'primevue/button'
import { useValidationErrors } from '@/composables/useValidationErrors'
import type { ValidationResult } from '@/api/types'

const props = defineProps<{ validationResult: ValidationResult | null }>()

const validationResultRef = toRef(props, 'validationResult')
const { globalErrors } = useValidationErrors(validationResultRef)

function signature(): string {
  return JSON.stringify(
    globalErrors.value.map((e) => [
      e.type,
      e.detail,
      e.node ?? null,
      e.edge_id ?? null,
    ]),
  )
}

const dismissedSignature = ref<string | null>(null)
const currentSignature = computed(() => signature())

const visible = computed(
  () =>
    globalErrors.value.length > 0 &&
    currentSignature.value !== dismissedSignature.value,
)

watch(currentSignature, (sig) => {
  // If the signature changes to one we haven't dismissed, ensure the banner
  // can re-appear. Nothing to do here other than letting `visible` re-evaluate.
  void sig
})

function onDismiss() {
  dismissedSignature.value = currentSignature.value
}
</script>

<template>
  <div v-if="visible" class="canvas-error-banner" role="alert">
    <i class="pi pi-exclamation-triangle banner-icon" />
    <div class="banner-rows">
      <div
        v-for="(err, i) in globalErrors"
        :key="i"
        data-testid="canvas-error-row"
        class="banner-row"
      >
        {{ err.detail }}
      </div>
    </div>
    <Button
      data-testid="canvas-error-dismiss"
      icon="pi pi-times"
      severity="secondary"
      size="small"
      text
      aria-label="Dismiss"
      class="banner-dismiss"
      @click="onDismiss"
    />
  </div>
</template>

<style scoped>
.canvas-error-banner {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: color-mix(
    in srgb,
    var(--p-red-500, #dc2626) 12%,
    var(--p-surface-0, #fff)
  );
  border-bottom: 1px solid var(--p-red-500, #dc2626);
  color: var(--p-text-color, #111827);
}

.banner-icon {
  color: var(--p-red-600, #b91c1c);
  font-size: 1.1rem;
}

.banner-rows {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.9rem;
}

.banner-dismiss {
  margin-left: auto;
}
</style>
