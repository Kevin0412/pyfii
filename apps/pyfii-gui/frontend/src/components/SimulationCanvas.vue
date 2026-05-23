<template>
  <section ref="canvasShellRef" class="canvas-shell" :class="{ fullscreen: isFullscreen }">
    <div class="canvas-frame">
      <canvas
        ref="canvasRef"
        :width="canvasWidth"
        :height="canvasHeight"
        :style="{ imageRendering: canvasImageRendering }"
        aria-label="Pyfii 2D simulation canvas"
      />
      <button
        class="fullscreen-btn"
        @click="toggleFullscreen"
        :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen'"
      >{{ isFullscreen ? '⬚' : '⬙' }}</button>
      <div v-if="exporting" class="export-overlay">
        <div class="export-progress-card">
          <span>Exporting WebM...</span>
          <progress :value="exportProgress" max="100" />
          <span>{{ Math.round(exportProgress) }}%</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

import { getFrameAtTime } from "../renderer/frame";
import { PyfiiCanvasRenderer } from "../renderer/canvas2d/PyfiiCanvasRenderer";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";
import type { RenderInput } from "../renderer/types";

const canvasRef = ref<HTMLCanvasElement | null>(null);
const canvasShellRef = ref<HTMLElement | null>(null);
const isFullscreen = ref(false);
const exporting = ref(false);
const exportProgress = ref(0);
const project = useProjectStore();
const player = usePlayerStore();
const safety = useSafetyStore();

const canvasWidth = computed(() => Math.max(1, Math.round(1200 * player.renderScale)));
const canvasHeight = computed(() => Math.max(1, Math.round(600 * player.renderScale)));
const canvasImageRendering = computed(() => player.renderScale >= 1 ? "auto" : "pixelated");

let renderer: PyfiiCanvasRenderer | null = null;
let frameRequest = 0;
let lastTimestamp = 0;

function render(timestamp: number): void {
  if (!lastTimestamp) {
    lastTimestamp = timestamp;
  }

  const delta = timestamp - lastTimestamp;
  lastTimestamp = timestamp;

  if (player.playing && !player.seeking && project.durationMs > 0) {
    const nextTime = player.currentTimeMs + delta * player.speed;
    if (nextTime >= project.durationMs) {
      player.setCurrentTime(project.durationMs);
      player.pause();
    } else {
      player.setCurrentTime(nextTime);
    }
  }

  if (renderer) {
    const frame = getFrameAtTime(project.tracks, player.currentTimeMs);
    renderer.draw(buildRenderInput());
  }

  frameRequest = requestAnimationFrame(render);
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
  isFullscreen.value = Boolean(document.fullscreenElement);
}

async function toggleFullscreen(): Promise<void> {
  if (isFullscreen.value) {
    await document.exitFullscreen();
  } else {
    await canvasShellRef.value?.requestFullscreen();
  }
}

async function exportVideo(): Promise<void> {
  const canvas = canvasRef.value;
  if (!canvas || !project.meta) return;

  const outputFps = Math.min(project.trackFps, 60);
  const stream = canvas.captureStream(outputFps);

  let mimeType = "";
  for (const candidate of [
    "video/webm; codecs=vp9",
    "video/webm; codecs=vp8",
    "video/webm",
  ]) {
    if (MediaRecorder.isTypeSupported(candidate)) {
      mimeType = candidate;
      break;
    }
  }

  const chunks: Blob[] = [];
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 8000000 });

  recorder.ondataavailable = (e: BlobEvent) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  const wasPlaying = player.playing;
  const savedTime = player.currentTimeMs;
  const savedScale = player.renderScale;

  // Ensure at least 1x scale for export quality
  if (player.renderScale < 1) {
    player.setRenderScale(1);
    renderer?.applyScale(1);
    await nextTick();
  }

  player.pause();
  player.setCurrentTime(0);
  await nextTick();

  cancelAnimationFrame(frameRequest);

  const durationMs = project.durationMs;

  const exportComplete = new Promise<void>((resolve) => {
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${project.meta?.name ?? "simulation"}.webm`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      player.setCurrentTime(savedTime);
      if (wasPlaying) player.play();

      if (player.renderScale !== savedScale) {
        player.setRenderScale(savedScale);
        renderer?.applyScale(savedScale);
      }

      exporting.value = false;
      exportProgress.value = 0;
      frameRequest = requestAnimationFrame(render);
      resolve();
    };

    recorder.start(100);
  });

  exporting.value = true;
  exportProgress.value = 0;

  function exportLoop(_timestamp: number): void {
    const simTime = player.currentTimeMs;
    if (simTime >= durationMs) {
      renderer?.draw(buildRenderInput());
      recorder.stop();
      return;
    }

    renderer?.draw(buildRenderInput());
    exportProgress.value = (simTime / durationMs) * 100;

    const frameIntervalMs = 1000 / outputFps;
    player.setCurrentTime(Math.min(simTime + frameIntervalMs, durationMs));

    requestAnimationFrame(exportLoop);
  }

  requestAnimationFrame(exportLoop);
  await exportComplete;
}

defineExpose({ exportVideo });

onMounted(() => {
  if (canvasRef.value) {
    renderer = new PyfiiCanvasRenderer(canvasRef.value, player.renderScale);
  }
  document.addEventListener("fullscreenchange", onFullscreenChange);
  frameRequest = requestAnimationFrame(render);
});

watch(() => player.renderScale, (newScale) => {
  renderer?.applyScale(newScale);
});

onUnmounted(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  cancelAnimationFrame(frameRequest);
});
</script>

<style scoped>
.canvas-shell {
  min-height: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
}

.canvas-shell.fullscreen {
  padding: 0;
  background: #000;
}

.canvas-shell.fullscreen .canvas-frame {
  width: 100vw;
  height: 100vh;
  max-width: none;
  border: none;
}

.canvas-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 1;
  border: 1px solid #f0f0f0;
  background: #000;
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.fullscreen-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
  opacity: 0.35;
  background: #141414;
  border: 1px solid #555;
  color: #f0f0f0;
  font-size: 16px;
  padding: 4px 8px;
  cursor: pointer;
  transition: opacity 0.2s;
  line-height: 1;
}

.canvas-frame:hover .fullscreen-btn,
.fullscreen-btn:focus-visible {
  opacity: 1;
}

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
  background: #141414;
  border: 1px solid #555;
  padding: 24px 36px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.export-progress-card progress {
  width: 240px;
  height: 8px;
}
</style>
