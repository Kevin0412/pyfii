# -*- coding: utf-8 -*-
# 该文件封装 pyfii 的读取与渲染调用

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyfii.read import read_fii
from pyfii.show import show


@dataclass
class RenderResult:
    # 渲染结果索引：用于后续视觉检查输入
    output_video: str
    field: int
    device: str
    frame_count_hint: int


def render_project(project_path: str, save_path: str, fps: int = 25) -> RenderResult:
    # 读取 Fii 项目并输出 2D 渲染视频
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
        ThreeD=False,
        show=True,
    )
    return RenderResult(
        output_video=f"{save_path}.mp4",
        field=int(field),
        device=str(device),
        frame_count_hint=int(t0),
    )


def render_segment_like(
    project_path: str,
    save_path: str,
    start_sec: float,
    end_sec: float,
    fps: int = 25,
) -> RenderResult:
    # 当前 pyfii 原生 show 不直接按时间切片，这里先复用全量渲染接口并记录窗口信息
    # 后续可扩展为按 data 切片后再渲染
    _ = (start_sec, end_sec)
    return render_project(project_path=project_path, save_path=save_path, fps=fps)
