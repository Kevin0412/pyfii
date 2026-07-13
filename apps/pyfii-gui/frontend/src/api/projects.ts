import { API_BASE_URL, requestJson } from "./client";
import type { ProjectMeta, SafetyResponse, TracksResponse } from "../renderer/types";

export interface ProjectCreateResponse extends ProjectMeta {
  warnings: string[];
}

export interface VideoExportRequest {
  render_mode: "classic2d" | "three3d";
  fps: number;
  render_scale: 1 | 2;
  projection: "orthographic" | "perspective";
  view_angle_a: number;
  view_angle_b: number;
  observer_distance: number;
  projection_distance: number;
}

export interface VideoExportResponse {
  export_id: string;
  project_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress_percent: number | null;
  filename: string;
  download_url: string | null;
  warnings: string[];
  error: string | null;
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

export async function importLocalProject(path: string, fps: number, ignoreAcc: boolean): Promise<ProjectCreateResponse> {
  return requestJson<ProjectCreateResponse>("/api/projects/local-path", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      path,
      fps,
      ignore_acc: ignoreAcc,
    }),
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

export function projectMusicUrl(projectId: string): string {
  return `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/music`;
}

export async function createVideoExport(
  projectId: string,
  options: VideoExportRequest,
): Promise<VideoExportResponse> {
  return requestJson<VideoExportResponse>(`/api/projects/${encodeURIComponent(projectId)}/video-exports`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(options),
  });
}

export async function fetchVideoExport(projectId: string, exportId: string): Promise<VideoExportResponse> {
  return requestJson<VideoExportResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/video-exports/${encodeURIComponent(exportId)}`,
  );
}

export function videoExportDownloadUrl(projectId: string, exportId: string): string {
  return `${API_BASE_URL}/api/projects/${encodeURIComponent(projectId)}/video-exports/${encodeURIComponent(exportId)}/download`;
}

export async function deleteProject(projectId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
}
