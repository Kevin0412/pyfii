import { defineStore } from "pinia";

export type ThemeMode = "dark" | "light";
export type LocaleMode = "en" | "zh";

const THEME_STORAGE_KEY = "pyfii-gui-theme";
const LOCALE_STORAGE_KEY = "pyfii-gui-locale";

function savedTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "dark";
  }

  return window.localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark";
}

function savedLocale(): LocaleMode {
  if (typeof window === "undefined") {
    return "en";
  }

  return window.localStorage.getItem(LOCALE_STORAGE_KEY) === "zh" ? "zh" : "en";
}

export const useUiStore = defineStore("ui", {
  state: () => ({
    theme: savedTheme() as ThemeMode,
    locale: savedLocale() as LocaleMode,
  }),
  actions: {
    setTheme(theme: ThemeMode) {
      this.theme = theme;
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    },
    toggleTheme() {
      this.setTheme(this.theme === "dark" ? "light" : "dark");
    },
    setLocale(locale: LocaleMode) {
      this.locale = locale;
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    },
    toggleLocale() {
      this.setLocale(this.locale === "en" ? "zh" : "en");
    },
  },
});
