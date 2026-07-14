<template>
  <div v-if="ui.guideOpen" class="guide-tour">
    <div
      v-for="(style, index) in maskStyles"
      :key="index"
      class="guide-mask"
      :style="style"
    />
    <div class="guide-highlight" :style="highlightStyle" />

    <section
      ref="cardRef"
      class="guide-card"
      :class="placement"
      :style="cardStyle"
      role="dialog"
      aria-modal="true"
      :aria-label="tt('guideTitle')"
      tabindex="-1"
    >
      <span class="guide-arrow" />
      <header>
        <div>
          <span class="eyebrow">PyFii GUI · {{ stepIndex + 1 }} / {{ steps.length }}</span>
          <h2>{{ tt(currentStep.title) }}</h2>
        </div>
        <button type="button" :aria-label="tt('closeGuide')" @click="ui.closeGuide()">×</button>
      </header>

      <p>{{ tt(currentStep.text) }}</p>

      <div class="step-progress" aria-hidden="true">
        <span
          v-for="(_, index) in steps"
          :key="index"
          :class="{ active: index === stepIndex }"
        />
      </div>

      <footer>
        <a href="/docs/guide" @click="ui.closeGuide()">{{ tt("openFullGuide") }}</a>
        <div class="guide-actions">
          <button v-if="stepIndex > 0" type="button" @click="previousStep">{{ tt("guideBack") }}</button>
          <button type="button" class="primary" @click="nextStep">
            {{ stepIndex === steps.length - 1 ? tt("startUsing") : tt("guideNext") }}
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
  type CSSProperties,
} from "vue";

import { text, type MessageKey } from "../i18n";
import { useUiStore } from "../stores/ui";

interface GuideStep {
  target: string;
  title: MessageKey;
  text: MessageKey;
}

interface Box {
  top: number;
  right: number;
  bottom: number;
  left: number;
  width: number;
  height: number;
}

const steps: GuideStep[] = [
  { target: "upload", title: "guideLoadTitle", text: "guideLoadText" },
  { target: "render", title: "guideRenderTitle", text: "guideRenderText" },
  { target: "preview", title: "guidePreviewTitle", text: "guidePreviewText" },
  { target: "fullscreen", title: "guideFullscreenTitle", text: "guideFullscreenText" },
  { target: "safety", title: "guideWarningsTitle", text: "guideWarningsText" },
  { target: "export", title: "guideExportTitle", text: "guideExportText" },
];

const ui = useUiStore();
const cardRef = ref<HTMLElement | null>(null);
const stepIndex = ref(0);
const targetBox = ref<Box>({ top: 0, right: 0, bottom: 0, left: 0, width: 0, height: 0 });
const cardTop = ref(16);
const cardLeft = ref(16);
const arrowLeft = ref(40);
const placement = ref<"above" | "below">("below");

const currentStep = computed(() => steps[stepIndex.value]);
const highlightStyle = computed<CSSProperties>(() => ({
  top: `${targetBox.value.top}px`,
  left: `${targetBox.value.left}px`,
  width: `${targetBox.value.width}px`,
  height: `${targetBox.value.height}px`,
}));
const cardStyle = computed<CSSProperties>(() => ({
  top: `${cardTop.value}px`,
  left: `${cardLeft.value}px`,
  "--guide-arrow-left": `${arrowLeft.value}px`,
}));
const maskStyles = computed<CSSProperties[]>(() => {
  const box = targetBox.value;
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  return [
    { top: "0", left: "0", width: `${viewportWidth}px`, height: `${box.top}px` },
    { top: `${box.bottom}px`, left: "0", width: `${viewportWidth}px`, height: `${Math.max(0, viewportHeight - box.bottom)}px` },
    { top: `${box.top}px`, left: "0", width: `${box.left}px`, height: `${box.height}px` },
    { top: `${box.top}px`, left: `${box.right}px`, width: `${Math.max(0, viewportWidth - box.right)}px`, height: `${box.height}px` },
  ];
});

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

function updatePosition(): void {
  const target = document.querySelector<HTMLElement>(`[data-guide="${currentStep.value.target}"]`);
  if (!target) return;

  const padding = 6;
  const rect = target.getBoundingClientRect();
  const left = clamp(rect.left - padding, 0, window.innerWidth);
  const top = clamp(rect.top - padding, 0, window.innerHeight);
  const right = clamp(rect.right + padding, 0, window.innerWidth);
  const bottom = clamp(rect.bottom + padding, 0, window.innerHeight);
  targetBox.value = {
    top,
    right,
    bottom,
    left,
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top),
  };

  const edge = 16;
  const gap = 14;
  const cardWidth = cardRef.value?.offsetWidth || Math.min(380, window.innerWidth - edge * 2);
  const cardHeight = cardRef.value?.offsetHeight || 220;
  const spaceBelow = window.innerHeight - bottom - gap - edge;
  placement.value = spaceBelow >= cardHeight || top < cardHeight + gap + edge ? "below" : "above";
  cardTop.value = placement.value === "below"
    ? clamp(bottom + gap, edge, window.innerHeight - cardHeight - edge)
    : clamp(top - cardHeight - gap, edge, window.innerHeight - cardHeight - edge);
  cardLeft.value = clamp(
    left + (right - left - cardWidth) / 2,
    edge,
    Math.max(edge, window.innerWidth - cardWidth - edge),
  );
  arrowLeft.value = clamp(
    left + (right - left) / 2 - cardLeft.value,
    24,
    cardWidth - 24,
  );
}

async function locateStep(): Promise<void> {
  await nextTick();
  const target = document.querySelector<HTMLElement>(`[data-guide="${currentStep.value.target}"]`);
  target?.scrollIntoView({ block: "nearest", inline: "nearest" });
  await nextTick();
  updatePosition();
  window.requestAnimationFrame(() => {
    updatePosition();
    cardRef.value?.focus({ preventScroll: true });
  });
}

function previousStep(): void {
  if (stepIndex.value > 0) stepIndex.value -= 1;
}

function nextStep(): void {
  if (stepIndex.value === steps.length - 1) {
    ui.closeGuide();
    return;
  }
  stepIndex.value += 1;
}

function onKeydown(event: KeyboardEvent): void {
  if (!ui.guideOpen) return;
  if (event.key === "Escape") ui.closeGuide();
  if (event.key === "ArrowLeft") previousStep();
  if (event.key === "ArrowRight") nextStep();
}

watch(() => ui.guideOpen, (open) => {
  if (!open) return;
  stepIndex.value = 0;
  void locateStep();
});
watch(stepIndex, () => void locateStep());

onMounted(() => {
  window.addEventListener("resize", updatePosition);
  window.addEventListener("scroll", updatePosition, true);
  window.addEventListener("keydown", onKeydown);
  if (ui.guideOpen) void locateStep();
});

onUnmounted(() => {
  window.removeEventListener("resize", updatePosition);
  window.removeEventListener("scroll", updatePosition, true);
  window.removeEventListener("keydown", onKeydown);
});
</script>

<style scoped>
.guide-tour {
  position: fixed;
  inset: 0;
  z-index: 100;
  pointer-events: none;
}

.guide-mask {
  position: fixed;
  z-index: 100;
  background: rgba(0, 0, 0, 0.7);
  pointer-events: auto;
}

.guide-highlight {
  position: fixed;
  z-index: 101;
  border: 2px solid var(--warning, #ffd15c);
  border-radius: 5px;
  box-shadow: 0 0 0 3px rgba(255, 209, 92, 0.24), 0 8px 30px rgba(0, 0, 0, 0.35);
  pointer-events: auto;
  transition: inset 0.18s ease, width 0.18s ease, height 0.18s ease;
}

.guide-card {
  --guide-arrow-left: 40px;
  position: fixed;
  z-index: 102;
  width: min(380px, calc(100vw - 32px));
  border: 1px solid var(--border-strong, #202020);
  background: var(--panel-bg-raised, #ffffff);
  color: var(--text, #151515);
  box-shadow: 0 18px 55px rgba(0, 0, 0, 0.38);
  pointer-events: auto;
  outline: none;
}

.guide-arrow {
  position: absolute;
  left: calc(var(--guide-arrow-left) - 7px);
  width: 14px;
  height: 14px;
  background: var(--panel-bg-raised, #ffffff);
  transform: rotate(45deg);
}

.guide-card.below .guide-arrow {
  top: -8px;
  border-top: 1px solid var(--border-strong, #202020);
  border-left: 1px solid var(--border-strong, #202020);
}

.guide-card.above .guide-arrow {
  bottom: -8px;
  border-right: 1px solid var(--border-strong, #202020);
  border-bottom: 1px solid var(--border-strong, #202020);
}

header,
footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 15px 17px;
}

header {
  border-bottom: 1px solid var(--border-soft, #c8c8c8);
}

header button {
  border: 0;
  background: transparent;
  color: var(--text, #151515);
  font-size: 22px;
  line-height: 1;
}

h2 {
  margin: 3px 0 0;
  font-size: 17px;
}

.eyebrow {
  color: var(--text-muted, #5b5b5b);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

p {
  min-height: 58px;
  margin: 0;
  padding: 15px 17px 10px;
  color: var(--text-muted, #5b5b5b);
  font-size: 13px;
  line-height: 1.6;
}

.step-progress {
  display: flex;
  gap: 6px;
  padding: 0 17px 14px;
}

.step-progress span {
  width: 22px;
  height: 3px;
  background: var(--border-soft, #c8c8c8);
}

.step-progress span.active {
  background: var(--warning, #8a6500);
}

footer {
  border-top: 1px solid var(--border-soft, #c8c8c8);
}

footer a {
  color: var(--text, #151515);
  font-size: 11px;
}

.guide-actions {
  display: flex;
  gap: 8px;
}

.guide-actions button {
  min-height: 32px;
  padding: 5px 11px;
}

.guide-actions .primary {
  border-color: var(--text, #151515);
  background: var(--text, #151515);
  color: var(--panel-bg, #ffffff);
}

@media (max-width: 540px) {
  footer {
    align-items: flex-end;
  }

  footer a {
    max-width: 90px;
  }
}
</style>
