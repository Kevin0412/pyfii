from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


JsonNumber = Union[int, float]


class MusicInfo(BaseModel):
    available: bool
    files: List[str] = Field(default_factory=list)


class SafetySummary(BaseModel):
    level: Literal["ok", "warning", "error"]
    error_count: int
    warning_count: int
    min_distance_cm: Optional[float] = None
    category_counts: Dict[str, int] = Field(default_factory=dict)
    max_category: Optional[
        Literal[
            "core_warning",
            "action_incomplete",
            "distance_51",
            "distance_34",
            "distance_17",
        ]
    ] = None


class ProjectMeta(BaseModel):
    project_id: str
    name: str
    field: Optional[int] = None
    device: Optional[str] = None
    drone_count: int
    duration_ms: float
    source_fps: int
    frame_count: int
    music: MusicInfo
    safety_summary: SafetySummary


class ProjectCreateResponse(ProjectMeta):
    warnings: List[str] = Field(default_factory=list)


class LocalProjectCreateRequest(BaseModel):
    path: str
    fps: int = 60
    ignore_acc: bool = False


class FeatureFlags(BaseModel):
    local_project_import: bool


class DeploymentInfo(BaseModel):
    icp_beian: str = ""
    icp_url: str = ""
    gongan_beian: str = ""
    gongan_url: str = ""


class AppConfigResponse(BaseModel):
    title: str
    features: FeatureFlags
    deployment: DeploymentInfo


class DroneTrackResponse(BaseModel):
    id: int
    samples: List[List[JsonNumber]]


class TracksResponse(BaseModel):
    project_id: str
    fps: int
    duration_ms: float
    field: Optional[int] = None
    device: Optional[str] = None
    drones: List[DroneTrackResponse]


class SafetyEvent(BaseModel):
    id: str
    time_ms: float
    frame: int
    level: Literal["warning", "error"]
    type: str
    drone_a: Optional[int] = None
    drone_b: Optional[int] = None
    distance_cm: Optional[float] = None
    threshold_cm: Optional[float] = None
    category: Literal[
        "core_warning",
        "action_incomplete",
        "distance_51",
        "distance_34",
        "distance_17",
    ]
    category_label: str
    category_rank: int
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class SafetyResponse(BaseModel):
    summary: SafetySummary
    events: List[SafetyEvent]


class VideoExportRequest(BaseModel):
    render_mode: Literal["classic2d", "three3d"] = "classic2d"
    fps: int = Field(default=30, ge=1, le=60)
    render_scale: Literal[1, 2] = 1
    projection: Literal["orthographic", "perspective"] = "perspective"
    view_angle_a: float = Field(default=90, ge=-180, le=180)
    view_angle_b: float = Field(default=3, ge=-90, le=90)
    observer_distance: float = Field(default=600, gt=0)
    projection_distance: float = Field(default=450, gt=0)


class VideoExportResponse(BaseModel):
    export_id: str
    project_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress_percent: Optional[float] = None
    filename: str
    download_url: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class DeleteResponse(BaseModel):
    ok: bool
