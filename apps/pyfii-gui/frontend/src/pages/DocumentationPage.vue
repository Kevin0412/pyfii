<template>
  <div class="docs-page" :class="`theme-${ui.theme}`">
    <SiteHeader active="docs" />

    <div class="docs-layout">
      <aside>
        <details ref="navigationRef" class="docs-navigation">
          <summary>
            <span>{{ ui.locale === "zh" ? "文档目录" : "Contents" }}</span>
            <strong>{{ currentTitle }}</strong>
          </summary>
          <div class="docs-nav-groups">
            <section v-for="group in groups" :key="group.id">
              <h2>{{ group.label }}</h2>
              <a
                v-for="item in group.items"
                :key="item.id"
                :href="item.source.route"
                :class="{ active: item.id === documentId }"
                @click="closePhoneNavigation"
              >
                {{ item.source.title[ui.locale] }}
              </a>
            </section>
          </div>
        </details>
      </aside>
      <!-- Markdown is bundled from trusted repository documentation sources. -->
      <article class="markdown-body">
        <p v-if="loading" class="document-status">{{ tt("loadingDocument") }}</p>
        <p v-else-if="loadFailed" class="document-status error">{{ tt("documentLoadFailed") }}</p>
        <p v-else-if="ui.locale === 'en'" class="language-note">
          The documentation body is currently maintained in Chinese.
        </p>
        <div v-if="!loading && !loadFailed" v-html="html" />
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import SiteHeader from "../components/SiteHeader.vue";
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

const html = ref("");
const navigationRef = ref<HTMLDetailsElement | null>(null);
const loading = ref(true);
const loadFailed = ref(false);
const navigation = documentNavigation();
let loadVersion = 0;

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}

function closePhoneNavigation(): void {
  if (document.body.dataset.device === "phone" && navigationRef.value) {
    navigationRef.value.open = false;
  }
}

watch(
  () => props.documentId,
  async (documentId) => {
    const version = ++loadVersion;
    loading.value = true;
    loadFailed.value = false;
    try {
      const nextHtml = await documentHtml(documentId);
      if (version === loadVersion) html.value = nextHtml;
    } catch {
      if (version === loadVersion) loadFailed.value = true;
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  },
  { immediate: true },
);

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
  {
    id: "choreo",
    label: ui.locale === "zh" ? "编舞与 Agent" : "Choreography & Agent",
    items: navigation.filter((item) => item.source.group === "choreo"),
  },
  {
    id: "research",
    label: ui.locale === "zh" ? "工程研究" : "Engineering Research",
    items: navigation.filter((item) => item.source.group === "research"),
  },
]);
const currentTitle = computed(() => documentSource(props.documentId).title[ui.locale]);
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

.docs-navigation > summary {
  display: none;
}

.docs-navigation:not([open]) > .docs-nav-groups {
  display: block;
}

.docs-nav-groups section + section {
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

.document-status {
  margin: 60px 0;
  color: var(--text-muted);
  text-align: center;
}

.document-status.error {
  color: #b90000;
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

:global(body[data-device="tablet"][data-orientation="portrait"] .docs-page .docs-layout),
:global(body[data-device="phone"] .docs-page .docs-layout) {
  grid-template-columns: 1fr;
  gap: 24px;
  padding: 24px 18px 60px;
}

:global(body[data-device="tablet"][data-orientation="portrait"] .docs-page aside),
:global(body[data-device="phone"] .docs-page aside) {
  position: static;
  max-height: none;
}

:global(body[data-device="tablet"][data-orientation="portrait"] .docs-page .docs-nav-groups) {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 28px;
}

:global(body[data-device="phone"] .docs-page .docs-navigation) {
  border: 1px solid var(--border-soft);
  background: var(--panel-bg);
}

:global(body[data-device="phone"] .docs-page .docs-navigation > summary) {
  min-height: 48px;
  display: grid;
  gap: 3px;
  padding: 9px 12px;
  cursor: pointer;
  list-style-position: inside;
}

:global(body[data-device="phone"] .docs-page .docs-navigation > summary span) {
  color: var(--text-muted);
  font-size: 10px;
  text-transform: uppercase;
}

:global(body[data-device="phone"] .docs-page .docs-navigation > summary strong) {
  color: var(--text);
  font-size: 12px;
}

:global(body[data-device="phone"] .docs-page .docs-navigation:not([open]) > .docs-nav-groups) {
  display: none;
}

:global(body[data-device="phone"] .docs-page .docs-nav-groups) {
  padding: 4px 12px 14px;
}

:global(body[data-device="phone"] .docs-page aside a) {
  min-height: 38px;
  display: flex;
  align-items: center;
}

:global(body[data-device="phone"] .docs-page .markdown-body h1) {
  font-size: clamp(28px, 10vw, 42px);
}

:global(body[data-device="phone"] .docs-page .markdown-body pre) {
  padding: 12px;
  font-size: 12px;
}
</style>
