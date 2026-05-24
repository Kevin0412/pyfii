<template>
  <div class="sim-page" :class="`theme-${ui.theme}`">
    <header class="topbar">
      <div class="brand">
        <span class="brand-title">Pyfii GUI</span>
        <span class="brand-subtitle">仿真器</span>
      </div>
      <button
        class="theme-toggle"
        type="button"
        :aria-pressed="ui.theme === 'light'"
        @click="ui.toggleTheme()"
      >
        {{ ui.theme === "dark" ? "浅色" : "深色" }}
      </button>
      <label class="scale-select">
        缩放
        <select v-model.number="player.renderScale">
          <option :value="0.5">0.5 倍</option>
          <option :value="1">1 倍</option>
          <option :value="2">2 倍</option>
          <option :value="4">4 倍</option>
        </select>
      </label>
      <label class="scale-select">
        视图
        <select v-model="player.renderMode">
          <option value="classic2d">经典 2D</option>
          <option value="three3d">三维 3D</option>
        </select>
      </label>
      <template v-if="player.renderMode === 'three3d'">
        <label class="scale-select">
          相机
          <select v-model="player.threeProjection">
            <option value="orthographic">正交</option>
            <option value="perspective">透视</option>
          </select>
        </label>
        <label class="compact-input">
          水平
          <input v-model.number="player.viewAngleA" type="number" min="-180" max="180" step="5" />
        </label>
        <label class="compact-input">
          俯仰
          <input v-model.number="player.viewAngleB" type="number" min="-90" max="90" step="5" />
        </label>
        <label class="compact-input">
          观察距
          <input v-model.number="player.observerDistance" type="number" min="50" step="50" />
        </label>
        <label class="compact-input">
          投影距
          <input v-model.number="player.projectionDistance" type="number" min="50" step="50" />
        </label>
        <button class="view-reset" type="button" @click="player.resetThreeView()">重置视角</button>
      </template>
      <ProjectUpload />
      <button
        class="export-btn"
        :disabled="!project.hasProject"
        @click="simCanvasRef?.exportVideo()"
      >导出 WebM</button>
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
import { useUiStore } from "../stores/ui";

const simCanvasRef = ref<InstanceType<typeof SimulationCanvas> | null>(null);
const simColumnRef = ref<HTMLElement | null>(null);
const player = usePlayerStore();
const project = useProjectStore();
const ui = useUiStore();

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
  --app-bg: #090909;
  --panel-bg: #101010;
  --panel-bg-alt: #0e0e0e;
  --panel-bg-raised: #141414;
  --simulation-bg: #050505;
  --fullscreen-bg: #000;
  --border-strong: #efefef;
  --border-soft: #303030;
  --border-control: #d8d8d8;
  --text: #efefef;
  --text-strong: #f3f3f3;
  --text-muted: #8d8d8d;
  --text-subtle: #858585;
  --control-bg: #141414;
  --control-hover-bg: #202020;
  --control-disabled: #777;
  --danger: #ff3232;
  --risk: #ff8a3d;
  --warning: #ffd15c;
  --ok: #42d47d;
  --neutral: #b8b8b8;
  --danger-bg: #241414;
  --table-header-bg: #121212;
  --shadow: rgba(0, 0, 0, 0.45);
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) minmax(180px, 28vh);
  background: var(--app-bg);
  color: var(--text);
}

.theme-light {
  --app-bg: #f3f3f3;
  --panel-bg: #ffffff;
  --panel-bg-alt: #ededed;
  --panel-bg-raised: #f8f8f8;
  --simulation-bg: #dedede;
  --fullscreen-bg: #000;
  --border-strong: #202020;
  --border-soft: #c8c8c8;
  --border-control: #555555;
  --text: #151515;
  --text-strong: #050505;
  --text-muted: #5b5b5b;
  --text-subtle: #686868;
  --control-bg: #ffffff;
  --control-hover-bg: #e7e7e7;
  --control-disabled: #8c8c8c;
  --danger: #b90000;
  --risk: #bd4c00;
  --warning: #8a6500;
  --ok: #007333;
  --neutral: #606060;
  --danger-bg: #ffe5e5;
  --table-header-bg: #e9e9e9;
  --shadow: rgba(0, 0, 0, 0.18);
}

.topbar {
  min-height: 56px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-strong);
  background: var(--panel-bg-alt);
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
  color: var(--text-subtle);
  font-size: 11px;
}

.theme-toggle {
  min-width: 64px;
}

.scale-select,
.compact-input {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-size: 12px;
}

.compact-input input {
  width: 72px;
  border: 1px solid var(--border-control);
  background: var(--control-bg);
  color: var(--text);
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
  border-right: 1px solid var(--border-control);
  background: var(--panel-bg);
  overflow: auto;
}

.simulation-column {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  background: var(--simulation-bg);
}

.simulation-column.fullscreen {
  background: var(--fullscreen-bg);
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
    border-bottom: 1px solid var(--border-control);
  }
}
</style>
