import { defineStore } from "pinia";
import type { SafetyEvent, SafetySummary } from "../renderer/types";

interface SafetyState {
  summary: SafetySummary | null;
  events: SafetyEvent[];
  activeEventId: string | null;
}

export const useSafetyStore = defineStore("safety", {
  state: (): SafetyState => ({
    summary: null,
    events: [],
    activeEventId: null,
  }),
  actions: {
    setSafety(summary: SafetySummary, events: SafetyEvent[]) {
      this.summary = summary;
      this.events = events;
      this.activeEventId = null;
    },
    setActiveEvent(id: string | null) {
      this.activeEventId = id;
    },
    clear() {
      this.summary = null;
      this.events = [];
      this.activeEventId = null;
    },
  },
});
