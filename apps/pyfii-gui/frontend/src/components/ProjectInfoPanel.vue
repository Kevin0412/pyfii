<template>
  <section class="project-info">
    <h2>{{ tt("project") }}</h2>

    <div v-if="project.meta" class="info-list">
      <div>
        <span>{{ tt("name") }}</span>
        <strong>{{ project.meta.name }}</strong>
      </div>
      <div>
        <span>{{ tt("projectId") }}</span>
        <code>{{ project.meta.project_id }}</code>
      </div>
      <div>
        <span>{{ tt("field") }}</span>
        <strong>{{ project.meta.field ?? "?" }} {{ tt("meterUnit") }}</strong>
      </div>
      <div>
        <span>{{ tt("device") }}</span>
        <strong>{{ project.meta.device ?? tt("unknown") }}</strong>
      </div>
      <div>
        <span>{{ tt("drones") }}</span>
        <strong>{{ project.meta.drone_count }}</strong>
      </div>
      <div>
        <span>{{ tt("duration") }}</span>
        <strong>{{ formatTime(project.meta.duration_ms) }}</strong>
      </div>
      <div>
        <span>{{ tt("frames") }}</span>
        <strong>{{ project.meta.frame_count }}</strong>
      </div>
      <div>
        <span>{{ tt("safety") }}</span>
        <strong :class="categoryClass(project.meta.safety_summary.max_category)">
          {{ summaryLabel(project.meta.safety_summary.max_category) }}
        </strong>
      </div>
      <div>
        <span>{{ tt("minDistance") }}</span>
        <strong>
          {{ project.meta.safety_summary.min_distance_cm === null ? "-" : `${project.meta.safety_summary.min_distance_cm.toFixed(1)} ${tt("centimeterUnit")}` }}
        </strong>
      </div>
      <div>
        <span>{{ tt("music") }}</span>
        <strong>{{ project.meta.music.available ? project.meta.music.files.join(", ") : tt("none") }}</strong>
      </div>
      <div v-if="project.uploadWarnings.length">
        <span>{{ tt("coreWarnings") }}</span>
        <strong class="level-warning">{{ project.uploadWarnings.length }}</strong>
      </div>
    </div>

    <div v-else class="empty">
      {{ tt("projectEmpty") }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { useProjectStore } from "../stores/project";
import type { SafetyCategory } from "../renderer/types";
import { safetyCategoryLabel, text, type MessageKey } from "../i18n";
import { useUiStore } from "../stores/ui";

const project = useProjectStore();
const ui = useUiStore();

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}

function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)} ${tt("secondUnit")}`;
}

function summaryLabel(category: SafetyCategory | null): string {
  return category ? safetyCategoryLabel(ui.locale, category) : tt("ok");
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
