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

function savedTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "dark";
  }

  return window.localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark";
}

function savedLocale(): LocaleMode {
  if (typeof window === "undefined") {
    return "zh";
  }

  return window.localStorage.getItem(LOCALE_STORAGE_KEY) === "en" ? "en" : "zh";
}

export const useUiStore = defineStore("ui", {
  state: () => ({
    theme: savedTheme() as ThemeMode,
    locale: savedLocale() as LocaleMode,
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
