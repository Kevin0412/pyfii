import { defineStore } from "pinia";

export type ThemeMode = "dark" | "light";

const THEME_STORAGE_KEY = "pyfii-gui-theme";

function savedTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "dark";
  }

  return window.localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark";
}

export const useUiStore = defineStore("ui", {
  state: () => ({
    theme: savedTheme() as ThemeMode,
  }),
  actions: {
    setTheme(theme: ThemeMode) {
      this.theme = theme;
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    },
    toggleTheme() {
      this.setTheme(this.theme === "dark" ? "light" : "dark");
    },
  },
});
