<template>
  <form class="upload-bar" @submit.prevent="submit">
    <label class="file-control">
      <span>{{ tt("uploadProject") }}</span>
      <input type="file" accept=".zip,application/zip" @change="onFileChange" />
    </label>

    <label>
      {{ tt("frameRate") }}
      <select v-model.number="fps" :disabled="project.loading">
        <option :value="60">60</option>
        <option :value="30">30</option>
        <option :value="100">100</option>
        <option :value="200">200</option>
      </select>
    </label>

    <label class="inline-check">
      <input v-model="ignoreAcc" type="checkbox" :disabled="project.loading" />
      {{ tt("ignoreAcceleration") }}
    </label>

    <button type="submit" :disabled="!selectedFile || project.loading">
      {{ project.loading ? tt("parsing") : tt("load") }}
    </button>

    <span v-if="selectedFile" class="selected-file">{{ selectedFile.name }}</span>
    <span v-if="project.error" class="upload-error">{{ project.error }}</span>
  </form>
</template>

<script setup lang="ts">
import { ref } from "vue";

import { ApiError } from "../api/client";
import { fetchProjectSafety, fetchProjectTracks, uploadProjectZip } from "../api/projects";
import { text, type MessageKey } from "../i18n";
import { usePlayerStore } from "../stores/player";
import { useProjectStore } from "../stores/project";
import { useSafetyStore } from "../stores/safety";
import { useUiStore } from "../stores/ui";

const project = useProjectStore();
const player = usePlayerStore();
const safety = useSafetyStore();
const ui = useUiStore();

const selectedFile = ref<File | null>(null);
const fps = ref(60);
const ignoreAcc = ref(false);

function tt(key: MessageKey): string {
  return text(ui.locale, key);
}

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
  return tt("unknownUploadError");
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
    const meta = await uploadProjectZip(selectedFile.value, fps.value, ignoreAcc.value);
    project.setMeta(meta, meta.warnings);

    const [tracksResponse, safetyResponse] = await Promise.all([
      fetchProjectTracks(meta.project_id, fps.value),
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
  color: var(--text);
  font-size: 12px;
}

.file-control input {
  max-width: 220px;
}

.inline-check input {
  margin: 0;
}

.selected-file {
  color: var(--text-muted);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-error {
  color: var(--danger);
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
