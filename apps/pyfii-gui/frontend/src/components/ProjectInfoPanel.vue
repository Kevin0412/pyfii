<template>
  <section class="project-info">
    <h2>项目</h2>

    <div v-if="project.meta" class="info-list">
      <div>
        <span>名称</span>
        <strong>{{ project.meta.name }}</strong>
      </div>
      <div>
        <span>项目 ID</span>
        <code>{{ project.meta.project_id }}</code>
      </div>
      <div>
        <span>场地</span>
        <strong>{{ project.meta.field ?? "?" }} 米</strong>
      </div>
      <div>
        <span>机型</span>
        <strong>{{ project.meta.device ?? "未知" }}</strong>
      </div>
      <div>
        <span>无人机</span>
        <strong>{{ project.meta.drone_count }}</strong>
      </div>
      <div>
        <span>时长</span>
        <strong>{{ formatTime(project.meta.duration_ms) }}</strong>
      </div>
      <div>
        <span>帧数</span>
        <strong>{{ project.meta.frame_count }}</strong>
      </div>
      <div>
        <span>安全</span>
        <strong :class="categoryClass(project.meta.safety_summary.max_category)">
          {{ summaryLabel(project.meta.safety_summary.max_category) }}
        </strong>
      </div>
      <div>
        <span>最小距离</span>
        <strong>
          {{ project.meta.safety_summary.min_distance_cm === null ? "-" : `${project.meta.safety_summary.min_distance_cm.toFixed(1)}cm` }}
        </strong>
      </div>
      <div>
        <span>音乐</span>
        <strong>{{ project.meta.music.available ? project.meta.music.files.join(", ") : "无" }}</strong>
      </div>
      <div v-if="project.uploadWarnings.length">
        <span>核心警告</span>
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
  return `${(ms / 1000).toFixed(2)} 秒`;
}

function summaryLabel(category: SafetyCategory | null): string {
  if (category === "distance_17") return "碰撞警告";
  if (category === "distance_34") return "碰撞风险";
  if (category === "distance_51") return "距离过近";
  if (category === "action_incomplete") return "动作未完成";
  return "正常";
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
  color: var(--text-strong);
}

.info-list {
  display: grid;
  gap: 10px;
}

.info-list > div {
  display: grid;
  gap: 3px;
  padding-bottom: 9px;
  border-bottom: 1px solid var(--border-soft);
}

span {
  color: var(--text-muted);
  font-size: 11px;
}

strong,
code {
  color: var(--text-strong);
  font-size: 12px;
  word-break: break-word;
}

.empty {
  color: var(--text-muted);
  line-height: 1.6;
  font-size: 12px;
}

.category-distance_17 {
  color: var(--danger);
}

.category-distance_34 {
  color: var(--risk);
}

.category-distance_51 {
  color: var(--warning);
}

.category-action_incomplete {
  color: var(--neutral);
}
</style>
