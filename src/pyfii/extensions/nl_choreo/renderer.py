# -*- coding: utf-8 -*-
# 该文件封装 pyfii 的读取与渲染调用，并提供段级素材裁剪

from __future__ import annotations

from dataclasses import dataclass
import warnings

import cv2


@dataclass
class RenderResult:
    # 渲染结果索引：用于后续视觉检查输入
    output_video: str
    field: int
    device: str
    frame_count_hint: int
    warnings: list[str]


def render_project(project_path: str, save_path: str, fps: int = 25, three_d: bool = False) -> RenderResult:
    # 读取 Fii 项目并输出渲染视频（可选 3D）
    # 延迟导入，避免在无图形环境中仅导入模块就触发 pyautogui 初始化
    from pyfii.read import read_fii
    from pyfii.show import show

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data, t0, music, field, device = read_fii(project_path)
        show(
            data,
            t0,
            music,
            field=field,
            device=device,
            save=save_path,
            FPS=fps,
            max_fps=200,
            ThreeD=three_d,
            show=True,
        )

    warning_msgs = [str(w.message) for w in caught]
    return RenderResult(
        output_video=f"{save_path}.mp4",
        field=int(field),
        device=str(device),
        frame_count_hint=int(t0),
        warnings=warning_msgs,
    )


def cut_video_segment(source_video: str, output_video: str, start_sec: float, end_sec: float) -> str:
    # 按时间窗口裁剪段级视频，供 Qwen 局部检查
    if end_sec <= start_sec:
        raise ValueError("end_sec must be greater than start_sec")

    cap = cv2.VideoCapture(source_video)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open source video: {source_video}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    start_frame = max(0, int(start_sec * fps))
    end_frame = max(start_frame + 1, int(end_sec * fps))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx >= start_frame and idx < end_frame:
            writer.write(frame)
        if idx >= end_frame:
            break
        idx += 1

    writer.release()
    cap.release()
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
