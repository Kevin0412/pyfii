<template>
  <section ref="shellRef" class="canvas-shell">
    <div class="canvas-frame" :style="{ width: fw + 'px', height: fh + 'px' }">
      <canvas
        ref="canvas2dRef"
        class="sim-canvas"
        :class="{ active: player.renderMode === 'classic2d' }"
        :width="canvasWidth"
        :height="canvasHeight"
        :style="{ imageRendering: canvasImageRendering }"
        aria-label="Pyfii 2D simulation canvas"
      />
      <canvas
        ref="canvas3dRef"
        class="sim-canvas"
        :class="{ active: player.renderMode === 'three3d' }"
        :width="canvasWidth"
        :height="canvasHeight"
        aria-label="Pyfii 3D simulation canvas"
        @pointerdown="onThreePointerDown"
        @pointermove="onThreePointerMove"
        @pointerup="onThreePointerUp"
        @pointercancel="onThreePointerUp"
        @wheel.prevent="onThreeWheel"
        @contextmenu.prevent
      />
      <div v-if="player.renderMode === 'three3d'" class="three-hud">
        <span>A:{{ player.viewAngleA.toFixed(0) }}</span>
        <span>B:{{ player.viewAngleB.toFixed(0) }}</span>
        <span>T+{{ (player.currentTimeMs / 1000).toFixed(3) }}</span>
        <span>FPS:{{ renderFpsText }}</span>
        <span
          v-for="drone in hudDrones"
          :key="drone.id"
          class="hud-drone"
          :style="{ color: droneColorCss(drone.id) }"
        >
          D{{ drone.id }}({{ drone.xCm.toFixed(0) }},{{ drone.yCm.toFixed(0) }},{{ drone.zCm.toFixed(0) }})
        </span>
      </div>
      <button
        class="fullscreen-btn"
        @click="player.setFullscreen(!player.fullscreen)"
        :title="player.fullscreen ? tt('exitFullscreen') : tt('fullscreen')"
      >{{ player.fullscreen ? '⬚' : '⬙' }}</button>
      <div v-if="exporting" class="export-overlay">
        <div class="export-progress-card">
          <span>{{ tt("exportingVideo") }}</span>
          <div class="export-progress-row">
            <div
              class="export-progress-track"
              :class="{ indeterminate: exportProgress === null }"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-valuenow="exportProgress === null ? undefined : Math.round(exportProgress)"
            >
              <span :style="{ width: exportProgress === null ? undefined : `${exportProgress}%` }" />
            </div>
            <strong>{{ exportProgress === null ? "…" : `${Math.round(exportProgress)}%` }}</strong>
          </div>
          <span class="export-phase">{{ exportPhaseText }}</span>
        </div>
      </div>
      <div v-if="exportMessage" class="export-message" :class="{ error: exportFailed }">
        <span>{{ exportMessage }}</span>
        <button type="button" @click="exportMessage = ''">×</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import { ApiError } from "../api/client";
import {
  createVideoExport,
  fetchVideoExport,
  videoExportDownloadUrl,
  type VideoExportRequest,
} from "../api/projects";
import { text, type MessageKey } from "../i18n";
import { getFrameAtTime } from "../renderer/frame";
import { PyfiiCanvasRenderer } from "../renderer/canvas2d/PyfiiCanvasRenderer";
import { PyfiiThreeRenderer } from "../renderer/three/PyfiiThreeRenderer";
import { droneColor } from "../renderer/palette";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";
import { useUiStore } from "../stores/ui";
import type { RenderInput, ThreeRenderSettings } from "../renderer/types";

const canvas2dRef = ref<HTMLCanvasElement | null>(null);
const canvas3dRef = ref<HTMLCanvasElement | null>(null);
const shellRef = ref<HTMLElement | null>(null);
const fw = ref(0);
const fh = ref(0);
const exporting = ref(false);
const exportProgress = ref<number | null>(0);
const exportStatus = ref<"queued" | "running">("queued");
const exportMessage = ref("");
const exportFailed = ref(false);
const renderFps = ref(0);
const project = useProjectStore();
const player = usePlayerStore();
const safety = useSafetyStore();
const ui = useUiStore();

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}

const canvasWidth = computed(() => Math.max(1, Math.round(1200 * player.renderScale)));
const canvasHeight = computed(() => Math.max(1, Math.round(600 * player.renderScale)));
const canvasImageRendering = computed(() => player.renderScale >= 1 ? "auto" : "pixelated");
const hudFrame = computed(() => getFrameAtTime(project.tracks, player.currentTimeMs));
const hudDrones = computed(() => [...hudFrame.value.drones].sort((a, b) => a.id - b.id));
const renderFpsText = computed(() => renderFps.value > 0 ? renderFps.value.toFixed(1) : project.trackFps.toFixed(1));
const exportPhaseText = computed(() => {
  if (exportStatus.value === "queued") return tt("waitingForRenderer");
  if (exportProgress.value !== null && exportProgress.value >= 95) return tt("finalizingVideo");
  return tt("renderingOnServer");
});

let canvasRenderer: PyfiiCanvasRenderer | null = null;
let threeRenderer: PyfiiThreeRenderer | null = null;
let frameRequest = 0;
let lastTimestamp = 0;
let fpsWindowStart = 0;
let fpsFrames = 0;
let ro: ResizeObserver | null = null;
let dragState: { pointerId: number; x: number; y: number } | null = null;

function droneColorCss(id: number): string {
  return droneColor(id, 0);
}

function sizeFrame(): void {
  const el = shellRef.value;
  if (!el) return;
  const cw = el.clientWidth;
  const ch = el.clientHeight;
  if (cw <= 0 || ch <= 0) return;
  const w = Math.min(cw, ch * 2);
  fw.value = Math.round(w);
  fh.value = Math.round(w / 2);
}

function render(timestamp: number): void {
  if (!lastTimestamp) lastTimestamp = timestamp;
  if (!fpsWindowStart) fpsWindowStart = timestamp;
  const delta = timestamp - lastTimestamp;
  lastTimestamp = timestamp;
  fpsFrames += 1;
  if (timestamp - fpsWindowStart >= 500) {
    renderFps.value = (fpsFrames * 1000) / (timestamp - fpsWindowStart);
    fpsFrames = 0;
    fpsWindowStart = timestamp;
  }

  if (player.playing && !player.seeking && project.durationMs > 0) {
    const nextTime = player.currentTimeMs + delta * player.speed;
    if (nextTime >= project.durationMs) {
      player.setCurrentTime(project.durationMs);
      player.pause();
    } else {
      player.setCurrentTime(nextTime);
    }
  }

  drawActiveRenderer();
  frameRequest = requestAnimationFrame(render);
}

function syncRendererSize(): void {
  canvasRenderer?.applyScale(player.renderScale);
  threeRenderer?.setSize(canvasWidth.value, canvasHeight.value);
}

function threeSettings(): ThreeRenderSettings {
  return {
    projection: player.threeProjection,
    renderScale: player.renderScale,
    viewAngleA: player.viewAngleA,
    viewAngleB: player.viewAngleB,
    observerDistance: player.observerDistance,
    projectionDistance: player.projectionDistance,
  };
}

function drawActiveRenderer(): void {
  const input = buildRenderInput();
  if (player.renderMode === "three3d") {
    threeRenderer?.draw(input, threeSettings());
  } else {
    canvasRenderer?.draw(input);
  }
}

function buildRenderInput(): RenderInput {
  const frame = getFrameAtTime(project.tracks, player.currentTimeMs);
  return {
    meta: project.meta,
    frame,
    tracks: project.tracks,
    safetyEvents: safety.events,
    options: {
      selectedDroneId: player.selectedDroneId,
      showTrail: player.showTrail,
      showSafetyMarkers: player.showSafetyMarkers,
      fps: project.trackFps,
      playing: player.playing,
    },
  };
}

function onFullscreenChange(): void {
  player.setFullscreen(Boolean(document.fullscreenElement));
}

function onThreePointerDown(event: PointerEvent): void {
  if (player.renderMode !== "three3d") return;
  dragState = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
  canvas3dRef.value?.setPointerCapture(event.pointerId);
}

function onThreePointerMove(event: PointerEvent): void {
  if (player.renderMode !== "three3d" || !dragState || dragState.pointerId !== event.pointerId) return;
  const dx = event.clientX - dragState.x;
  const dy = event.clientY - dragState.y;
  dragState = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
  player.setViewAngleA(player.viewAngleA - dx * 0.35);
  player.setViewAngleB(player.viewAngleB - dy * 0.25);
}

function onThreePointerUp(event: PointerEvent): void {
  if (dragState?.pointerId === event.pointerId) {
    dragState = null;
    canvas3dRef.value?.releasePointerCapture(event.pointerId);
  }
}

function onThreeWheel(event: WheelEvent): void {
  if (player.renderMode !== "three3d") return;
  const factor = event.deltaY > 0 ? 0.92 : 1.08;
  player.setProjectionDistance(player.projectionDistance * factor);
}

function waitMs(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function downloadFile(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

async function exportVideo(): Promise<void> {
  if (!project.meta || !project.projectId || project.durationMs <= 0 || exporting.value) return;

  exporting.value = true;
  exportProgress.value = 0;
  exportStatus.value = "queued";
  exportMessage.value = "";
  exportFailed.value = false;

  try {
    const options: VideoExportRequest = {
      render_mode: player.renderMode,
      fps: Math.min(60, Math.max(1, Math.round(project.trackFps))),
      render_scale: player.renderScale >= 2 ? 2 : 1,
      projection: player.threeProjection,
      view_angle_a: player.viewAngleA,
      view_angle_b: player.viewAngleB,
      observer_distance: player.observerDistance,
      projection_distance: player.projectionDistance,
    };
    let job = await createVideoExport(project.projectId, options);
    exportProgress.value = job.progress_percent;
    exportStatus.value = job.status === "queued" ? "queued" : "running";

    while (job.status === "queued" || job.status === "running") {
      await waitMs(750);
      job = await fetchVideoExport(project.projectId, job.export_id);
      exportProgress.value = job.progress_percent;
      if (job.status === "queued" || job.status === "running") {
        exportStatus.value = job.status;
      }
    }

    if (job.status === "failed") {
      throw new Error(job.error || tt("videoExportFailed"));
    }

    downloadFile(videoExportDownloadUrl(project.projectId, job.export_id), job.filename);
    exportMessage.value = job.warnings.length
      ? `${tt("videoExportCompleteWithWarnings")} (${job.warnings.length})`
      : tt("videoExportComplete");
  } catch (error) {
    exportFailed.value = true;
    exportMessage.value = error instanceof ApiError
      ? `${error.code}: ${error.message}`
      : error instanceof Error ? error.message : tt("videoExportFailed");
  } finally {
    exporting.value = false;
    exportProgress.value = 0;
    exportStatus.value = "queued";
  }
}

defineExpose({ exportVideo });

onMounted(() => {
  if (canvas2dRef.value) canvasRenderer = new PyfiiCanvasRenderer(canvas2dRef.value, player.renderScale);
  if (canvas3dRef.value) threeRenderer = new PyfiiThreeRenderer(canvas3dRef.value);
  syncRendererSize();
  document.addEventListener("fullscreenchange", onFullscreenChange);
  ro = new ResizeObserver(() => sizeFrame());
  if (shellRef.value) ro.observe(shellRef.value);
  sizeFrame();
  frameRequest = requestAnimationFrame(render);
});

watch(
  () => [
    player.renderScale,
    player.renderMode,
    player.threeProjection,
    player.viewAngleA,
    player.viewAngleB,
    player.observerDistance,
    player.projectionDistance,
  ],
  () => {
    syncRendererSize();
    drawActiveRenderer();
  },
);

onUnmounted(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  ro?.disconnect();
  cancelAnimationFrame(frameRequest);
  threeRenderer?.dispose();
});
</script>

<style scoped>
.canvas-shell {
  contain: strict;
  min-height: 0;
  min-width: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
}

.canvas-frame {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--border-strong);
  background: #000;
}

.sim-canvas {
  display: block;
  width: 100%;
  height: 100%;
  opacity: 0;
  pointer-events: none;
}

.sim-canvas:not(:first-child) {
  position: absolute;
  inset: 0;
}

.sim-canvas.active {
  opacity: 1;
  pointer-events: auto;
}

.sim-canvas[aria-label="Pyfii 3D simulation canvas"].active {
  cursor: grab;
}

.sim-canvas[aria-label="Pyfii 3D simulation canvas"].active:active {
  cursor: grabbing;
}

.three-hud {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 8;
  display: grid;
  row-gap: 10px;
  padding: 0;
  color: #ffffff;
  font-family: "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 14px;
  font-weight: 400;
  line-height: 20px;
  pointer-events: none;
}

.fullscreen-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
  opacity: 0.35;
  background: var(--control-bg);
  border: 1px solid var(--border-control);
  color: var(--text);
  font-size: 16px;
  padding: 4px 8px;
  cursor: pointer;
  transition: opacity 0.2s;
  line-height: 1;
}

.canvas-frame:hover .fullscreen-btn,
.fullscreen-btn:focus-visible { opacity: 1; }

.export-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.75);
  z-index: 20;
}

.export-progress-card {
  background: var(--panel-bg-raised);
  border: 1px solid var(--border-control);
  padding: 24px 36px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.export-progress-row {
  width: min(320px, 70vw);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  align-items: center;
  gap: 12px;
}

.export-progress-row strong {
  text-align: right;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.export-progress-track {
  height: 10px;
  overflow: hidden;
  border: 1px solid var(--border-control);
  background: var(--panel-bg-alt);
}

.export-progress-track span {
  display: block;
  height: 100%;
  background: var(--text-strong);
  transition: width 0.25s ease;
}

.export-progress-track.indeterminate span {
  width: 38%;
  animation: export-progress-slide 1.1s ease-in-out infinite;
}

.export-phase {
  color: var(--text-muted);
  font-size: 11px;
}

@keyframes export-progress-slide {
  from { transform: translateX(-110%); }
  to { transform: translateX(270%); }
}

.export-message {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 21;
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: min(520px, calc(100% - 24px));
  padding: 9px 12px;
  border: 1px solid var(--ok);
  color: var(--text);
  background: var(--panel-bg-raised);
  font-size: 12px;
}

.export-message.error {
  border-color: var(--danger);
}

.export-message button {
  border: 0;
  color: inherit;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
}
</style>
