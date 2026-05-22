<template>
  <div class="sim-page">
    <header class="topbar">
      <div class="brand">
        <span class="brand-title">Pyfii GUI</span>
        <span class="brand-subtitle">MVP Simulator</span>
      </div>
      <ProjectUpload />
      <button class="export-placeholder" disabled title="TODO: WebM / Electron + ffmpeg MP4 export">
        Export TODO
      </button>
    </header>

    <main class="workspace">
      <aside class="project-column">
        <ProjectInfoPanel />
      </aside>
      <section class="simulation-column">
        <SimulationCanvas />
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

.export-placeholder {
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
