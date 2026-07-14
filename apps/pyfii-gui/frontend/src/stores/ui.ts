import { defineStore } from "pinia";

export type ThemeMode = "dark" | "light";
export type LocaleMode = "en" | "zh";

interface DeploymentState {
  icp_beian: string;
  icp_url: string;
  gongan_beian: string;
  gongan_url: string;
}

const THEME_STORAGE_KEY = "pyfii-gui-theme";
const LOCALE_STORAGE_KEY = "pyfii-gui-locale-v2";
const GUIDE_STORAGE_KEY = "pyfii-gui-guide-seen-v2";

function storedTheme(): ThemeMode | null {
  if (typeof window === "undefined") {
    return null;
  }

  const theme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return theme === "dark" || theme === "light" ? theme : null;
}

function savedLocale(): LocaleMode {
  if (typeof window === "undefined") {
    return "zh";
  }

  return window.localStorage.getItem(LOCALE_STORAGE_KEY) === "en" ? "en" : "zh";
}

function shouldOpenGuide(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return window.localStorage.getItem(GUIDE_STORAGE_KEY) !== "1";
}

export const useUiStore = defineStore("ui", {
  state: () => ({
    theme: (storedTheme() ?? "light") as ThemeMode,
    themePreferenceSaved: storedTheme() !== null,
    locale: savedLocale() as LocaleMode,
    guideOpen: shouldOpenGuide(),
    localProjectImportEnabled: false,
    deployment: {
      icp_beian: "",
      icp_url: "",
      gongan_beian: "",
      gongan_url: "",
    } as DeploymentState,
  }),
  getters: {
    complianceLinks: (state): Array<{ label: string; url: string }> => {
      const links: Array<{ label: string; url: string }> = [];
      if (state.deployment.icp_beian) {
        links.push({
          label: state.deployment.icp_beian,
          url: state.deployment.icp_url || "https://beian.miit.gov.cn/",
        });
      }
      if (state.deployment.gongan_beian) {
        links.push({
          label: state.deployment.gongan_beian,
          url: state.deployment.gongan_url || "#",
        });
      }
      return links;
    },
  },
  actions: {
    setTheme(theme: ThemeMode) {
      this.theme = theme;
      this.themePreferenceSaved = true;
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    },
    applyDefaultTheme(theme: ThemeMode) {
      if (!this.themePreferenceSaved) {
        this.theme = theme;
      }
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
    openGuide() {
      this.guideOpen = true;
    },
    closeGuide() {
      this.guideOpen = false;
      window.localStorage.setItem(GUIDE_STORAGE_KEY, "1");
    },
    setAppConfig(config: { features: { local_project_import: boolean }; deployment: DeploymentState }) {
      this.localProjectImportEnabled = Boolean(config.features.local_project_import);
      this.deployment = {
        icp_beian: config.deployment.icp_beian || "",
        icp_url: config.deployment.icp_url || "",
        gongan_beian: config.deployment.gongan_beian || "",
        gongan_url: config.deployment.gongan_url || "",
      };
    },
  },
});
