# -*- coding: utf-8 -*-
# 该文件封装 pyfii 的读取与渲染调用，并提供段级素材裁剪

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import warnings
from typing import Any


@dataclass
class RenderResult:
    # 渲染结果索引：用于后续视觉检查输入
    output_video: str
    field: int
    device: str
    frame_count_hint: int
    warnings: list[str]


def _timing_fps_for_render(three_d: bool) -> int:
    # read_fii 与 show.max_fps 必须同源，避免节拍采样漂移
    return 60 if three_d else 200


def _build_show_kwargs(
    *,
    field: int,
    device: str,
    save_path: str,
    fps: int,
    three_d: bool,
    timing_fps: int,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "field": field,
        "device": device,
        "save": save_path,
        "FPS": int(fps),
        "max_fps": int(timing_fps),
        "ThreeD": bool(three_d),
        "show": True,
    }
    if three_d:
        kwargs.update(
            {
                "FPS": max(60, int(fps)),
                "imshow": [90, 3],
                "d": (600, 500),
            }
        )
    return kwargs


def _render_with_shared_track(
    *,
    project_path: str,
    variants: list[tuple[str, bool, int]],
) -> tuple[RenderResult, dict[str, RenderResult]]:
    # 一次 read_fii，按给定变体多次 show（例如 2D/3D）
    from pyfii.read import read_fii
    from pyfii.show import show

    if not variants:
        raise ValueError("variants cannot be empty")

    timing_fps = _timing_fps_for_render(three_d=any(v[1] for v in variants))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, t0, music, field, device = read_fii(project_path, fps=timing_fps)

        results: dict[str, RenderResult] = {}
        for save_path, three_d, fps in variants:
            show_kwargs = _build_show_kwargs(
                field=int(field),
                device=str(device),
                save_path=save_path,
                fps=int(fps),
                three_d=bool(three_d),
                timing_fps=timing_fps,
            )
            show(data, t0, music, **show_kwargs)
            results[save_path] = RenderResult(
                output_video=f"{save_path}.mp4",
                field=int(field),
                device=str(device),
                frame_count_hint=int(t0),
                warnings=[],
            )

    warning_msgs = [str(w.message) for w in caught]
    for key, item in list(results.items()):
        results[key] = RenderResult(
            output_video=item.output_video,
            field=item.field,
            device=item.device,
            frame_count_hint=item.frame_count_hint,
            warnings=warning_msgs,
        )

    first_save = variants[0][0]
    return results[first_save], results


def render_project(project_path: str, save_path: str, fps: int = 25, three_d: bool = False) -> RenderResult:
    # 读取 Fii 项目并输出渲染视频（可选 3D）
    result, _ = _render_with_shared_track(
        project_path=project_path,
        variants=[(save_path, three_d, int(fps))],
    )
    return result


def render_project_pair(project_path: str, save_path_2d: str, save_path_3d: str, fps: int = 25) -> tuple[RenderResult, RenderResult]:
    # 一次 read_fii 同时输出 2D/3D，确保两者与同一 timing_fps 对齐
    _, results = _render_with_shared_track(
        project_path=project_path,
        variants=[
            (save_path_2d, False, int(fps)),
            (save_path_3d, True, int(fps)),
        ],
    )
    return results[save_path_2d], results[save_path_3d]


def cut_video_segment(source_video: str, output_video: str, start_sec: float, end_sec: float) -> str:
    # 按时间窗口裁剪段级视频，供 Qwen 局部检查
    if end_sec <= start_sec:
        raise ValueError("end_sec must be greater than start_sec")

    src_probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            source_video,
        ],
        capture_output=True,
        text=True,
    )
    if src_probe.returncode != 0:
        raise RuntimeError(f"ffprobe failed for source: {src_probe.stderr.strip()}")
    src_info = json.loads(src_probe.stdout or "{}")
    src_duration = float((src_info.get("format") or {}).get("duration") or 0.0)
    if src_duration <= 0.0:
        raise RuntimeError(f"source video duration invalid: {source_video}")

    safe_start = max(0.0, min(float(start_sec), max(0.0, src_duration - 0.05)))
    safe_end = max(safe_start + 0.05, min(float(end_sec), src_duration))
    duration = max(0.05, safe_end - safe_start)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{safe_start:.3f}",
        "-i",
        source_video,
        "-t",
        f"{duration:.3f}",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "baseline",
        "-level",
        "3.1",
        "-g",
        "30",
        "-bf",
        "0",
        "-movflags",
        "+faststart",
        output_video,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"cut segment failed: {proc.stderr.strip()}")

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            output_video,
        ],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise RuntimeError(f"ffprobe failed for segment: {probe.stderr.strip()}")
    info = json.loads(probe.stdout or "{}")
    streams = info.get("streams", [])
    if not streams:
        raise RuntimeError(f"segment has no video stream: {output_video}")
    return output_video


def render_segment_like(
    project_path: str,
    save_path: str,
    start_sec: float,
    end_sec: float,
    fps: int = 25,
) -> RenderResult:
    # 先渲染完整视频，再裁剪目标片段，实现段级可检查素材
    full_save = f"{save_path}_full"
    full_result = render_project(project_path=project_path, save_path=full_save, fps=fps)
    clipped = cut_video_segment(
        source_video=full_result.output_video,
        output_video=f"{save_path}.mp4",
        start_sec=start_sec,
        end_sec=end_sec,
    )
    return RenderResult(
        output_video=clipped,
        field=full_result.field,
        device=full_result.device,
        frame_count_hint=full_result.frame_count_hint,
        warnings=full_result.warnings,
    )
