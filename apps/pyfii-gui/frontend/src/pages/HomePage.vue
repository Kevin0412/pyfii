<template>
  <div class="portal-page" :class="`theme-${ui.theme}`">
    <SiteHeader active="home" />

    <main>
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">OPEN-SOURCE PYTHON TOOLKIT FOR FII</p>
          <h1>{{ tt("portalTitle") }}</h1>
          <p class="hero-summary">{{ tt("portalSummary") }}</p>
          <div class="hero-actions">
            <a class="primary-action" href="/docs/tutorial/install">{{ tt("getStarted") }} →</a>
            <a href="/studio">{{ tt("openStudio") }}</a>
            <a href="/docs">{{ tt("browseResources") }}</a>
            <a href="https://github.com/Kevin0412/pyfii" target="_blank" rel="noopener noreferrer">
              GitHub ↗
            </a>
          </div>
        </div>
        <div class="hero-terminal" aria-label="PyFii workflow">
          <span>$ pip install pyfii</span>
          <span class="terminal-muted">01 / {{ tt("portalStepCode") }}</span>
          <span class="terminal-muted">02 / {{ tt("portalStepValidate") }}</span>
          <span class="terminal-muted">03 / {{ tt("portalStepPreview") }}</span>
          <strong>PROJECT READY FOR REVIEW_</strong>
        </div>
      </section>

      <section class="portal-section" aria-labelledby="start-heading">
        <div class="section-heading">
          <p class="eyebrow">START HERE</p>
          <h2 id="start-heading">{{ tt("portalExplore") }}</h2>
        </div>
        <div class="entry-grid">
          <a href="/docs">
            <span class="entry-index">01</span>
            <strong>{{ tt("resources") }}</strong>
            <p>{{ tt("portalResourcesText") }}</p>
            <span class="entry-arrow">→</span>
          </a>
          <a href="/studio">
            <span class="entry-index">02</span>
            <strong>{{ tt("studio") }}</strong>
            <p>{{ tt("portalStudioText") }}</p>
            <span class="entry-arrow">→</span>
          </a>
        </div>
      </section>

      <section class="portal-section video-section" aria-labelledby="video-heading">
        <div class="section-heading">
          <p class="eyebrow">VIDEO TUTORIAL</p>
          <h2 id="video-heading">{{ tt("portalVideoTitle") }}</h2>
          <p>{{ tt("portalVideoText") }}</p>
        </div>
        <div class="video-frame">
          <iframe
            src="https://player.bilibili.com/player.html?isOutside=true&aid=955309609&bvid=BV1Ms4y1F7fM&cid=1178427157&p=1"
            title="PyFii Bilibili video tutorial"
            loading="lazy"
            scrolling="no"
            frameborder="0"
            allow="autoplay; fullscreen; picture-in-picture"
            allowfullscreen
          />
        </div>
      </section>
    </main>

    <footer class="portal-footer">
      <div>
        <strong>PyFii</strong>
        <span>{{ tt("portalFooter") }}</span>
      </div>
      <a href="https://github.com/Kevin0412/pyfii" target="_blank" rel="noopener noreferrer">
        github.com/Kevin0412/pyfii ↗
      </a>
      <div v-if="ui.complianceLinks.length" class="compliance-links" aria-label="备案信息">
        <a
          v-for="link in ui.complianceLinks"
          :key="link.label"
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
        >
          <img v-if="link.kind === 'gongan'" :src="beianIcon" alt="" />
          <span>{{ link.label }}</span>
        </a>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import beianIcon from "../assets/beian-icon.png";
import SiteHeader from "../components/SiteHeader.vue";
import { text, type MessageKey } from "../i18n";
import { useUiStore } from "../stores/ui";

const ui = useUiStore();

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}
</script>

<style scoped>
.portal-page {
  --app-bg: #090909;
  --panel-bg: #101010;
  --panel-bg-alt: #0d0d0d;
  --border-soft: #303030;
  --border-control: #d8d8d8;
  --text: #efefef;
  --text-muted: #969696;
  --control-bg: #141414;
  --control-hover-bg: #202020;
  min-height: 100vh;
  background: var(--app-bg);
  color: var(--text);
}

.theme-light {
  --app-bg: #f3f3f3;
  --panel-bg: #fff;
  --panel-bg-alt: #eaeaea;
  --border-soft: #c8c8c8;
  --border-control: #555;
  --text: #151515;
  --text-muted: #606060;
  --control-bg: #fff;
  --control-hover-bg: #e4e4e4;
}

main {
  width: min(1180px, calc(100% - 40px));
  margin: 0 auto;
}

.hero {
  min-height: min(680px, calc(100vh - 58px));
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  align-items: center;
  gap: clamp(40px, 8vw, 110px);
  padding: 80px 0;
}

.eyebrow {
  margin: 0 0 14px;
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: 0.18em;
}

h1 {
  max-width: 800px;
  margin: 0;
  font-size: clamp(44px, 7vw, 86px);
  font-weight: 500;
  letter-spacing: -0.06em;
  line-height: 0.98;
}

.hero-summary {
  max-width: 680px;
  margin: 28px 0 0;
  color: var(--text-muted);
  font-size: clamp(14px, 1.6vw, 18px);
  line-height: 1.75;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 34px;
}

.hero-actions a {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  border: 1px solid var(--border-control);
  color: var(--text);
  font-size: 12px;
  text-decoration: none;
}

.hero-actions a:hover {
  background: var(--control-hover-bg);
}

.hero-actions .primary-action {
  background: var(--text);
  color: var(--app-bg);
}

.hero-terminal {
  display: grid;
  gap: 18px;
  padding: 24px;
  border: 1px solid var(--border-soft);
  background: var(--panel-bg-alt);
  font-size: 11px;
  line-height: 1.45;
}

.terminal-muted {
  color: var(--text-muted);
}

.hero-terminal strong {
  margin-top: 18px;
  font-size: 12px;
}

.portal-section {
  padding: 90px 0;
  border-top: 1px solid var(--border-soft);
}

.section-heading {
  max-width: 670px;
  margin-bottom: 34px;
}

.section-heading h2 {
  margin: 0;
  font-size: clamp(28px, 4vw, 48px);
  font-weight: 500;
  letter-spacing: -0.04em;
}

.section-heading > p:last-child {
  margin: 18px 0 0;
  color: var(--text-muted);
  line-height: 1.7;
}

.entry-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid var(--border-soft);
  border-left: 1px solid var(--border-soft);
}

.entry-grid a {
  min-height: 230px;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: 18px;
  padding: 22px;
  border-right: 1px solid var(--border-soft);
  border-bottom: 1px solid var(--border-soft);
  color: var(--text);
  text-decoration: none;
}

.entry-grid a:hover {
  background: var(--control-hover-bg);
}

.entry-index,
.entry-grid p {
  color: var(--text-muted);
  font-size: 11px;
}

.entry-grid strong {
  font-size: 18px;
  font-weight: 500;
}

.entry-grid p {
  margin: 0;
  line-height: 1.65;
}

.entry-arrow {
  justify-self: end;
  font-size: 20px;
}

.video-section {
  display: grid;
  grid-template-columns: minmax(260px, 0.65fr) minmax(0, 1.35fr);
  align-items: center;
  gap: clamp(30px, 7vw, 90px);
}

.video-frame {
  position: relative;
  padding-top: 56.25%;
  border: 1px solid var(--border-soft);
  background: #000;
  overflow: hidden;
}

.video-frame iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.portal-footer {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 20px;
  padding: 28px max(20px, calc((100% - 1180px) / 2));
  border-top: 1px solid var(--border-soft);
  background: var(--panel-bg-alt);
  color: var(--text-muted);
  font-size: 11px;
}

.portal-footer > div:first-child {
  display: grid;
  gap: 5px;
}

.portal-footer strong {
  color: var(--text);
  font-size: 15px;
}

.portal-footer a {
  color: inherit;
  text-decoration: none;
}

.portal-footer a:hover {
  color: var(--text);
  text-decoration: underline;
}

.compliance-links {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  gap: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--border-soft);
}

.compliance-links a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.compliance-links img {
  width: 18px;
  height: 20px;
  object-fit: contain;
}

:global(body[data-device="tablet"][data-orientation="portrait"] .portal-page .hero),
:global(body[data-device="tablet"][data-orientation="portrait"] .portal-page .video-section),
:global(body[data-device="phone"] .portal-page .hero),
:global(body[data-device="phone"] .portal-page .video-section) {
  grid-template-columns: 1fr;
}

:global(body[data-device="tablet"][data-orientation="portrait"] .portal-page .hero),
:global(body[data-device="phone"] .portal-page .hero) {
  min-height: auto;
}

:global(body[data-device="phone"] .portal-page main) {
  width: min(100% - 28px, 1180px);
}

:global(body[data-device="phone"] .portal-page .hero) {
  padding: 52px 0;
}

:global(body[data-device="phone"] .portal-page h1) {
  font-size: clamp(38px, 13vw, 58px);
}

:global(body[data-device="phone"] .portal-page .hero-actions a) {
  min-height: 44px;
}

:global(body[data-device="phone"] .portal-page .portal-section) {
  padding: 62px 0;
}

:global(body[data-device="phone"] .portal-page .entry-grid) {
  grid-template-columns: 1fr;
}

:global(body[data-device="phone"] .portal-page .entry-grid a) {
  min-height: 190px;
}

:global(body[data-device="phone"] .portal-page .portal-footer) {
  grid-template-columns: 1fr;
}

:global(body[data-device="phone"] .portal-page .compliance-links) {
  justify-content: flex-start;
  flex-direction: column;
}

:global(body[data-device="phone"][data-orientation="landscape"] .portal-page .hero) {
  grid-template-columns: minmax(0, 1.2fr) minmax(240px, 0.8fr);
}
</style>
