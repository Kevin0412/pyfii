<template>
  <section class="safety-panel">
    <header>
      <h2>{{ tt("safetyLog") }}</h2>
      <template v-if="safety.summary">
        <span
          v-for="category in categories"
          :key="category.value"
          :class="categoryClass(category.value)"
        >
          {{ categoryLabel(category.value, true) }} {{ categoryCount(category.value) }}
        </span>
      </template>
      <span v-else class="muted">{{ tt("waitingForProject") }}</span>
    </header>

    <div class="summary-bar">
      <span class="count">{{ visibleEvents.length }} / {{ safety.events.length }}</span>
      <button :disabled="!hasFilters" @click="clearFilters">{{ tt("clearFilters") }}</button>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>
              <button class="th-button" @click="cycleSort('time')">
                {{ tt("time") }} <span>{{ sortGlyph("time") }}</span>
              </button>
            </th>
            <th>
              <button class="th-button" @click="cycleSort('category')">
                {{ tt("category") }} <span>{{ sortGlyph("category") }}</span>
              </button>
            </th>
            <th>
              <button class="th-button" @click="cycleSort('drone')">
                {{ tt("drones") }} <span>{{ sortGlyph("drone") }}</span>
              </button>
            </th>
            <th>
              <button class="th-button" @click="cycleSort('message')">
                {{ tt("message") }} <span>{{ sortGlyph("message") }}</span>
              </button>
            </th>
          </tr>
          <tr class="filter-row">
            <th>
              <select v-model="timeWindow">
                <option value="all">{{ tt("allTime") }}</option>
                <option value="current">{{ tt("nearCurrent") }}</option>
              </select>
            </th>
            <th>
              <select v-model="categoryFilter">
                <option value="all">{{ tt("allClasses") }}</option>
                <option v-for="category in categories" :key="category.value" :value="category.value">
                  {{ categoryLabel(category.value) }}
                </option>
              </select>
            </th>
            <th>
              <details class="multi-select">
                <summary>{{ droneFilterLabel }}</summary>
                <div class="multi-menu">
                  <label v-for="droneId in availableDrones" :key="droneId">
                    <input v-model="selectedDroneIds" type="checkbox" :value="droneId" />
                    D{{ droneId }}
                  </label>
                  <span v-if="availableDrones.length === 0" class="empty-option">{{ tt("noDrones") }}</span>
                </div>
              </details>
            </th>
            <th>
              <input v-model.trim="query" type="search" :placeholder="tt('filterMessage')" />
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
            <td :class="categoryClass(event.category)">{{ categoryLabel(event.category) }}</td>
            <td>{{ droneLabel(event) }}</td>
            <td>{{ event.message }}</td>
          </tr>
          <tr v-if="visibleEvents.length === 0">
            <td colspan="4" class="empty">{{ safety.events.length === 0 ? tt("noSafetyLog") : tt("noMatchedSafetyLog") }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { safetyCategoryLabel, text, type MessageKey } from "../i18n";
import type { SafetyCategory, SafetyEvent } from "../renderer/types";
import { usePlayerStore } from "../stores/player";
import { useSafetyStore } from "../stores/safety";
import { useUiStore } from "../stores/ui";

interface CategoryOption {
  value: SafetyCategory;
}

const safety = useSafetyStore();
const player = usePlayerStore();
const ui = useUiStore();
const categoryFilter = ref<"all" | SafetyCategory>("all");
const selectedDroneIds = ref<number[]>([]);
const query = ref("");
const timeWindow = ref<"all" | "current">("all");
const sortColumn = ref<"time" | "category" | "drone" | "message">("time");
const sortDirection = ref<"asc" | "desc">("desc");

const categories: CategoryOption[] = [
  { value: "distance_17" },
  { value: "distance_34" },
  { value: "distance_51" },
  { value: "action_incomplete" },
];

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}

function categoryLabel(category: SafetyCategory, short = false): string {
  return safetyCategoryLabel(ui.locale, category, short);
}

const availableDrones = computed(() => {
  const ids = new Set<number>();
  for (const event of safety.events) {
    if (event.drone_a) ids.add(event.drone_a);
    if (event.drone_b) ids.add(event.drone_b);
  }
  return [...ids].sort((a, b) => a - b);
});

const droneFilterLabel = computed(() => {
  if (selectedDroneIds.value.length === 0) {
    return tt("allDrones");
  }
  return selectedDroneIds.value
    .slice()
    .sort((a, b) => a - b)
    .map((id) => `D${id}`)
    .join(", ");
});

const hasFilters = computed(() => {
  return categoryFilter.value !== "all"
    || selectedDroneIds.value.length > 0
    || query.value !== ""
    || timeWindow.value !== "all"
    || sortColumn.value !== "time"
    || sortDirection.value !== "desc";
});

const visibleEvents = computed(() => {
  const selected = new Set(selectedDroneIds.value);
  const textQuery = query.value.toLowerCase();

  const events = safety.events.filter((event) => {
    if (!isInTimeWindow(event)) return false;
    if (categoryFilter.value !== "all" && event.category !== categoryFilter.value) return false;
    if (
      selected.size > 0
      && (!event.drone_a || !selected.has(event.drone_a))
      && (!event.drone_b || !selected.has(event.drone_b))
    ) {
      return false;
    }
    if (textQuery && !`${categoryLabel(event.category)} ${event.category_label} ${event.message}`.toLowerCase().includes(textQuery)) return false;
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
  selectedDroneIds.value = [];
  query.value = "";
  timeWindow.value = "all";
  sortColumn.value = "time";
  sortDirection.value = "desc";
}

function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)} ${tt("secondUnit")}`;
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
  sortDirection.value = column === "time" || column === "category" ? "desc" : "asc";
}

function sortGlyph(column: typeof sortColumn.value): string {
  if (sortColumn.value !== column) {
    return "";
  }
  return sortDirection.value === "asc" ? "↑" : "↓";
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
  border-top: 1px solid var(--border-strong);
  background: var(--panel-bg-alt);
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
}

header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-soft);
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
  padding: 7px 12px;
  border-bottom: 1px solid var(--border-soft);
  background: var(--panel-bg);
}

.summary-bar button {
  justify-self: end;
  min-height: 28px;
  padding: 4px 8px;
}

.count {
  color: var(--text-muted);
  font-size: 11px;
}

.table-wrap {
  min-height: 0;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

th,
td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--border-soft);
  text-align: left;
  vertical-align: top;
}

th {
  position: sticky;
  top: 0;
  background: var(--table-header-bg);
  color: var(--text-muted);
  z-index: 1;
}

.filter-row th {
  top: 27px;
  background: var(--panel-bg);
}

.filter-row select,
.filter-row input,
.multi-select summary {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--border-control);
  background: var(--control-bg);
  color: var(--text);
  padding: 4px 6px;
  min-height: 28px;
}

.multi-select {
  position: relative;
}

.multi-select summary {
  cursor: pointer;
  list-style: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.multi-select summary::-webkit-details-marker {
  display: none;
}

.multi-menu {
  position: absolute;
  z-index: 5;
  top: calc(100% + 4px);
  left: 0;
  min-width: 140px;
  max-height: 180px;
  overflow: auto;
  border: 1px solid var(--border-control);
  background: var(--panel-bg);
  padding: 6px;
  box-shadow: 0 8px 18px var(--shadow);
}

.multi-menu label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  color: var(--text);
  cursor: pointer;
}

.multi-menu label:hover {
  background: var(--control-hover-bg);
}

.multi-menu input {
  width: auto;
}

.empty-option {
  display: block;
  padding: 5px;
  color: var(--text-muted);
}

.th-button {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--text-muted);
  padding: 0;
  display: flex;
  justify-content: space-between;
  cursor: pointer;
}

.th-button:hover {
  color: var(--text);
  background: transparent;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover,
tbody tr.active {
  background: var(--danger-bg);
}

td:first-child,
td:nth-child(2),
td:nth-child(3) {
  white-space: nowrap;
}

.category-distance_17 {
  color: var(--danger);
  font-weight: 800;
}

.category-distance_34 {
  color: var(--risk);
  font-weight: 700;
}

.category-distance_51 {
  color: var(--warning);
  font-weight: 700;
}

.category-action_incomplete {
  color: var(--neutral);
  font-weight: 700;
}

.empty {
  color: var(--text-muted);
  text-align: center;
  cursor: default;
}

@media (max-width: 980px) {
  .summary-bar {
    grid-template-columns: 1fr;
  }
}
</style>
