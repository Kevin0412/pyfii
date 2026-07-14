<template>
  <div class="docs-page" :class="`theme-${ui.theme}`">
    <SiteHeader active="docs" />

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
      <article class="markdown-body">
        <p v-if="ui.locale === 'en'" class="language-note">
          The documentation body is currently maintained in Chinese.
        </p>
        <div v-html="html" />
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import SiteHeader from "../components/SiteHeader.vue";
import {
  documentHtml,
  documentNavigation,
  type DocumentId,
} from "../content/documentation";
import { useUiStore } from "../stores/ui";

const props = defineProps<{ documentId: DocumentId }>();
const ui = useUiStore();

const html = computed(() => documentHtml(props.documentId));
const navigation = documentNavigation();
const groups = computed(() => [
  {
    id: "start",
    label: ui.locale === "zh" ? "文档中心" : "Documentation",
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
</script>

<style scoped>
.docs-page {
  --app-bg: #0b0b0b;
  --panel-bg: #111;
  --panel-bg-alt: #111;
  --text: #ececec;
  --text-muted: #949494;
  --border-soft: #303030;
  --border-control: #d8d8d8;
  --control-bg: #141414;
  --control-hover-bg: #202020;
  --docs-code: #171717;
  min-height: 100vh;
  background: var(--app-bg);
  color: var(--text);
}

.theme-light {
  --app-bg: #f7f7f7;
  --panel-bg: #fff;
  --panel-bg-alt: #fff;
  --text: #181818;
  --text-muted: #626262;
  --border-soft: #d2d2d2;
  --border-control: #555;
  --control-bg: #fff;
  --control-hover-bg: #ededed;
  --docs-code: #ededed;
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
  color: var(--text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

aside a {
  display: block;
  padding: 5px 8px;
  border-left: 2px solid transparent;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.35;
  text-decoration: none;
}

aside a:hover,
aside a.active {
  border-left-color: var(--text);
  color: var(--text);
}

.markdown-body {
  min-width: 0;
  line-height: 1.72;
}

.language-note {
  margin: 0 0 24px;
  padding: 10px 12px;
  border-left: 3px solid var(--border-control);
  background: var(--docs-code);
  color: var(--text-muted);
  font-size: 13px;
}

.markdown-body :deep(h1) {
  margin: 0 0 30px;
  font-size: clamp(30px, 5vw, 48px);
  line-height: 1.1;
}

.markdown-body :deep(h2) {
  margin: 42px 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
  font-size: 24px;
}

.markdown-body :deep(h3) {
  margin-top: 28px;
  font-size: 18px;
}

.markdown-body :deep(p),
.markdown-body :deep(li) {
  color: var(--text);
}

.markdown-body :deep(a) {
  color: #5da9ff;
}

.markdown-body :deep(pre) {
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--border-soft);
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
  border: 1px solid var(--border-soft);
}

@media (max-width: 820px) {
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
