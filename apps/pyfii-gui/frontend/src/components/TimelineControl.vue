<template>
  <section class="timeline">
    <button :disabled="!project.hasProject" @click="player.togglePlaying">
      {{ player.playing ? "Pause" : "Play" }}
    </button>

    <span class="time-readout">{{ formatTime(player.currentTimeMs) }} / {{ formatTime(project.durationMs) }}</span>

    <input
      v-model.number="currentTime"
      type="range"
      min="0"
      :max="Math.max(project.durationMs, 1)"
      step="10"
      :disabled="!project.hasProject"
    />

    <label>
      Speed
      <select v-model.number="speed" :disabled="!project.hasProject">
        <option :value="0.25">0.25x</option>
        <option :value="0.5">0.5x</option>
        <option :value="1">1x</option>
        <option :value="2">2x</option>
        <option :value="4">4x</option>
      </select>
    </label>

    <label class="toggle">
      <input v-model="player.showSafetyMarkers" type="checkbox" />
      safety
    </label>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";

const player = usePlayerStore();
const project = useProjectStore();
const safety = useSafetyStore();

const currentTime = computed({
  get: () => player.currentTimeMs,
  set: (value: number) => {
    player.setCurrentTime(Number(value));
    safety.setActiveEvent(null);
  },
});

const speed = computed({
  get: () => player.speed,
  set: (value: number) => player.setSpeed(Number(value)),
});

function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)}s`;
}
</script>

<style scoped>
.timeline {
  display: grid;
  grid-template-columns: auto auto minmax(180px, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-top: 1px solid #d8d8d8;
  background: #101010;
}

.time-readout {
  min-width: 150px;
  color: #dcdcdc;
  font-size: 12px;
}

label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #cfcfcf;
  font-size: 12px;
}

.toggle input {
  margin: 0;
}

@media (max-width: 760px) {
  .timeline {
    grid-template-columns: 1fr 1fr;
  }

  input[type="range"] {
    grid-column: 1 / -1;
  }
}
</style>
