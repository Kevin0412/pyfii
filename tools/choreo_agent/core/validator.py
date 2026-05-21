"""Validator — 四层验证 + 悬停检测"""
import subprocess
import sys
import warnings
from pathlib import Path
from dataclasses import dataclass, field

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = "/home/kevin0412/.conda/envs/pyfii/bin/python"


@dataclass
class ValidationResult:
    compile_ok: bool = False
    run_ok: bool = False
    read_fii_ok: bool = False
    distance_warnings: int = -1
    action_warnings: int = -1
    min_distance_cm: float | None = None
    xy_span: tuple[float, float] | None = None
    hover_segments: list[tuple[float, float]] = field(default_factory=list)
    error_message: str = ""

    @property
    def passed(self) -> bool:
        return (
            self.compile_ok
            and self.run_ok
            and self.read_fii_ok
            and self.distance_warnings == 0
            and self.action_warnings == 0
        )

    @property
    def hover_feedback(self) -> str:
        if not self.hover_segments:
            return ""
        parts = [f"{s:.0f}-{e:.0f}s" for s, e in self.hover_segments]
        return f"动作不丰富，存在整体悬停: {', '.join(parts)}。请增加 move2 或减少 delay/light 空闲时间。"

    def compute_assign_feedback(self, starts_xy, targets_xy):
        """计算 best_assign 并返回修复建议"""
        from core.best_assign import best_assign
        perm, min_d = best_assign(starts_xy, targets_xy)
        return f"使用排列 perm={perm} (min_d={min_d:.1f}cm) 替换当前恒等映射。"


def validate(script_path: Path, output_dir: Path) -> ValidationResult:
    result = ValidationResult()

    # 1. 语法层
    try:
        code = script_path.read_text(encoding="utf-8")
        compile(code, str(script_path), "exec")
        result.compile_ok = True
    except SyntaxError as e:
        result.error_message = f"Syntax error: {e}"
        return result

    # 2-4. 执行+读回+验收
    try:
        proc = subprocess.run(
            [PYTHON, str(script_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            result.error_message = proc.stderr[-500:]
            return result
        result.run_ok = True

        output = proc.stdout + proc.stderr
        for line in output.splitlines():
            if "dist:" in line and "act:" in line:
                for p in line.split():
                    if p.startswith("dist:"):
                        result.distance_warnings = int(p.split(":")[1])
                    if p.startswith("act:"):
                        result.action_warnings = int(p.split(":")[1])
            if "minD=" in line:
                for p in line.split():
                    if p.startswith("minD="):
                        result.min_distance_cm = float(p.split("=")[1].replace("cm", ""))
            if "XY(" in line:
                for p in line.split():
                    if p.startswith("XY("):
                        nums = p.strip("XY()").split(",")
                        result.xy_span = (float(nums[0]), float(nums[1]))

        if result.distance_warnings >= 0:
            result.read_fii_ok = True

        # 悬停检测
        result.hover_segments = _detect_hover(output_dir)

    except subprocess.TimeoutExpired:
        result.error_message = "Script timed out"
    except Exception as e:
        result.error_message = str(e)

    return result


def _detect_hover(output_dir: Path, threshold_cm: float = 5, min_duration_s: float = 2.0) -> list[tuple[float, float]]:
    """检测整体悬停：所有机位移 < threshold 持续 > min_duration_s"""
    import numpy as np
    import pyfii as pf

    fii_dir = output_dir
    if not (fii_dir / "动作组").exists():
        # 找子目录
        for child in fii_dir.iterdir():
            if child.is_dir() and (child / "动作组").exists():
                fii_dir = child
                break

    try:
        data, t0, *_ = pf.read_fii(str(fii_dir), fps=60, ignore_acc=True)
    except Exception:
        return []

    N = len(data)
    fps = 60
    min_frames = int(min_duration_s * fps)
    min_len = min(len(d) for d in data)

    hover_segments = []
    hover_start = None

    for frame in range(1, min_len):
        max_move = 0.0
        for i in range(N):
            if frame < len(data[i]):
                dx = abs(data[i][frame][1] - data[i][frame - 1][1])
                dy = abs(data[i][frame][2] - data[i][frame - 1][2])
                if dx > max_move:
                    max_move = dx
                if dy > max_move:
                    max_move = dy

        if max_move < threshold_cm:
            if hover_start is None:
                hover_start = frame
        else:
            if hover_start is not None and (frame - hover_start) >= min_frames:
                hover_segments.append((hover_start / fps, frame / fps))
            hover_start = None

    if hover_start is not None and (min_len - hover_start) >= min_frames:
        hover_segments.append((hover_start / fps, min_len / fps))

    return hover_segments
