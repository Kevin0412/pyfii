<template>
  <section class="safety-panel">
    <header>
      <h2>Safety Log</h2>
      <span v-if="safety.summary" :class="`level-${safety.summary.level}`">
        {{ safety.summary.level }} · E{{ safety.summary.error_count }} / W{{ safety.summary.warning_count }}
      </span>
      <span v-else class="muted">waiting for project</span>
    </header>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>time</th>
            <th>level</th>
            <th>type</th>
            <th>drones</th>
            <th>message</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="event in safety.events"
            :key="event.id"
            :class="{ active: event.id === safety.activeEventId }"
            @click="jumpToEvent(event)"
          >
            <td>{{ formatTime(event.time_ms) }}</td>
            <td :class="`level-${event.level}`">{{ event.level }}</td>
            <td>{{ event.type }}</td>
            <td>{{ droneLabel(event) }}</td>
            <td>{{ event.message }}</td>
          </tr>
          <tr v-if="safety.events.length === 0">
            <td colspan="5" class="empty">暂无安全日志</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { SafetyEvent } from "../renderer/types";
import { usePlayerStore } from "../stores/player";
import { useSafetyStore } from "../stores/safety";

const safety = useSafetyStore();
const player = usePlayerStore();

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
  grid-template-rows: auto minmax(0, 1fr);
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

tbody tr {
  cursor: pointer;
}

tbody tr:hover,
tbody tr.active {
  background: #241414;
}

td:first-child,
td:nth-child(2),
td:nth-child(3),
td:nth-child(4) {
  white-space: nowrap;
}

.empty {
  color: #8b8b8b;
  text-align: center;
  cursor: default;
}
</style>
