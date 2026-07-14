<template>
  <header class="site-header">
    <a class="site-brand" href="/">
      <strong>PyFii</strong>
      <span>Python × Fii</span>
    </a>
    <nav aria-label="Site navigation">
      <a href="/" :aria-current="active === 'home' ? 'page' : undefined">{{ tt("home") }}</a>
      <a href="/docs" :aria-current="active === 'docs' ? 'page' : undefined">{{ tt("resources") }}</a>
      <a href="/studio" :aria-current="active === 'studio' ? 'page' : undefined">{{ tt("studio") }}</a>
    </nav>
    <div class="site-actions">
      <button type="button" @click="ui.toggleTheme()">
        {{ ui.theme === "dark" ? tt("themeLight") : tt("themeDark") }}
      </button>
      <button type="button" @click="ui.toggleLocale()">{{ tt("languageSwitch") }}</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { text, type MessageKey } from "../i18n";
import { useUiStore } from "../stores/ui";

defineProps<{ active: "home" | "docs" | "studio" }>();

const ui = useUiStore();

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}
</script>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 30;
  min-height: 58px;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 8px clamp(14px, 3vw, 34px);
  border-bottom: 1px solid var(--border-soft, #303030);
  background: color-mix(in srgb, var(--panel-bg, #101010) 94%, transparent);
  color: var(--text, #efefef);
  backdrop-filter: blur(12px);
}

.site-brand {
  flex: 0 0 auto;
  display: grid;
  color: inherit;
  line-height: 1;
  text-decoration: none;
}

.site-brand strong {
  font-size: 19px;
  letter-spacing: 0.02em;
}

.site-brand span {
  margin-top: 5px;
  color: var(--text-muted, #8d8d8d);
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

nav {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 4px;
}

nav a {
  padding: 7px 9px;
  border: 1px solid transparent;
  color: var(--text-muted, #8d8d8d);
  font-size: 12px;
  text-decoration: none;
  white-space: nowrap;
}

nav a:hover,
nav a[aria-current="page"] {
  border-color: var(--border-soft, #303030);
  color: var(--text, #efefef);
  background: var(--control-hover-bg, #202020);
}

.site-actions {
  flex: 0 0 auto;
  display: flex;
  gap: 7px;
}

.site-actions button {
  min-height: 30px;
  padding: 5px 9px;
  font-size: 11px;
}

@media (max-width: 760px) {
  .site-header {
    position: relative;
    flex-wrap: wrap;
    gap: 8px 14px;
  }

  nav {
    order: 3;
    width: 100%;
    overflow-x: auto;
  }

  .site-actions {
    margin-left: auto;
  }
}
</style>
