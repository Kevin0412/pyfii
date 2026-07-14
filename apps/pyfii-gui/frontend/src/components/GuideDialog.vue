<template>
  <div v-if="ui.guideOpen" class="guide-backdrop" @click.self="ui.closeGuide()">
    <section class="guide-dialog" role="dialog" aria-modal="true" :aria-label="tt('guideTitle')">
      <header>
        <div>
          <span class="eyebrow">PyFii GUI</span>
          <h2>{{ tt("guideTitle") }}</h2>
        </div>
        <button type="button" :aria-label="tt('closeGuide')" @click="ui.closeGuide()">×</button>
      </header>
      <ol>
        <li>
          <strong>{{ tt("guideLoadTitle") }}</strong>
          <span>{{ tt("guideLoadText") }}</span>
        </li>
        <li>
          <strong>{{ tt("guideWarningsTitle") }}</strong>
          <span>{{ tt("guideWarningsText") }}</span>
        </li>
        <li>
          <strong>{{ tt("guidePreviewTitle") }}</strong>
          <span>{{ tt("guidePreviewText") }}</span>
        </li>
        <li>
          <strong>{{ tt("guideExportTitle") }}</strong>
          <span>{{ tt("guideExportText") }}</span>
        </li>
      </ol>
      <footer>
        <a href="/docs/guide" @click="ui.closeGuide()">{{ tt("openFullGuide") }}</a>
        <button type="button" @click="ui.closeGuide()">{{ tt("startUsing") }}</button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { text, type MessageKey } from "../i18n";
import { useUiStore } from "../stores/ui";

const ui = useUiStore();

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}
</script>

<style scoped>
.guide-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.72);
}

.guide-dialog {
  width: min(680px, 100%);
  max-height: min(760px, calc(100vh - 40px));
  overflow: auto;
  border: 1px solid var(--border-strong);
  background: var(--panel-bg-raised);
  color: var(--text);
  box-shadow: 0 24px 80px var(--shadow);
}

header,
footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
}

header {
  border-bottom: 1px solid var(--border-soft);
}

footer {
  border-top: 1px solid var(--border-soft);
}

h2 {
  margin: 3px 0 0;
  font-size: 22px;
}

.eyebrow {
  color: var(--text-muted);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

header button {
  border: 0;
  background: transparent;
  color: var(--text);
  font-size: 24px;
  cursor: pointer;
}

ol {
  margin: 0;
  padding: 10px 22px 18px 56px;
}

li {
  padding: 11px 0 11px 5px;
}

li::marker {
  color: var(--warning);
  font-weight: 800;
}

li strong,
li span {
  display: block;
}

li span {
  margin-top: 5px;
  color: var(--text-muted);
  line-height: 1.55;
}

footer a {
  color: var(--text);
}

footer button {
  min-height: 34px;
  padding: 6px 14px;
  border: 1px solid var(--border-control);
  background: var(--control-bg);
  color: var(--text);
  cursor: pointer;
}
</style>
