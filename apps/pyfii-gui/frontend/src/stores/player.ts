import { defineStore } from "pinia";

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
  },
});
