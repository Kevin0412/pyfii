<template>
  <form class="upload-bar" @submit.prevent="submit">
    <label class="file-control">
      <span>上传项目</span>
      <input type="file" accept=".zip,application/zip" @change="onFileChange" />
    </label>

    <label>
      Source FPS
      <select v-model.number="sourceFps" :disabled="project.loading">
        <option :value="200">200</option>
        <option :value="100">100</option>
        <option :value="60">60</option>
        <option :value="30">30</option>
      </select>
    </label>

    <label>
      Tracks FPS
      <select v-model.number="trackFps" :disabled="project.loading">
        <option :value="60">60</option>
        <option :value="30">30</option>
        <option :value="100">100</option>
        <option :value="200">200</option>
      </select>
    </label>

    <label class="inline-check">
      <input v-model="ignoreAcc" type="checkbox" :disabled="project.loading" />
      ignore_acc
    </label>

    <button type="submit" :disabled="!selectedFile || project.loading">
      {{ project.loading ? "Parsing..." : "Load" }}
    </button>

    <span v-if="selectedFile" class="selected-file">{{ selectedFile.name }}</span>
    <span v-if="project.error" class="upload-error">{{ project.error }}</span>
  </form>
</template>

<script setup lang="ts">
import { ref } from "vue";

import { ApiError } from "../api/client";
import { fetchProjectSafety, fetchProjectTracks, uploadProjectZip } from "../api/projects";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";

const project = useProjectStore();
const player = usePlayerStore();
const safety = useSafetyStore();

const selectedFile = ref<File | null>(null);
const sourceFps = ref(200);
const trackFps = ref(60);
const ignoreAcc = ref(false);

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] || null;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown upload error.";
}

async function submit(): Promise<void> {
  if (!selectedFile.value) {
    return;
  }

  project.beginLoading();
  safety.clear();
  player.pause();
  player.setCurrentTime(0);

  try {
    const meta = await uploadProjectZip(selectedFile.value, sourceFps.value, ignoreAcc.value);
    project.setMeta(meta, meta.warnings);

    const [tracksResponse, safetyResponse] = await Promise.all([
      fetchProjectTracks(meta.project_id, trackFps.value),
      fetchProjectSafety(meta.project_id),
    ]);

    project.setTracks(tracksResponse.drones, tracksResponse.fps);
    safety.setSafety(safetyResponse.summary, safetyResponse.events);
  } catch (error) {
    project.setError(errorMessage(error));
  }
}
</script>

<style scoped>
.upload-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
}

.upload-bar label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #cfcfcf;
  font-size: 12px;
}

.file-control input {
  max-width: 220px;
}

.inline-check input {
  margin: 0;
}

.selected-file {
  color: #8e8e8e;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-error {
  color: #ff5b5b;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
