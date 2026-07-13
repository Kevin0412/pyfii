<template>
  <div class="docs-page" :class="`theme-${ui.theme}`">
    <header class="docs-header">
      <a class="docs-brand" href="#/">PyFii GUI</a>
      <nav aria-label="Documentation navigation">
        <a href="#/guide">{{ label("guide") }}</a>
        <a href="#/docs">{{ label("core") }}</a>
        <a href="#/tutorial">{{ label("tutorial") }}</a>
        <a href="#/">{{ tt("backToSimulator") }}</a>
      </nav>
      <button type="button" @click="ui.toggleTheme()">
        {{ ui.theme === "dark" ? tt("themeLight") : tt("themeDark") }}
      </button>
      <button type="button" @click="ui.toggleLocale()">{{ tt("languageSwitch") }}</button>
    </header>

    <div class="docs-layout">
      <aside>
        <section v-for="group in groups" :key="group.id">
          <h2>{{ group.label }}</h2>
          <a
            v-for="item in group.items"
            :key="item.id"
            :href="item.source.route"
            :class="{ active: item.id === documentId }"
          >
            {{ item.source.title[ui.locale] }}
          </a>
        </section>
      </aside>
      <!-- Markdown is bundled from trusted repository documentation sources. -->
      <article class="markdown-body" v-html="html" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import {
  documentHtml,
  documentNavigation,
  documentSource,
  type DocumentId,
} from "../content/documentation";
import { text, type MessageKey } from "../i18n";
import { useUiStore } from "../stores/ui";

const props = defineProps<{ documentId: DocumentId }>();
const ui = useUiStore();

const html = computed(() => documentHtml(props.documentId));
const navigation = documentNavigation();
const groups = computed(() => [
  {
    id: "start",
    label: ui.locale === "zh" ? "开始" : "Start",
    items: navigation.filter((item) => item.source.group === "start"),
  },
  {
    id: "docs",
    label: ui.locale === "zh" ? "文档" : "Docs",
    items: navigation.filter((item) => item.source.group === "docs"),
  },
  {
    id: "tutorial",
    label: ui.locale === "zh" ? "教程" : "Tutorials",
    items: navigation.filter((item) => item.source.group === "tutorial"),
  },
]);

function label(id: DocumentId): string {
  return documentSource(id).title[ui.locale];
}

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}
</script>

<style scoped>
.docs-page {
  --docs-bg: #0b0b0b;
  --docs-panel: #111;
  --docs-text: #ececec;
  --docs-muted: #949494;
  --docs-border: #303030;
  --docs-code: #171717;
  min-height: 100vh;
  background: var(--docs-bg);
  color: var(--docs-text);
}

.theme-light {
  --docs-bg: #f7f7f7;
  --docs-panel: #fff;
  --docs-text: #181818;
  --docs-muted: #626262;
  --docs-border: #d2d2d2;
  --docs-code: #ededed;
}

.docs-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 54px;
  padding: 8px 18px;
  border-bottom: 1px solid var(--docs-border);
  background: var(--docs-panel);
}

.docs-brand {
  margin-right: 12px;
  color: var(--docs-text);
  font-size: 18px;
  text-decoration: none;
}

nav {
  display: flex;
  gap: 6px;
  flex: 1;
}

nav a,
.docs-header button {
  padding: 6px 9px;
  border: 1px solid var(--docs-border);
  background: transparent;
  color: var(--docs-text);
  font-size: 12px;
  text-decoration: none;
  cursor: pointer;
}

.docs-layout {
  display: grid;
  grid-template-columns: 230px minmax(0, 860px);
  justify-content: center;
  align-items: start;
  gap: 42px;
  padding: 34px 28px 80px;
}

aside {
  position: sticky;
  top: 88px;
  max-height: calc(100vh - 110px);
  overflow: auto;
}

aside section + section {
  margin-top: 22px;
}

aside h2 {
  margin: 0 0 7px;
  color: var(--docs-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

aside a {
  display: block;
  padding: 5px 8px;
  border-left: 2px solid transparent;
  color: var(--docs-muted);
  font-size: 12px;
  line-height: 1.35;
  text-decoration: none;
}

aside a:hover,
aside a.active {
  border-left-color: var(--docs-text);
  color: var(--docs-text);
}

.markdown-body {
  min-width: 0;
  line-height: 1.72;
}

.markdown-body :deep(h1) {
  margin: 0 0 30px;
  font-size: clamp(30px, 5vw, 48px);
  line-height: 1.1;
}

.markdown-body :deep(h2) {
  margin: 42px 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--docs-border);
  font-size: 24px;
}

.markdown-body :deep(h3) {
  margin-top: 28px;
  font-size: 18px;
}

.markdown-body :deep(p),
.markdown-body :deep(li) {
  color: var(--docs-text);
}

.markdown-body :deep(a) {
  color: #5da9ff;
}

.markdown-body :deep(pre) {
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--docs-border);
  background: var(--docs-code);
  line-height: 1.5;
}

.markdown-body :deep(code) {
  font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
}

.markdown-body :deep(:not(pre) > code) {
  padding: 2px 5px;
  background: var(--docs-code);
}

.markdown-body :deep(img) {
  max-width: 100%;
}

.markdown-body :deep(table) {
  display: block;
  max-width: 100%;
  overflow: auto;
  border-collapse: collapse;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 7px 10px;
  border: 1px solid var(--docs-border);
}

@media (max-width: 820px) {
  .docs-header {
    flex-wrap: wrap;
  }

  nav {
    order: 3;
    width: 100%;
    overflow: auto;
  }

  .docs-layout {
    grid-template-columns: 1fr;
    gap: 24px;
    padding: 24px 18px 60px;
  }

  aside {
    position: static;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    max-height: none;
  }
}
</style>
