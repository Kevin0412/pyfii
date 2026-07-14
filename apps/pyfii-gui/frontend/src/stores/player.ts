import { defineStore } from "pinia";

import { wrapHorizontalAngle } from "../renderer/three/geometry";

export type RenderMode = "classic2d" | "three3d";
export type ThreeProjectionMode = "orthographic" | "perspective";

interface PlayerState {
  currentTimeMs: number;
  playing: boolean;
  speed: number;
  selectedDroneId: number | null;
  showTrail: boolean;
  showSafetyMarkers: boolean;
  seeking: boolean;
  wasPlayingBeforeSeek: boolean;
  renderScale: number;
  fullscreen: boolean;
  renderMode: RenderMode;
  threeProjection: ThreeProjectionMode;
  viewAngleA: number;
  viewAngleB: number;
  observerDistance: number;
  projectionDistance: number;
}

export const usePlayerStore = defineStore("player", {
  state: (): PlayerState => ({
    currentTimeMs: 0,
    playing: false,
    speed: 1,
    selectedDroneId: null,
    showTrail: false,
    showSafetyMarkers: true,
    seeking: false,
    wasPlayingBeforeSeek: false,
    renderScale: 1,
    fullscreen: false,
    renderMode: "classic2d",
    threeProjection: "perspective",
    viewAngleA: 90,
    viewAngleB: 3,
    observerDistance: 600,
    projectionDistance: 450,
  }),
  actions: {
    play() {
      this.playing = true;
    },
    pause() {
      this.playing = false;
    },
    togglePlaying() {
      this.playing = !this.playing;
    },
    setCurrentTime(timeMs: number) {
      this.currentTimeMs = Math.max(0, timeMs);
    },
    setSpeed(speed: number) {
      this.speed = speed;
    },
    setSelectedDrone(id: number | null) {
      this.selectedDroneId = id;
    },
    startSeeking() {
      if (!this.seeking) {
        this.wasPlayingBeforeSeek = this.playing;
      }
      this.playing = false;
      this.seeking = true;
    },
    endSeeking() {
      const shouldResume = this.wasPlayingBeforeSeek;
      this.seeking = false;
      this.wasPlayingBeforeSeek = false;
      if (shouldResume) {
        this.playing = true;
      }
    },
    setRenderScale(scale: number) {
      this.renderScale = scale;
    },
    setFullscreen(v: boolean) {
      this.fullscreen = v;
    },
    setRenderMode(mode: RenderMode) {
      this.renderMode = mode;
    },
    setThreeProjection(mode: ThreeProjectionMode) {
      this.threeProjection = mode;
    },
    setViewAngleA(value: number) {
      this.viewAngleA = wrapHorizontalAngle(value);
    },
    setViewAngleB(value: number) {
      this.viewAngleB = Math.max(-90, Math.min(90, value));
    },
    setObserverDistance(value: number) {
      this.observerDistance = Math.max(50, value);
    },
    setProjectionDistance(value: number) {
      this.projectionDistance = Math.max(50, value);
    },
    resetThreeView() {
      this.threeProjection = "perspective";
      this.viewAngleA = 90;
      this.viewAngleB = 3;
      this.observerDistance = 600;
      this.projectionDistance = 450;
    },
  },
});
