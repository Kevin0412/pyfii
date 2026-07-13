<template>
  <HomePage v-if="route.page === 'home'" />
  <DocumentationPage
    v-else-if="route.page === 'document'"
    :document-id="route.documentId"
  />
  <SimulatorPage v-else />
</template>

<script setup lang="ts">
import { defineAsyncComponent, onMounted, onUnmounted, ref, watchEffect } from "vue";

import { fetchAppConfig } from "./api/config";
import {
  appRouteFromPath,
  canonicalAppPath,
  isAppPath,
  legacyPathFromHash,
  type AppRoute,
} from "./content/documentRoutes";
import HomePage from "./pages/HomePage.vue";
import { useUiStore } from "./stores/ui";

const DocumentationPage = defineAsyncComponent(() => import("./pages/DocumentationPage.vue"));
const SimulatorPage = defineAsyncComponent(() => import("./pages/SimulatorPage.vue"));
const ui = useUiStore();
const route = ref<AppRoute>(
  appRouteFromPath(legacyPathFromHash(window.location.hash) ?? window.location.pathname),
);

function syncRoute(): void {
  route.value = appRouteFromPath(window.location.pathname);
}

function normalizeInitialLocation(): void {
  const legacyPath = legacyPathFromHash(window.location.hash);
  const currentPath = canonicalAppPath(window.location.pathname);
  const nextPath = legacyPath ?? currentPath;
  if (legacyPath || nextPath !== window.location.pathname) {
    const hash = legacyPath ? "" : window.location.hash;
    window.history.replaceState({}, "", `${nextPath}${window.location.search}${hash}`);
  }
  syncRoute();
}

function handleInternalLink(event: MouseEvent): void {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }

  const target = event.target instanceof Element
    ? event.target.closest<HTMLAnchorElement>("a")
    : null;
  if (!target || target.target || target.hasAttribute("download")) {
    return;
  }

  const url = new URL(target.href, window.location.href);
  if (url.origin !== window.location.origin || !isAppPath(url.pathname)) {
    return;
  }

  event.preventDefault();
  const path = canonicalAppPath(url.pathname);
  window.history.pushState({}, "", `${path}${url.search}${url.hash}`);
  syncRoute();
  window.scrollTo({ top: 0 });
}

watchEffect(() => {
  document.body.dataset.theme = ui.theme;
  document.documentElement.lang = ui.locale === "zh" ? "zh-CN" : "en";
});

onMounted(() => {
  normalizeInitialLocation();
  window.addEventListener("popstate", syncRoute);
  document.addEventListener("click", handleInternalLink);
  fetchAppConfig()
    .then((config) => ui.setAppConfig(config))
    .catch(() => {
      /* Deployment config is optional for a static frontend preview. */
    });
});

onUnmounted(() => {
  window.removeEventListener("popstate", syncRoute);
  document.removeEventListener("click", handleInternalLink);
});
</script>
