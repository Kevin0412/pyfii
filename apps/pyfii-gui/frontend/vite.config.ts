import { readFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

const envDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(envDir, "../../..");

function deploymentDomain(): string | undefined {
  const configuredPath = process.env.PYFII_GUI_DEPLOY_CONFIG;
  const configPath = configuredPath
    ? isAbsolute(configuredPath)
      ? configuredPath
      : resolve(repoRoot, configuredPath)
    : resolve(envDir, "../deploy.json");

  try {
    const config = JSON.parse(readFileSync(configPath, "utf-8")) as { domain?: unknown };
    const domain = typeof config.domain === "string" ? config.domain.trim() : "";
    return domain || undefined;
  } catch {
    return undefined;
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envDir, "");
  const devPort = Number.parseInt(env.VITE_DEV_PORT || "5173", 10);
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://localhost:8000";
  const allowedDomain = deploymentDomain();

  return {
    plugins: [vue()],
    server: {
      host: env.VITE_DEV_HOST || "0.0.0.0",
      port: Number.isNaN(devPort) ? 5173 : devPort,
      allowedHosts: allowedDomain ? [allowedDomain] : [],
      fs: {
        // Allow the dev server to serve markdown & image assets from the
        // repository root (e.g. doc/**).  Vite 8 tightened the default
        // allow-list to the project root only.
        allow: [envDir, repoRoot],
      },
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      allowedHosts: allowedDomain ? [allowedDomain] : [],
    },
  };
});
