import { defineStore } from "pinia";

interface PlayerState {
  currentTimeMs: number;
  playing: boolean;
  speed: number;
  selectedDroneId: number | null;
  showTrail: boolean;
  showSafetyMarkers: boolean;
  seeking: boolean;
  renderScale: number;
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
    renderScale: 1,
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
      this.playing = false;
      this.seeking = true;
    },
    endSeeking() {
      this.seeking = false;
    },
    setRenderScale(scale: number) {
      this.renderScale = scale;
    },
  },
});
