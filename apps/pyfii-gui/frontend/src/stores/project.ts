import { defineStore } from "pinia";
import type { DroneTrack, ProjectMeta } from "../renderer/types";

interface ProjectState {
  projectId: string | null;
  meta: ProjectMeta | null;
  tracks: DroneTrack[];
  trackFps: number;
  uploadWarnings: string[];
  loading: boolean;
  error: string | null;
}

export const useProjectStore = defineStore("project", {
  state: (): ProjectState => ({
    projectId: null,
    meta: null,
    tracks: [],
    trackFps: 60,
    uploadWarnings: [],
    loading: false,
    error: null,
  }),
  getters: {
    durationMs: (state): number => state.meta?.duration_ms || 0,
    hasProject: (state): boolean => Boolean(state.projectId && state.meta),
  },
  actions: {
    beginLoading() {
      this.loading = true;
      this.error = null;
    },
    setError(message: string) {
      this.error = message;
      this.loading = false;
    },
    setLoadedProject(meta: ProjectMeta, warnings: string[], tracks: DroneTrack[], fps: number) {
      this.projectId = meta.project_id;
      this.meta = meta;
      this.tracks = tracks;
      this.trackFps = fps;
      this.uploadWarnings = warnings;
      this.loading = false;
    },
    clear() {
      this.projectId = null;
      this.meta = null;
      this.tracks = [];
      this.trackFps = 60;
      this.uploadWarnings = [];
      this.loading = false;
      this.error = null;
    },
  },
});
