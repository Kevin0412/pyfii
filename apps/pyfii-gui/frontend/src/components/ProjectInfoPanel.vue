<template>
  <section class="project-info">
    <h2>Project</h2>

    <div v-if="project.meta" class="info-list">
      <div>
        <span>name</span>
        <strong>{{ project.meta.name }}</strong>
      </div>
      <div>
        <span>project_id</span>
        <code>{{ project.meta.project_id }}</code>
      </div>
      <div>
        <span>field</span>
        <strong>{{ project.meta.field ?? "?" }}m</strong>
      </div>
      <div>
        <span>device</span>
        <strong>{{ project.meta.device ?? "unknown" }}</strong>
      </div>
      <div>
        <span>drones</span>
        <strong>{{ project.meta.drone_count }}</strong>
      </div>
      <div>
        <span>duration</span>
        <strong>{{ formatTime(project.meta.duration_ms) }}</strong>
      </div>
      <div>
        <span>frames</span>
        <strong>{{ project.meta.frame_count }}</strong>
      </div>
      <div>
        <span>safety</span>
        <strong :class="categoryClass(project.meta.safety_summary.max_category)">
          {{ summaryLabel(project.meta.safety_summary.max_category) }}
        </strong>
      </div>
      <div>
        <span>min distance</span>
        <strong>
          {{ project.meta.safety_summary.min_distance_cm === null ? "-" : `${project.meta.safety_summary.min_distance_cm.toFixed(1)}cm` }}
        </strong>
      </div>
      <div>
        <span>music</span>
        <strong>{{ project.meta.music.available ? project.meta.music.files.join(", ") : "none" }}</strong>
      </div>
      <div v-if="project.uploadWarnings.length">
        <span>core warnings</span>
        <strong class="level-warning">{{ project.uploadWarnings.length }}</strong>
      </div>
    </div>

    <div v-else class="empty">
      选择一个 Fii 项目 zip 后，这里会显示 field、device、无人机数量和安全概要。
    </div>
  </section>
</template>

<script setup lang="ts">
import { useProjectStore } from "../stores/project";
import type { SafetyCategory } from "../renderer/types";

const project = useProjectStore();

function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)}s`;
}

function summaryLabel(category: SafetyCategory | null): string {
  if (category === "distance_17") return "碰撞警告";
  if (category === "distance_34") return "碰撞风险";
  if (category === "distance_51") return "距离过近";
  if (category === "action_incomplete") return "动作未完成";
  return "ok";
}

function categoryClass(category: SafetyCategory | null): string {
  return category ? `category-${category}` : "level-ok";
}
</script>

<style scoped>
.project-info {
  padding: 16px;
}

h2 {
  margin: 0 0 14px;
  font-size: 15px;
  font-weight: 700;
  color: #f3f3f3;
}

.info-list {
  display: grid;
  gap: 10px;
}

.info-list > div {
  display: grid;
  gap: 3px;
  padding-bottom: 9px;
  border-bottom: 1px solid #303030;
}

span {
  color: #8d8d8d;
  font-size: 11px;
}

strong,
code {
  color: #f2f2f2;
  font-size: 12px;
  word-break: break-word;
}

.empty {
  color: #8d8d8d;
  line-height: 1.6;
  font-size: 12px;
}

.category-distance_17 {
  color: #ff3232;
}

.category-distance_34 {
  color: #ff8a3d;
}

.category-distance_51 {
  color: #ffd15c;
}

.category-action_incomplete {
  color: #b8b8b8;
}
</style>
