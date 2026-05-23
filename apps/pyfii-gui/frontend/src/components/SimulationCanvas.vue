<template>
  <section ref="shellRef" class="canvas-shell">
    <div class="canvas-frame" :style="{ width: fw + 'px', height: fh + 'px' }">
      <canvas
        ref="canvasRef"
        :width="canvasWidth"
        :height="canvasHeight"
        :style="{ imageRendering: canvasImageRendering }"
        aria-label="Pyfii 2D simulation canvas"
      />
      <button
        class="fullscreen-btn"
        @click="player.setFullscreen(!player.fullscreen)"
        :title="player.fullscreen ? 'Exit fullscreen' : 'Fullscreen'"
      >{{ player.fullscreen ? '⬚' : '⬙' }}</button>
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

import { projectMusicUrl } from "../api/projects";
import { getFrameAtTime } from "../renderer/frame";
import { PyfiiCanvasRenderer } from "../renderer/canvas2d/PyfiiCanvasRenderer";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";
import type { RenderInput } from "../renderer/types";

const canvasRef = ref<HTMLCanvasElement | null>(null);
const shellRef = ref<HTMLElement | null>(null);
const fw = ref(0);
const fh = ref(0);
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
let ro: ResizeObserver | null = null;

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

  if (renderer) renderer.draw(buildRenderInput());
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
  player.setFullscreen(Boolean(document.fullscreenElement));
}

function waitMs(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function waitForPaint(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

function waitForAudioReady(audio: HTMLAudioElement): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      audio.oncanplaythrough = null;
      audio.onerror = null;
    };
    audio.oncanplaythrough = () => {
      cleanup();
      resolve();
    };
    audio.onerror = () => {
      cleanup();
      reject(new Error("audio load failed"));
    };
    audio.load();
  });
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function exportVideo(): Promise<void> {
  const canvas = canvasRef.value;
  if (!canvas || !project.meta || project.durationMs <= 0 || exporting.value) return;

  const captureFps = Math.min(project.trackFps, 60);
  const frameIntervalMs = 1000 / captureFps;
  const totalFrames = Math.ceil(project.durationMs / frameIntervalMs);
  const durationMs = project.durationMs;
  let stream = canvas.captureStream(captureFps);
  const streamTracks: MediaStreamTrack[] = [...stream.getTracks()];
  let audioEl: HTMLAudioElement | null = null;
  let audioCtx: AudioContext | null = null;
  let audioSource: MediaElementAudioSourceNode | null = null;
  let audioDest: MediaStreamAudioDestinationNode | null = null;

  if (project.projectId && project.meta.music.available) {
    try {
      const musicUrl = projectMusicUrl(project.projectId);
      audioEl = new Audio(musicUrl);
      audioEl.preload = "auto";
      await waitForAudioReady(audioEl);
      audioCtx = new AudioContext();
      audioSource = audioCtx.createMediaElementSource(audioEl);
      audioDest = audioCtx.createMediaStreamDestination();
      audioSource.connect(audioDest);
      stream = new MediaStream([
        ...stream.getVideoTracks(),
        ...audioDest.stream.getAudioTracks(),
      ]);
      streamTracks.push(...audioDest.stream.getTracks());
    } catch {
      audioEl = null;
      audioCtx?.close();
      audioCtx = null;
      audioSource = null;
      audioDest = null;
    }
  }

  let mimeType = "";
  for (const candidate of ["video/webm; codecs=vp9,opus", "video/webm; codecs=vp8,opus", "video/webm"]) {
    if (MediaRecorder.isTypeSupported(candidate)) { mimeType = candidate; break; }
  }

  const chunks: Blob[] = [];
  const recorderOptions: MediaRecorderOptions = { videoBitsPerSecond: 8000000 };
  if (mimeType) {
    recorderOptions.mimeType = mimeType;
  }
  const recorder = new MediaRecorder(stream, recorderOptions);
  recorder.ondataavailable = (e: BlobEvent) => { if (e.data.size > 0) chunks.push(e.data); };

  const wasPlaying = player.playing;
  const savedTime = player.currentTimeMs;
  const savedScale = player.renderScale;

  if (player.renderScale < 1) {
    player.setRenderScale(1);
    renderer?.applyScale(1);
    await nextTick();
  }

  player.pause();
  player.setCurrentTime(0);
  await nextTick();
  cancelAnimationFrame(frameRequest);

  const exportComplete = new Promise<Blob>((resolve, reject) => {
    recorder.onstop = () => {
      resolve(new Blob(chunks, { type: mimeType || "video/webm" }));
    };
    recorder.onerror = () => {
      reject(new Error("MediaRecorder failed."));
    };
  });

  exporting.value = true;
  exportProgress.value = 0;

  try {
    recorder.start(250);

    if (audioEl) {
      audioEl.currentTime = 0;
      await audioCtx?.resume();
      await audioEl.play();
    }

    for (let i = 0; i <= totalFrames; i += 1) {
      const simTime = Math.min(i * frameIntervalMs, durationMs);
      player.setCurrentTime(simTime);
      renderer?.draw(buildRenderInput());
      exportProgress.value = durationMs > 0 ? (simTime / durationMs) * 100 : 100;
      await waitForPaint();
      if (i < totalFrames) {
        await waitMs(frameIntervalMs);
      }
    }

    audioEl?.pause();
    if (recorder.state !== "inactive") {
      recorder.stop();
    }
    const blob = await exportComplete;
    downloadBlob(blob, `${project.meta?.name ?? "simulation"}.webm`);
  } catch (error) {
    console.error(error);
    audioEl?.pause();
    if (recorder.state !== "inactive") {
      recorder.stop();
    }
  } finally {
    audioSource?.disconnect();
    audioDest?.disconnect();
    await audioCtx?.close();
    streamTracks.forEach((track) => track.stop());
    player.setCurrentTime(savedTime);
    if (player.renderScale !== savedScale) {
      player.setRenderScale(savedScale);
      renderer?.applyScale(savedScale);
    }
    if (wasPlaying) {
      player.play();
    }
    exporting.value = false;
    exportProgress.value = 0;
    frameRequest = requestAnimationFrame(render);
  }
}

defineExpose({ exportVideo });

onMounted(() => {
  if (canvasRef.value) renderer = new PyfiiCanvasRenderer(canvasRef.value, player.renderScale);
  document.addEventListener("fullscreenchange", onFullscreenChange);
  ro = new ResizeObserver(() => sizeFrame());
  if (shellRef.value) ro.observe(shellRef.value);
  sizeFrame();
  frameRequest = requestAnimationFrame(render);
});

watch(() => player.renderScale, (newScale) => renderer?.applyScale(newScale));

onUnmounted(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  ro?.disconnect();
  cancelAnimationFrame(frameRequest);
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
