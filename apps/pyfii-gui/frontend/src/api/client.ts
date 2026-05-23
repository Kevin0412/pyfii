function normalizeApiBaseUrl(value: string | undefined): string {
  const baseUrl = value?.trim() || "";
  if (baseUrl === "/") {
    return "";
  }
  return baseUrl.replace(/\/$/, "");
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const apiPayload = payload as ApiErrorPayload;
    const error = apiPayload.error;
    throw new ApiError(
      response.status,
      error?.code || "request_failed",
      error?.message || response.statusText,
      error?.details || {},
    );
  }

  return payload as T;
}
