<template>
  <SimulatorPage />
</template>

<script setup lang="ts">
import { watchEffect } from "vue";

import SimulatorPage from "./pages/SimulatorPage.vue";
import { useUiStore } from "./stores/ui";

const ui = useUiStore();

watchEffect(() => {
  document.body.dataset.theme = ui.theme;
});
</script>
