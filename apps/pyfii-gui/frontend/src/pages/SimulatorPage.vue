<template>
  <div class="sim-page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-title">Pyfii GUI</span>
        <span class="brand-subtitle">Simulator</span>
      </div>
      <label class="scale-select">
        Scale
        <select v-model.number="player.renderScale">
          <option :value="0.5">0.5x</option>
          <option :value="1">1x</option>
          <option :value="2">2x</option>
          <option :value="4">4x</option>
        </select>
      </label>
      <label class="scale-select">
        Render
        <select v-model="player.renderMode">
          <option value="classic2d">2D classic</option>
          <option value="three3d">3D</option>
        </select>
      </label>
      <template v-if="player.renderMode === 'three3d'">
        <label class="scale-select">
          Camera
          <select v-model="player.threeProjection">
            <option value="orthographic">orthographic</option>
            <option value="perspective">perspective</option>
          </select>
        </label>
        <label class="compact-input">
          A
          <input v-model.number="player.viewAngleA" type="number" min="-180" max="180" step="5" />
        </label>
        <label class="compact-input">
          B
          <input v-model.number="player.viewAngleB" type="number" min="-90" max="90" step="5" />
        </label>
        <label class="compact-input">
          Obs
          <input v-model.number="player.observerDistance" type="number" min="50" step="50" />
        </label>
        <label class="compact-input">
          Proj
          <input v-model.number="player.projectionDistance" type="number" min="50" step="50" />
        </label>
        <button class="view-reset" @click="player.resetJudgeView()">Judge</button>
      </template>
      <ProjectUpload />
      <button
        class="export-btn"
        :disabled="!project.hasProject"
        @click="simCanvasRef?.exportVideo()"
      >Export WebM</button>
    </header>

    <main class="workspace">
      <aside class="project-column">
        <ProjectInfoPanel />
      </aside>
      <section ref="simColumnRef" class="simulation-column" :class="{ fullscreen: player.fullscreen }">
        <SimulationCanvas ref="simCanvasRef" />
        <TimelineControl />
      </section>
    </main>

    <SafetyLogPanel />
  </div>
</template>

<script setup lang="ts">
import ProjectInfoPanel from "../components/ProjectInfoPanel.vue";
import ProjectUpload from "../components/ProjectUpload.vue";
import SafetyLogPanel from "../components/SafetyLogPanel.vue";
import SimulationCanvas from "../components/SimulationCanvas.vue";
import TimelineControl from "../components/TimelineControl.vue";
import { onMounted, onUnmounted, ref, watch } from "vue";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";

const simCanvasRef = ref<InstanceType<typeof SimulationCanvas> | null>(null);
const simColumnRef = ref<HTMLElement | null>(null);
const player = usePlayerStore();
const project = useProjectStore();

function onFullscreenChange(): void {
  if (!document.fullscreenElement) {
    player.setFullscreen(false);
  }
}

watch(() => player.fullscreen, async (v) => {
  if (v && !document.fullscreenElement) {
    try {
      await simColumnRef.value?.requestFullscreen();
    } catch { /* user denied or unsupported */ }
  } else if (!v && document.fullscreenElement) {
    await document.exitFullscreen();
  }
});

onMounted(() => {
  document.addEventListener("fullscreenchange", onFullscreenChange);
});

onUnmounted(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
});
</script>

<style scoped>
.sim-page {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) minmax(180px, 28vh);
  background: #090909;
  color: #efefef;
}

.topbar {
  min-height: 56px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 14px;
  border-bottom: 1px solid #efefef;
  background: #0e0e0e;
}

.brand {
  min-width: 170px;
  display: grid;
  gap: 2px;
}

.brand-title {
  font-size: 18px;
  letter-spacing: 0;
}

.brand-subtitle {
  color: #858585;
  font-size: 11px;
}

.scale-select,
.compact-input {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #cfcfcf;
  font-size: 12px;
}

.compact-input input {
  width: 64px;
  border: 1px solid #d8d8d8;
  background: #141414;
  color: #f0f0f0;
  padding: 6px 7px;
}

.view-reset {
  padding: 6px 10px;
}

.export-btn {
  margin-left: auto;
}

.workspace {
  min-height: 0;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
}

.project-column {
  border-right: 1px solid #d8d8d8;
  background: #101010;
  overflow: auto;
}

.simulation-column {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  background: #050505;
}

.simulation-column.fullscreen {
  background: #000;
}

@media (max-width: 900px) {
  .sim-page {
    grid-template-rows: auto auto minmax(180px, 34vh);
  }

  .topbar {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .project-column {
    border-right: 0;
    border-bottom: 1px solid #d8d8d8;
  }
}
</style>
