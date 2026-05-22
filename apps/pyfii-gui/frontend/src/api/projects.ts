import { requestJson } from "./client";
import type { ProjectMeta, SafetyResponse, TracksResponse } from "../renderer/types";

export interface ProjectCreateResponse extends ProjectMeta {
  warnings: string[];
}

export async function uploadProjectZip(file: File, fps: number, ignoreAcc: boolean): Promise<ProjectCreateResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("fps", String(fps));
  form.append("ignore_acc", String(ignoreAcc));

  return requestJson<ProjectCreateResponse>("/api/projects", {
    method: "POST",
    body: form,
  });
}

export async function fetchProject(projectId: string): Promise<ProjectMeta> {
  return requestJson<ProjectMeta>(`/api/projects/${projectId}`);
}

export async function fetchProjectTracks(projectId: string, fps: number): Promise<TracksResponse> {
  return requestJson<TracksResponse>(`/api/projects/${projectId}/tracks?fps=${fps}`);
}

export async function fetchProjectSafety(projectId: string): Promise<SafetyResponse> {
  return requestJson<SafetyResponse>(`/api/projects/${projectId}/safety`);
}

export async function deleteProject(projectId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
}
