<template>
  <section class="safety-panel">
    <header>
      <h2>Safety Log</h2>
      <template v-if="safety.summary">
        <span
          v-for="category in categories"
          :key="category.value"
          :class="categoryClass(category.value)"
        >
          {{ category.shortLabel }} {{ categoryCount(category.value) }}
        </span>
      </template>
      <span v-else class="muted">waiting for project</span>
    </header>

    <div class="summary-bar">
      <span class="count">{{ visibleEvents.length }} / {{ safety.events.length }}</span>
      <button :disabled="!hasFilters" @click="clearFilters">clear filters</button>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>
              <button class="th-button" @click="cycleSort('time')">
                time <span>{{ sortGlyph("time") }}</span>
              </button>
            </th>
            <th>
              <button class="th-button" @click="cycleSort('category')">
                class <span>{{ sortGlyph("category") }}</span>
              </button>
            </th>
            <th>
              <button class="th-button" @click="cycleSort('drone')">
                drones <span>{{ sortGlyph("drone") }}</span>
              </button>
            </th>
            <th>
              <button class="th-button" @click="cycleSort('message')">
                message <span>{{ sortGlyph("message") }}</span>
              </button>
            </th>
          </tr>
          <tr class="filter-row">
            <th>
              <select v-model="timeWindow">
                <option value="all">all time</option>
                <option value="first30">0-30s</option>
                <option value="first60">0-60s</option>
                <option value="current">near current</option>
              </select>
            </th>
            <th>
              <select v-model="categoryFilter">
                <option value="all">all classes</option>
                <option v-for="category in categories" :key="category.value" :value="category.value">
                  {{ category.label }}
                </option>
              </select>
            </th>
            <th>
              <input v-model.trim="droneFilter" type="text" placeholder="D1" />
            </th>
            <th>
              <input v-model.trim="query" type="search" placeholder="filter message" />
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="event in visibleEvents"
            :key="event.id"
            :class="{ active: event.id === safety.activeEventId }"
            @click="jumpToEvent(event)"
          >
            <td>{{ formatTime(event.time_ms) }}</td>
            <td :class="categoryClass(event.category)">{{ event.category_label }}</td>
            <td>{{ droneLabel(event) }}</td>
            <td>{{ event.message }}</td>
          </tr>
          <tr v-if="visibleEvents.length === 0">
            <td colspan="4" class="empty">{{ safety.events.length === 0 ? "暂无安全日志" : "没有匹配的安全日志" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import type { SafetyCategory, SafetyEvent } from "../renderer/types";
import { usePlayerStore } from "../stores/player";
import { useSafetyStore } from "../stores/safety";

interface CategoryOption {
  value: SafetyCategory;
  label: string;
  shortLabel: string;
}

const safety = useSafetyStore();
const player = usePlayerStore();
const categoryFilter = ref<"all" | SafetyCategory>("all");
const droneFilter = ref("");
const query = ref("");
const timeWindow = ref<"all" | "first30" | "first60" | "current">("all");
const sortColumn = ref<"time" | "category" | "drone" | "message">("category");
const sortDirection = ref<"asc" | "desc">("desc");

const categories: CategoryOption[] = [
  { value: "distance_17", label: "碰撞警告", shortLabel: "碰撞警告" },
  { value: "distance_34", label: "碰撞风险", shortLabel: "碰撞风险" },
  { value: "distance_51", label: "距离过近", shortLabel: "距离过近" },
  { value: "action_incomplete", label: "动作未完成", shortLabel: "未完成" },
];

const hasFilters = computed(() => {
  return categoryFilter.value !== "all"
    || droneFilter.value !== ""
    || query.value !== ""
    || timeWindow.value !== "all"
    || sortColumn.value !== "category"
    || sortDirection.value !== "desc";
});

const visibleEvents = computed(() => {
  const normalizedDrone = droneFilter.value.replace(/^d/i, "");
  const droneNumber = normalizedDrone === "" ? null : Number(normalizedDrone);
  const textQuery = query.value.toLowerCase();

  const events = safety.events.filter((event) => {
    if (!isInTimeWindow(event)) return false;
    if (categoryFilter.value !== "all" && event.category !== categoryFilter.value) return false;
    if (droneNumber !== null && (event.drone_a !== droneNumber && event.drone_b !== droneNumber)) return false;
    if (textQuery && !`${event.category_label} ${event.message}`.toLowerCase().includes(textQuery)) return false;
    return true;
  });

  return [...events].sort(compareEvents);
});

function compareEvents(a: SafetyEvent, b: SafetyEvent): number {
  let value = 0;
  if (sortColumn.value === "time") {
    value = a.time_ms - b.time_ms;
  } else if (sortColumn.value === "category") {
    value = a.category_rank - b.category_rank || a.time_ms - b.time_ms;
  } else if (sortColumn.value === "drone") {
    value = firstDrone(a) - firstDrone(b) || a.time_ms - b.time_ms;
  } else {
    value = a.message.localeCompare(b.message) || a.time_ms - b.time_ms;
  }
  return sortDirection.value === "asc" ? value : -value;
}

function categoryCount(category: SafetyCategory): number {
  return safety.summary?.category_counts[category] ?? 0;
}

function categoryClass(category: SafetyCategory): string {
  return `category-${category}`;
}

function clearFilters(): void {
  categoryFilter.value = "all";
  droneFilter.value = "";
  query.value = "";
  timeWindow.value = "all";
  sortColumn.value = "category";
  sortDirection.value = "desc";
}

function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)}s`;
}

function droneLabel(event: SafetyEvent): string {
  if (event.drone_a && event.drone_b) {
    return `D${event.drone_a}/D${event.drone_b}`;
  }
  if (event.drone_a) {
    return `D${event.drone_a}`;
  }
  return "-";
}

function firstDrone(event: SafetyEvent): number {
  return event.drone_a ?? event.drone_b ?? Number.POSITIVE_INFINITY;
}

function isInTimeWindow(event: SafetyEvent): boolean {
  if (timeWindow.value === "first30") {
    return event.time_ms <= 30000;
  }
  if (timeWindow.value === "first60") {
    return event.time_ms <= 60000;
  }
  if (timeWindow.value === "current") {
    return Math.abs(event.time_ms - player.currentTimeMs) <= 5000;
  }
  return true;
}

function cycleSort(column: typeof sortColumn.value): void {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
    return;
  }
  sortColumn.value = column;
  sortDirection.value = column === "category" ? "desc" : "asc";
}

function sortGlyph(column: typeof sortColumn.value): string {
  if (sortColumn.value !== column) {
    return "";
  }
  return sortDirection.value === "asc" ? "up" : "down";
}

function jumpToEvent(event: SafetyEvent): void {
  player.pause();
  player.setCurrentTime(event.time_ms);
  safety.setActiveEvent(event.id);
}
</script>

<style scoped>
.safety-panel {
  min-height: 0;
  border-top: 1px solid #efefef;
  background: #0d0d0d;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
}

header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid #303030;
}

h2 {
  margin: 0;
  font-size: 14px;
}

.summary-bar {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  align-items: center;
  padding: 8px 14px;
  border-bottom: 1px solid #303030;
  background: #101010;
}

.summary-bar button {
  justify-self: end;
  padding: 5px 10px;
}

.count {
  color: #8b8b8b;
  font-size: 11px;
}

.table-wrap {
  min-height: 0;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th,
td {
  padding: 7px 10px;
  border-bottom: 1px solid #242424;
  text-align: left;
  vertical-align: top;
}

th {
  position: sticky;
  top: 0;
  background: #121212;
  color: #a8a8a8;
  z-index: 1;
}

.filter-row th {
  top: 31px;
  background: #101010;
}

.filter-row select,
.filter-row input {
  width: 100%;
  min-width: 0;
  border: 1px solid #4a4a4a;
  background: #090909;
  color: #f0f0f0;
  padding: 5px 7px;
}

.th-button {
  width: 100%;
  border: 0;
  background: transparent;
  color: #a8a8a8;
  padding: 0;
  display: flex;
  justify-content: space-between;
  cursor: pointer;
}

.th-button:hover {
  color: #f0f0f0;
  background: transparent;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover,
tbody tr.active {
  background: #241414;
}

td:first-child,
td:nth-child(2),
td:nth-child(3) {
  white-space: nowrap;
}

.category-distance_17 {
  color: #ff3232;
  font-weight: 800;
}

.category-distance_34 {
  color: #ff8a3d;
  font-weight: 700;
}

.category-distance_51 {
  color: #ffd15c;
  font-weight: 700;
}

.category-action_incomplete {
  color: #b8b8b8;
  font-weight: 700;
}

.empty {
  color: #8b8b8b;
  text-align: center;
  cursor: default;
}

@media (max-width: 980px) {
  .summary-bar {
    grid-template-columns: 1fr;
  }
}
</style>
