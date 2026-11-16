<script setup lang="ts">
import { useOutputPlanningRecovery } from '@/composables/useOutputPlanningRecovery'
import OutputPlanningDialog from './OutputPlanningDialog.vue'

const { report, reports, busy, error, validationReports, correctionUnavailableReason, dismiss, submit, selectReport } = useOutputPlanningRecovery()
</script>

<template>
  <OutputPlanningDialog v-if="report" :report="report" :reports="reports" :busy="busy" :error="error"
    :validation-reports="validationReports" :correction-unavailable-reason="correctionUnavailableReason"
    @cancel="dismiss" @submit="submit" @select-report="selectReport" />
</template>
