# -*- coding: utf-8 -*-
# 该文件封装 pyfii 的读取与渲染调用，并提供段级素材裁剪

from __future__ import annotations

from dataclasses import dataclass
import subprocess
import warnings


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

    duration = max(0.05, end_sec - start_sec)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        source_video,
        "-t",
        f"{duration:.3f}",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_video,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"cut segment failed: {proc.stderr.strip()}")
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
