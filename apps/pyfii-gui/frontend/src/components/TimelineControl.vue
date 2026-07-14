<template>
  <section class="timeline" data-guide="preview">
    <button :disabled="!project.hasProject" @click="togglePlayback">
      {{ player.playing ? tt("pause") : tt("play") }}
    </button>

    <span class="time-readout">{{ formatTime(player.currentTimeMs) }} / {{ formatTime(project.durationMs) }}</span>

    <div class="range-wrap">
      <input
        v-model.number="currentTime"
        type="range"
        min="0"
        :max="Math.max(project.durationMs, 1)"
        step="10"
        :disabled="!project.hasProject"
        @pointerdown="startSeek"
        @pointerup="endSeek"
        @pointercancel="endSeek"
        @change="endSeek"
        @blur="endSeek"
      />
      <div class="safety-ticks">
        <span
          v-for="marker in safetyMarkers"
          :key="marker.id"
          class="tick"
          :class="marker.category"
          :style="{ left: marker.position + '%' }"
          :title="markerTitle(marker)"
        ></span>
      </div>
    </div>

    <label>
      {{ tt("speed") }}
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
      {{ tt("safetyMarkers") }}
    </label>

    <audio
      v-if="musicUrl"
      ref="audioRef"
      class="music-player"
      :src="musicUrl"
      preload="metadata"
      controls
      @play="onAudioPlay"
      @pause="onAudioPause"
      @seeked="onAudioSeek"
      @ended="player.pause"
    />

    <span v-else class="music-empty">{{ tt("noMusic") }}</span>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import { projectMusicUrl } from "../api/projects";
import { safetyCategoryLabel, text, type MessageKey } from "../i18n";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";
import { useUiStore } from "../stores/ui";

const player = usePlayerStore();
const project = useProjectStore();
const safety = useSafetyStore();
const ui = useUiStore();
const audioRef = ref<HTMLAudioElement | null>(null);

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}

const musicUrl = computed(() => {
  if (!project.projectId || !project.meta?.music.available) {
    return "";
  }
  return projectMusicUrl(project.projectId);
});

const currentTime = computed({
  get: () => player.currentTimeMs,
  set: (value: number) => {
    player.setCurrentTime(Number(value));
    safety.setActiveEvent(null);
  },
});

const safetyMarkers = computed(() => {
  const duration = project.durationMs;
  if (duration <= 0) return [];
  return safety.events.map((event) => ({
    id: event.id,
    category: event.category,
    categoryLabel: safetyCategoryLabel(ui.locale, event.category),
    position: (event.time_ms / duration) * 100,
    message: event.message,
    formattedTime: formatTime(event.time_ms),
  }));
});

const speed = computed({
  get: () => player.speed,
  set: (value: number) => player.setSpeed(Number(value)),
});

function syncAudioTime(force = false): void {
  const audio = audioRef.value;
  if (!audio || !musicUrl.value) {
    return;
  }
  const targetSeconds = player.currentTimeMs / 1000;
  if (force || Math.abs(audio.currentTime - targetSeconds) > 0.35) {
    audio.currentTime = targetSeconds;
  }
}

async function playAudio(): Promise<void> {
  const audio = audioRef.value;
  if (!audio || !musicUrl.value) {
    return;
  }
  audio.playbackRate = player.speed;
  syncAudioTime(true);
  try {
    await audio.play();
  } catch {
    // Browsers may block audio until a user gesture; the simulation can still run.
  }
}

function pauseAudio(): void {
  audioRef.value?.pause();
}

function togglePlayback(): void {
  if (player.playing) {
    player.pause();
    pauseAudio();
    return;
  }

  if (project.durationMs > 0 && player.currentTimeMs >= project.durationMs - 1) {
    player.setCurrentTime(0);
    safety.setActiveEvent(null);
    syncAudioTime(true);
  }
  player.play();
  void playAudio();
}

function startSeek(): void {
  if (project.hasProject) {
    player.startSeeking();
  }
}

function endSeek(): void {
  if (player.seeking) {
    player.endSeeking();
  }
}

function onAudioPlay(): void {
  if (player.seeking) {
    return;
  }
  if (!player.playing) {
    if (project.durationMs > 0 && player.currentTimeMs >= project.durationMs - 1) {
      player.setCurrentTime(0);
      safety.setActiveEvent(null);
    }
    player.play();
  }
  syncAudioTime();
}

function onAudioPause(): void {
  if (player.seeking) {
    return;
  }
  if (player.playing && !audioRef.value?.ended) {
    player.pause();
  }
}

function onAudioSeek(): void {
  const audio = audioRef.value;
  if (!audio || player.seeking) {
    return;
  }
  player.setCurrentTime(audio.currentTime * 1000);
  safety.setActiveEvent(null);
}

function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)} ${tt("secondUnit")}`;
}

function markerTitle(marker: { categoryLabel: string; message: string; formattedTime: string }): string {
  return ui.locale === "zh"
    ? `${marker.categoryLabel}：${marker.message}，时间 ${marker.formattedTime}`
    : `${marker.categoryLabel}: ${marker.message} at ${marker.formattedTime}`;
}

watch(
  () => player.playing,
  (playing) => {
    if (playing) {
      void playAudio();
    } else {
      pauseAudio();
    }
  },
);

watch(
  () => player.speed,
  (value) => {
    if (audioRef.value) {
      audioRef.value.playbackRate = value;
    }
  },
);

watch(
  () => player.currentTimeMs,
  () => syncAudioTime(false),
);

watch(
  musicUrl,
  async () => {
    await nextTick();
    if (audioRef.value) {
      audioRef.value.load();
      audioRef.value.playbackRate = player.speed;
      syncAudioTime(true);
      if (player.playing) {
        void playAudio();
      }
    }
  },
);
</script>

<style scoped>
.timeline {
  display: grid;
  grid-template-columns: auto auto minmax(160px, 1fr) auto auto minmax(160px, 240px);
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-top: 1px solid var(--border-control);
  background: var(--panel-bg);
}

.time-readout {
  min-width: 132px;
  color: var(--text);
  font-size: 11.5px;
}

.range-wrap {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 0;
}

.range-wrap input[type="range"] {
  width: 100%;
}

.safety-ticks {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.tick {
  position: absolute;
  bottom: 6px;
  transform: translateX(-50%);
  width: 3px;
  height: 10px;
  border-radius: 1.5px;
}

.tick.distance_17 {
  background: var(--danger);
  height: 12px;
}

.tick.distance_34 {
  background: var(--risk);
  height: 11px;
}

.tick.distance_51 {
  background: var(--warning);
  height: 10px;
}

.tick.action_incomplete {
  background: var(--neutral);
  height: 8px;
}

label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text);
  font-size: 11.5px;
  white-space: nowrap;
}

.timeline button,
.timeline select {
  min-height: 28px;
  padding: 4px 8px;
}

.toggle input {
  margin: 0;
}

.music-player {
  width: 100%;
  height: 28px;
  filter: grayscale(1);
}

.music-empty {
  color: var(--text-muted);
  font-size: 11.5px;
}

:global(body[data-device="phone"] .timeline),
:global(body[data-device="tablet"][data-orientation="portrait"] .timeline) {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

:global(body[data-device="phone"] .range-wrap),
:global(body[data-device="phone"] .music-player),
:global(body[data-device="phone"] .music-empty),
:global(body[data-device="tablet"][data-orientation="portrait"] .range-wrap),
:global(body[data-device="tablet"][data-orientation="portrait"] .music-player),
:global(body[data-device="tablet"][data-orientation="portrait"] .music-empty) {
  grid-column: 1 / -1;
}

:global(body[data-device="phone"] .timeline button),
:global(body[data-device="phone"] .timeline select) {
  min-height: 38px;
}

:global(body[data-device="phone"] .time-readout) {
  min-width: 0;
  text-align: right;
}
</style>
