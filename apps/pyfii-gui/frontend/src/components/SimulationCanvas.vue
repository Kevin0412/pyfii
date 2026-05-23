<template>
  <section class="canvas-shell">
    <div class="canvas-frame">
      <canvas
        ref="canvasRef"
        :width="canvasWidth"
        :height="canvasHeight"
        :style="{ imageRendering: canvasImageRendering }"
        aria-label="Pyfii 2D simulation canvas"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import { getFrameAtTime } from "../renderer/frame";
import { PyfiiCanvasRenderer } from "../renderer/canvas2d/PyfiiCanvasRenderer";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";

const canvasRef = ref<HTMLCanvasElement | null>(null);
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
    renderer.draw({
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
    });
  }

  frameRequest = requestAnimationFrame(render);
}

onMounted(() => {
  if (canvasRef.value) {
    renderer = new PyfiiCanvasRenderer(canvasRef.value, player.renderScale);
  }
  frameRequest = requestAnimationFrame(render);
});

watch(() => player.renderScale, (newScale) => {
  renderer?.applyScale(newScale);
});

onUnmounted(() => {
  cancelAnimationFrame(frameRequest);
});
</script>

<style scoped>
.canvas-shell {
  min-height: 0;
  display: grid;
  align-items: center;
  justify-items: center;
  padding: 14px;
  overflow: auto;
}

.canvas-frame {
  width: min(100%, 1200px);
  aspect-ratio: 2 / 1;
  border: 1px solid #f0f0f0;
  background: #000;
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
