<template>
  <section class="timeline">
    <button :disabled="!project.hasProject" @click="togglePlayback">
      {{ player.playing ? "Pause" : "Play" }}
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
        @mousedown="player.startSeeking()"
        @touchstart="player.startSeeking()"
        @mouseup="player.endSeeking()"
        @touchend="player.endSeeking()"
      />
      <div class="safety-ticks">
        <span
          v-for="marker in safetyMarkers"
          :key="marker.id"
          class="tick"
          :class="marker.level"
          :style="{ left: marker.position + '%' }"
          :title="`${marker.level}: ${marker.message} @ ${marker.formattedTime}`"
        ></span>
      </div>
    </div>

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

    <span v-else class="music-empty">no music</span>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import { projectMusicUrl } from "../api/projects";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";

const player = usePlayerStore();
const project = useProjectStore();
const safety = useSafetyStore();
const audioRef = ref<HTMLAudioElement | null>(null);

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
    level: event.level,
    position: (event.time_ms / duration) * 100,
    message: event.message,
    formattedTime: `${(event.time_ms / 1000).toFixed(2)}s`,
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

  player.play();
  void playAudio();
}

function onAudioPlay(): void {
  if (!player.playing) {
    player.play();
  }
  syncAudioTime();
}

function onAudioPause(): void {
  if (player.playing && !audioRef.value?.ended) {
    player.pause();
  }
}

function onAudioSeek(): void {
  const audio = audioRef.value;
  if (!audio) {
    return;
  }
  player.setCurrentTime(audio.currentTime * 1000);
  safety.setActiveEvent(null);
}

function formatTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)}s`;
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
  grid-template-columns: auto auto minmax(180px, 1fr) auto auto minmax(180px, 260px);
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

.tick.error {
  background: #ff3333;
  height: 12px;
}

.tick.warning {
  background: #ffd15c;
  height: 8px;
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

.music-player {
  width: 100%;
  height: 28px;
  filter: grayscale(1);
}

.music-empty {
  color: #777;
  font-size: 12px;
}

@media (max-width: 760px) {
  .timeline {
    grid-template-columns: 1fr 1fr;
  }

  .range-wrap,
  .music-player,
  .music-empty {
    grid-column: 1 / -1;
  }
}
</style>
