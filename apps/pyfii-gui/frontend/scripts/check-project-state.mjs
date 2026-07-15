import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const uploadSource = await readFile(
  new URL("../src/components/ProjectUpload.vue", import.meta.url),
  "utf8",
);
const completeData = uploadSource.indexOf("const [tracksResponse, safetyResponse] = await Promise.all");
const safetyCommit = uploadSource.indexOf("safety.setSafety(");
const projectCommit = uploadSource.indexOf("project.setLoadedProject(");

assert.ok(completeData >= 0, "tracks and safety must load together");
assert.ok(safetyCommit > completeData, "safety must not switch before all project data has loaded");
assert.ok(projectCommit > completeData, "project state must not switch before all project data has loaded");
assert.doesNotMatch(uploadSource, /project\.setMeta\(|project\.setTracks\(|safety\.clear\(\)/);
assert.match(uploadSource, /if \(project\.loading\) return;\s+project\.beginLoading\(\);/);

const projectStoreSource = await readFile(
  new URL("../src/stores/project.ts", import.meta.url),
  "utf8",
);
assert.match(
  projectStoreSource,
  /setLoadedProject\([^}]+this\.projectId[^}]+this\.meta[^}]+this\.tracks[^}]+this\.trackFps[^}]+this\.uploadWarnings[^}]+this\.loading = false;/s,
  "the project store must publish metadata and tracks in one action",
);

const canvasSource = await readFile(
  new URL("../src/components/SimulationCanvas.vue", import.meta.url),
  "utf8",
);
const exportStart = canvasSource.indexOf("async function exportVideo()");
const exportEnd = canvasSource.indexOf("defineExpose(", exportStart);
const exportSource = canvasSource.slice(exportStart, exportEnd);
const projectIdCapture = exportSource.indexOf("const projectId = project.projectId;");

assert.ok(projectIdCapture >= 0, "video export must capture its project ID when it starts");
assert.doesNotMatch(
  exportSource.slice(projectIdCapture + "const projectId = project.projectId;".length),
  /project\.projectId/,
  "video export must not read a mutable project ID after it starts",
);
assert.match(
  canvasSource,
  /\.sim-canvas\[aria-label="Pyfii 3D simulation canvas"\]\.active\s*\{[^}]*touch-action:\s*none;/s,
);

console.log("Atomic project loading, stable video export, and 3D touch checks passed.");
