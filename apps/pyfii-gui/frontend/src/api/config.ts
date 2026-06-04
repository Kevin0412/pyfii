import { requestJson } from "./client";

export interface DeploymentConfig {
  icp_beian: string;
  icp_url: string;
  gongan_beian: string;
  gongan_url: string;
}

export interface AppConfig {
  title: string;
  features: {
    local_project_import: boolean;
  };
  deployment: DeploymentConfig;
}

export async function fetchAppConfig(): Promise<AppConfig> {
  return requestJson<AppConfig>("/api/config");
}
