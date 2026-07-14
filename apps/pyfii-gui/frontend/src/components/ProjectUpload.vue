<template>
  <form class="upload-bar" data-guide="upload" @submit.prevent="submit">
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
      {{ project.loading ? tt("loadingProject") : tt("load") }}
    </button>

    <span v-if="selectedFile" class="selected-file">{{ selectedFile.name }}</span>
    <template v-if="ui.localProjectImportEnabled">
      <label class="local-path-control">
        <span>{{ tt("localProjectPath") }}</span>
        <input v-model.trim="localPath" type="text" :placeholder="tt('localProjectPlaceholder')" />
      </label>
      <button type="button" :disabled="!localPath || project.loading" @click="submitLocal">
        {{ project.loading ? tt("loadingProject") : tt("openLocal") }}
      </button>
    </template>
    <span v-if="project.error" class="upload-error">{{ project.error }}</span>
    <div v-if="project.loading" class="loading-progress" aria-live="polite">
      <div class="loading-progress-label">
        <span>{{ tt(loadPhase) }}</span>
        <strong>{{ Math.round(loadProgress) }}%</strong>
      </div>
      <progress :value="loadProgress" max="100">{{ Math.round(loadProgress) }}%</progress>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref } from "vue";

import { ApiError } from "../api/client";
import { fetchProjectSafety, fetchProjectTracks, importLocalProject, uploadProjectZip, type ProjectCreateResponse } from "../api/projects";
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
const localPath = ref("");
const fps = ref(60);
const ignoreAcc = ref(false);
const loadProgress = ref(0);
const loadPhase = ref<MessageKey>("uploadingProject");

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

  await loadProject(
    (onUploadProgress) => uploadProjectZip(
      selectedFile.value as File,
      fps.value,
      ignoreAcc.value,
      onUploadProgress,
    ),
    true,
  );
}

async function submitLocal(): Promise<void> {
  if (!localPath.value) {
    return;
  }

  await loadProject(() => importLocalProject(localPath.value, fps.value, ignoreAcc.value), false);
}

async function loadProject(
  loader: (onUploadProgress: (fraction: number) => void) => Promise<ProjectCreateResponse>,
  uploadsFile: boolean,
): Promise<void> {
  project.beginLoading();
  safety.clear();
  player.pause();
  player.setCurrentTime(0);
  loadProgress.value = 0;
  loadPhase.value = uploadsFile ? "uploadingProject" : "parsingProject";

  try {
    const meta = await loader((fraction) => {
      loadProgress.value = Math.round(Math.max(0, Math.min(1, fraction)) * 25);
      if (fraction >= 1) loadPhase.value = "parsingProject";
    });
    loadProgress.value = 50;
    loadPhase.value = "loadingProjectData";
    project.setMeta(meta, meta.warnings);

    let loadedResponses = 0;
    const markResponseLoaded = (): void => {
      loadedResponses += 1;
      loadProgress.value = 50 + loadedResponses * 25;
      if (loadedResponses === 2) loadPhase.value = "projectLoaded";
    };
    const [tracksResponse, safetyResponse] = await Promise.all([
      fetchProjectTracks(meta.project_id, fps.value).then((response) => {
        markResponseLoaded();
        return response;
      }),
      fetchProjectSafety(meta.project_id).then((response) => {
        markResponseLoaded();
        return response;
      }),
    ]);

    // Keep the completed bar visible briefly instead of removing it in the same render tick.
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    safety.setSafety(safetyResponse.summary, safetyResponse.events);
    project.setTracks(tracksResponse.drones, tracksResponse.fps);
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
  gap: 8px;
  min-width: 0;
  flex: 1 1 480px;
}

.upload-bar label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text);
  font-size: 11.5px;
  white-space: nowrap;
}

.upload-bar button,
.upload-bar select {
  min-height: 28px;
  padding: 4px 8px;
}

.file-control input {
  width: 178px;
  max-width: 178px;
  font-size: 11px;
}

.local-path-control input {
  width: 260px;
  max-width: 32vw;
  min-width: 180px;
  border: 1px solid var(--border-control);
  background: var(--control-bg);
  color: var(--text);
  padding: 4px 6px;
  font-size: 11px;
}

.inline-check input {
  margin: 0;
}

.selected-file {
  color: var(--text-muted);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.upload-error {
  color: var(--danger);
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.loading-progress {
  flex: 1 0 100%;
  display: grid;
  gap: 4px;
}

.loading-progress-label {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-muted);
  font-size: 10px;
}

.loading-progress-label strong {
  color: var(--text-strong);
  font-variant-numeric: tabular-nums;
}

.loading-progress progress {
  width: 100%;
  height: 8px;
  appearance: none;
  border: 1px solid var(--border-soft);
  background: var(--panel-bg);
}

.loading-progress progress::-webkit-progress-bar {
  background: var(--panel-bg);
}

.loading-progress progress::-webkit-progress-value {
  background: var(--text-strong);
}

.loading-progress progress::-moz-progress-bar {
  background: var(--text-strong);
}

:global(body[data-device="phone"] .upload-bar),
:global(body[data-device="tablet"][data-orientation="portrait"] .upload-bar) {
  width: 100%;
  flex-basis: 100%;
}

:global(body[data-device="phone"] .file-control),
:global(body[data-device="phone"] .local-path-control),
:global(body[data-device="tablet"][data-orientation="portrait"] .file-control),
:global(body[data-device="tablet"][data-orientation="portrait"] .local-path-control) {
  flex: 1 0 100%;
}

:global(body[data-device="phone"] .file-control input),
:global(body[data-device="phone"] .local-path-control input),
:global(body[data-device="tablet"][data-orientation="portrait"] .file-control input),
:global(body[data-device="tablet"][data-orientation="portrait"] .local-path-control input) {
  width: auto;
  min-width: 0;
  max-width: none;
  flex: 1;
}

:global(body[data-device="phone"] .upload-bar button),
:global(body[data-device="phone"] .upload-bar select),
:global(body[data-device="phone"] .file-control input),
:global(body[data-device="tablet"][data-orientation="portrait"] .upload-bar button),
:global(body[data-device="tablet"][data-orientation="portrait"] .upload-bar select),
:global(body[data-device="tablet"][data-orientation="portrait"] .file-control input) {
  min-height: 38px;
}

:global(body[data-device="phone"] .selected-file),
:global(body[data-device="phone"] .upload-error),
:global(body[data-device="tablet"][data-orientation="portrait"] .selected-file),
:global(body[data-device="tablet"][data-orientation="portrait"] .upload-error) {
  flex: 1 0 100%;
  max-width: 100%;
  white-space: normal;
}
</style>
