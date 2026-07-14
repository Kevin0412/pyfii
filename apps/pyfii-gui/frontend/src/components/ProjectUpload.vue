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
      {{ project.loading ? tt("parsing") : tt("load") }}
    </button>

    <span v-if="selectedFile" class="selected-file">{{ selectedFile.name }}</span>
    <template v-if="ui.localProjectImportEnabled">
      <label class="local-path-control">
        <span>{{ tt("localProjectPath") }}</span>
        <input v-model.trim="localPath" type="text" :placeholder="tt('localProjectPlaceholder')" />
      </label>
      <button type="button" :disabled="!localPath || project.loading" @click="submitLocal">
        {{ project.loading ? tt("parsing") : tt("openLocal") }}
      </button>
    </template>
    <span v-if="project.error" class="upload-error">{{ project.error }}</span>
    <div
      v-if="project.loading"
      class="loading-progress"
      role="progressbar"
      :aria-label="tt('parsing')"
      :aria-valuetext="tt('parsing')"
    >
      <span />
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

  await loadProject(() => uploadProjectZip(selectedFile.value as File, fps.value, ignoreAcc.value));
}

async function submitLocal(): Promise<void> {
  if (!localPath.value) {
    return;
  }

  await loadProject(() => importLocalProject(localPath.value, fps.value, ignoreAcc.value));
}

async function loadProject(loader: () => Promise<ProjectCreateResponse>): Promise<void> {
  project.beginLoading();
  safety.clear();
  player.pause();
  player.setCurrentTime(0);

  try {
    const meta = await loader();
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
  height: 4px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  background: var(--panel-bg);
}

.loading-progress span {
  display: block;
  width: 35%;
  height: 100%;
  background: var(--text-strong);
  animation: loading-progress-slide 1.1s ease-in-out infinite;
}

@keyframes loading-progress-slide {
  from { transform: translateX(-110%); }
  to { transform: translateX(315%); }
}

@media (prefers-reduced-motion: reduce) {
  .loading-progress span {
    width: 100%;
    opacity: 0.55;
    animation: none;
  }
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
