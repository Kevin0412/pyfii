<template>
  <DocumentationPage v-if="documentId" :document-id="documentId" />
  <SimulatorPage v-else />
</template>

<script setup lang="ts">
import { defineAsyncComponent, onMounted, onUnmounted, ref, watchEffect } from "vue";

import SimulatorPage from "./pages/SimulatorPage.vue";
import { documentFromHash, type DocumentId } from "./content/documentRoutes";
import { useUiStore } from "./stores/ui";

const DocumentationPage = defineAsyncComponent(() => import("./pages/DocumentationPage.vue"));
const ui = useUiStore();
const documentId = ref<DocumentId | null>(documentFromHash(window.location.hash));

function syncRoute(): void {
  documentId.value = documentFromHash(window.location.hash);
}

watchEffect(() => {
  document.body.dataset.theme = ui.theme;
  document.documentElement.lang = ui.locale === "zh" ? "zh-CN" : "en";
});

onMounted(() => window.addEventListener("hashchange", syncRoute));
onUnmounted(() => window.removeEventListener("hashchange", syncRoute));
</script>
