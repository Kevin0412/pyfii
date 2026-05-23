export type SafetyLevel = "ok" | "warning" | "error";
export type SafetyCategory = "action_incomplete" | "distance_51" | "distance_34" | "distance_17";

export interface MusicInfo {
  available: boolean;
  files: string[];
}

export interface SafetySummary {
  level: SafetyLevel;
  error_count: number;
  warning_count: number;
  min_distance_cm: number | null;
  category_counts: Partial<Record<SafetyCategory, number>>;
  max_category: SafetyCategory | null;
}

export interface ProjectMeta {
  project_id: string;
  name: string;
  field: number | null;
  device: string | null;
  drone_count: number;
  duration_ms: number;
  source_fps: number;
  frame_count: number;
  music: MusicInfo;
  safety_summary: SafetySummary;
}

export type DroneSample = [
  timeMs: number,
  xCm: number,
  yCm: number,
  zCm: number,
  yawDeg: number,
  ledR: number,
  ledG: number,
  ledB: number,
  accX: number,
  accY: number,
  accZ: number,
];

export interface DroneTrack {
  id: number;
  samples: DroneSample[];
}

export interface DroneFrame {
  id: number;
  timeMs: number;
  xCm: number;
  yCm: number;
  zCm: number;
  yawDeg: number;
  ledRgb: [number, number, number];
  acceleration: [number, number, number];
}

export interface RenderFrame {
  timeMs: number;
  drones: DroneFrame[];
}

export interface SafetyEvent {
  id: string;
  time_ms: number;
  frame: number;
  level: "warning" | "error";
  type: string;
  drone_a: number | null;
  drone_b: number | null;
  distance_cm: number | null;
  threshold_cm: number | null;
  category: SafetyCategory;
  category_label: string;
  category_rank: number;
  message: string;
  details: Record<string, unknown>;
}

export interface RenderOptions {
  selectedDroneId: number | null;
  showTrail: boolean;
  showSafetyMarkers: boolean;
  fps: number;
  playing: boolean;
}

export interface ThreeRenderSettings {
  projection: "orthographic" | "perspective";
  viewAngleA: number;
  viewAngleB: number;
  observerDistance: number;
  projectionDistance: number;
}

export interface RenderInput {
  meta: ProjectMeta | null;
  frame: RenderFrame;
  tracks: DroneTrack[];
  safetyEvents: SafetyEvent[];
  options: RenderOptions;
}

export interface TracksResponse {
  project_id: string;
  fps: number;
  duration_ms: number;
  field: number | null;
  device: string | null;
  drones: DroneTrack[];
}

export interface SafetyResponse {
  summary: SafetySummary;
  events: SafetyEvent[];
}
