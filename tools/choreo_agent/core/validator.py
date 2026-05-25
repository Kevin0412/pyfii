"""Validator — 四层验证 + 连贯性检测"""
import math
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path
from dataclasses import dataclass, field

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

DEFAULT_PYTHON = Path("/home/kevin0412/.conda/envs/pyfii/bin/python")
PYTHON = os.environ.get(
    "PYFII_AGENT_PYTHON",
    str(DEFAULT_PYTHON if DEFAULT_PYTHON.exists() else Path(sys.executable)),
)

HOVER_MOVE_THRESHOLD_CM_PER_FRAME = 0.2
MAX_GLOBAL_HOVER_S = 1.0
SEGMENT_EDGE_BUFFER_S = 1.0


@dataclass
class ValidationResult:
    compile_ok: bool = False
    run_ok: bool = False
    read_fii_ok: bool = False
    distance_warnings: int = -1
    action_warnings: int = -1
    min_distance_cm: float | None = None
    dense_min_distance_cm: float | None = None
    collision_intervals: list[dict] = field(default_factory=list)
    xy_span: tuple[float, float] | None = None
    continuity_required: bool = False
    hover_check_ok: bool = False
    hover_segments: list[tuple[float, float]] = field(default_factory=list)
    motion_start_s: float | None = None
    motion_end_s: float | None = None
    motion_envelope_ok: bool = True
    motion_envelope_errors: list[str] = field(default_factory=list)
    error_message: str = ""
    hover_error: str = ""
    continuity_error: str = ""

    @property
    def passed(self) -> bool:
        return (
            self.compile_ok
            and self.run_ok
            and self.read_fii_ok
            and self.distance_warnings == 0
            and self.action_warnings == 0
            and self.dense_min_distance_cm is not None
            and self.dense_min_distance_cm > 51
            and not self.collision_intervals
            and (
                not self.continuity_required
                or (
                    self.hover_check_ok
                    and not self.hover_segments
                    and self.motion_envelope_ok
                )
            )
        )

    @property
    def hover_feedback(self) -> str:
        if not self.continuity_required or not self.hover_segments:
            return ""
        parts = [f"{s:.2f}-{e:.2f}s({e - s:.2f}s)" for s, e in self.hover_segments]
        return (
            f"硬门失败：检测到超过 {MAX_GLOBAL_HOVER_S:.1f}s 的整体悬停: {', '.join(parts)}。"
            "这通常是代码结构问题：全体 move2 结束后接了过长 apply_light/delay。"
            "修复时不要只改颜色；请缩短 apply_light 到 ticks<=6，或把大几何拆成 A/B/C 分组并重叠 inittime，"
            "或在上述区间内插入小幅 move2/Z 变化，确保任意 1s 窗口至少一组无人机在运动。"
            "如果确实需要呼吸停顿，把全体静止压到 0.8s 内。"
        )

    def repair_feedback(self) -> str:
        """把验证失败转成可直接喂给 LLM 的修复反馈。"""
        hard_gate = (
            "硬门要求：compile=True, run=True, read_fii=True, distance warnings=0, "
            "action warnings=0, minD > 51cm"
        )
        if self.continuity_required:
            hard_gate += f", 无超过 {MAX_GLOBAL_HOVER_S:.1f}s 的整体悬停"
        lines = [
            "自动验证未通过，禁止进入下一步。请只重写当前未锁定段，不要修改 locked 段，不要输出 marker。",
            hard_gate + "。",
        ]
        if not self.compile_ok:
            lines.append(f"语法失败：{self.error_message[-500:]}")
            return "\n".join(lines)
        if not self.run_ok:
            lines.append(f"脚本执行失败：{self.error_message[-500:]}")
            return "\n".join(lines)
        if not self.read_fii_ok:
            lines.append(f"read_fii 未通过：{self.error_message[-500:]}")
            return "\n".join(lines)

        lines.append(f"distance warnings: {self.distance_warnings}")
        lines.append(f"action warnings: {self.action_warnings}")
        lines.append(f"minD: {self.min_distance_cm}cm")
        lines.append(f"dense minD: {self.dense_min_distance_cm}cm")
        lines.append(f"XY span: {self.xy_span}")
        if self.collision_intervals:
            lines.append("密采样危险区间（必须优先修复）：")
            for item in self.collision_intervals[:8]:
                pair = item.get("pair")
                lines.append(
                    f"- {item['start_s']:.2f}-{item['end_s']:.2f}s, "
                    f"min={item['min_distance_cm']:.1f}cm, pair={pair}"
                )
        if self.distance_warnings != 0:
            lines.append("距离风险：当前路径存在过近或对穿。请增大几何点间距、减少交叉换位、使用更保守的扇区保持或排队错峰。")
        if self.action_warnings != 0:
            lines.append("动作未完成风险：请延长时间预算、提前/推后 inittime、降低单次位移或提高合法速度/加速度。")
        hover = self.hover_feedback
        if hover:
            lines.append(hover)
        if self.hover_error:
            lines.append(f"悬停检测失败，因此禁止通过：{self.hover_error[-300:]}")
        if self.motion_start_s is not None or self.motion_end_s is not None:
            lines.append(f"motion window: start={self.motion_start_s}s end={self.motion_end_s}s")
        if self.motion_envelope_errors:
            lines.append("运动包络失败：")
            lines.extend(f"- {item}" for item in self.motion_envelope_errors)
        if self.continuity_error:
            lines.append(f"连贯性检测失败，因此禁止通过：{self.continuity_error[-300:]}")
        return "\n".join(lines)

    def compute_assign_feedback(self, starts_xy, targets_xy):
        """计算 best_assign 并返回修复建议"""
        from core.best_assign import best_assign
        perm, min_d = best_assign(starts_xy, targets_xy)
        return f"使用排列 perm={perm} (min_d={min_d:.1f}cm) 替换当前恒等映射。"


def validate(
    script_path: Path,
    output_dir: Path,
    quality_window: tuple[float, float] | None = None,
) -> ValidationResult:
    result = ValidationResult()
    result.continuity_required = quality_window is not None

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
        started_at = time.time()
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

        if not _output_updated(output_dir, started_at):
            result.error_message = f"Expected output dir was not updated: {output_dir}"
            return result

        if result.distance_warnings >= 0:
            result.read_fii_ok = True
            _add_dense_distance_report(result, output_dir)

        if result.continuity_required:
            try:
                result.hover_segments = _detect_hover(output_dir, window=quality_window)
                result.hover_check_ok = True
            except Exception as e:
                result.hover_error = str(e)
            try:
                result.motion_start_s, result.motion_end_s = _measure_motion_envelope(
                    output_dir,
                    window=quality_window,
                )
                result.motion_envelope_errors = _check_motion_envelope(
                    quality_window,
                    result.motion_start_s,
                    result.motion_end_s,
                )
                result.motion_envelope_ok = not result.motion_envelope_errors
            except Exception as e:
                result.motion_envelope_ok = False
                result.continuity_error = str(e)
        else:
            result.hover_check_ok = True

    except subprocess.TimeoutExpired:
        result.error_message = "Script timed out"
    except Exception as e:
        result.error_message = str(e)

    return result


def _detect_hover(
    output_dir: Path,
    threshold_cm: float = HOVER_MOVE_THRESHOLD_CM_PER_FRAME,
    min_duration_s: float = MAX_GLOBAL_HOVER_S,
    window: tuple[float, float] | None = None,
) -> list[tuple[float, float]]:
    """检测整体悬停：所有机 3D 位移都低于 threshold 且持续超过 min_duration_s。"""
    import pyfii as pf

    fii_dir = _find_fii_dir(output_dir)

    data, _t0, *_ = pf.read_fii(str(fii_dir), fps=60, ignore_acc=True)

    N = len(data)
    fps = 60
    min_frames = int(min_duration_s * fps)
    min_len = min(len(d) for d in data)
    start_frame = 1
    end_frame = min_len
    if window is not None:
        start_s, end_s = window
        start_frame = max(1, int(start_s * fps))
        end_frame = min(min_len, int(end_s * fps) + 1)
        if end_frame <= start_frame:
            return []

    hover_segments = []
    hover_start = None

    for frame in range(start_frame, end_frame):
        max_move = 0.0
        for i in range(N):
            if frame < len(data[i]):
                dx = abs(data[i][frame][1] - data[i][frame - 1][1])
                dy = abs(data[i][frame][2] - data[i][frame - 1][2])
                dz = abs(data[i][frame][3] - data[i][frame - 1][3])
                max_move = max(max_move, math.sqrt(dx * dx + dy * dy + dz * dz))

        if max_move < threshold_cm:
            if hover_start is None:
                hover_start = frame
        else:
            if hover_start is not None and (frame - hover_start) >= min_frames:
                hover_segments.append((hover_start / fps, frame / fps))
            hover_start = None

    if hover_start is not None and (end_frame - hover_start) >= min_frames:
        hover_segments.append((hover_start / fps, end_frame / fps))

    return hover_segments


def _measure_motion_envelope(
    output_dir: Path,
    window: tuple[float, float],
    threshold_cm: float = HOVER_MOVE_THRESHOLD_CM_PER_FRAME,
) -> tuple[float | None, float | None]:
    """返回当前时间窗内第一次/最后一次明显运动的时间。"""
    import pyfii as pf

    fii_dir = _find_fii_dir(output_dir)
    data, _t0, *_ = pf.read_fii(str(fii_dir), fps=60, ignore_acc=True)

    fps = 60
    min_len = min(len(d) for d in data)
    start_s, end_s = window
    start_frame = max(1, int(start_s * fps))
    end_frame = min(min_len, int(end_s * fps) + 1)
    first_motion = None
    last_motion = None

    for frame in range(start_frame, end_frame):
        if _frame_has_global_motion(data, frame, threshold_cm):
            time_s = frame / fps
            if first_motion is None:
                first_motion = time_s
            last_motion = time_s

    return (
        round(first_motion, 3) if first_motion is not None else None,
        round(last_motion, 3) if last_motion is not None else None,
    )


def _frame_has_global_motion(data, frame: int, threshold_cm: float) -> bool:
    for drone in data:
        if frame >= len(drone):
            continue
        dx = abs(drone[frame][1] - drone[frame - 1][1])
        dy = abs(drone[frame][2] - drone[frame - 1][2])
        dz = abs(drone[frame][3] - drone[frame - 1][3])
        if math.sqrt(dx * dx + dy * dy + dz * dz) >= threshold_cm:
            return True
    return False


def _check_motion_envelope(
    window: tuple[float, float],
    motion_start_s: float | None,
    motion_end_s: float | None,
) -> list[str]:
    start_s, end_s = window
    errors = []
    start_deadline = start_s + SEGMENT_EDGE_BUFFER_S
    end_floor = end_s - SEGMENT_EDGE_BUFFER_S

    if motion_start_s is None or motion_end_s is None:
        return [f"当前段 {start_s:.2f}-{end_s:.2f}s 内没有检测到明显运动。"]
    if motion_start_s >= start_deadline:
        errors.append(
            f"动作启动过晚：{motion_start_s:.2f}s；应在 {start_deadline:.2f}s 前开始运动。"
        )
    if motion_end_s <= end_floor:
        errors.append(
            f"动作收束过早：{motion_end_s:.2f}s；应在 {end_floor:.2f}s 后、{end_s:.2f}s 前完成收束。"
        )
    return errors


def _add_dense_distance_report(result: ValidationResult, output_dir: Path) -> None:
    """密采样距离报告，用于给 agent 直接反馈危险时间段。"""
    import pyfii as pf

    try:
        fii_dir = _find_fii_dir(output_dir)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data, *_ = pf.read_fii(str(fii_dir), fps=60, ignore_acc=False)
    except Exception:
        return

    if not data:
        return

    fps = 60
    min_len = min(len(drone) for drone in data)
    if min_len <= 0:
        return

    rows = []
    dense_min = float("inf")
    for frame in range(min_len):
        frame_min = float("inf")
        frame_pair = None
        positions = []
        for drone in data:
            positions.append((drone[frame][1], drone[frame][2]))

        for i in range(len(positions)):
            x1, y1 = positions[i]
            if x1 <= 0:
                continue
            for j in range(i + 1, len(positions)):
                x2, y2 = positions[j]
                if x2 <= 0:
                    continue
                distance = math.hypot(x1 - x2, y1 - y2)
                if 0 < distance < frame_min:
                    frame_min = distance
                    frame_pair = (i, j)

        if frame_min < dense_min:
            dense_min = frame_min
        if frame_min < 51:
            rows.append((frame / fps, frame_min, frame_pair))

    if dense_min != float("inf"):
        result.dense_min_distance_cm = round(dense_min, 1)
        result.min_distance_cm = result.dense_min_distance_cm
    result.collision_intervals = _compress_collision_rows(rows)


def _compress_collision_rows(rows: list[tuple[float, float, tuple[int, int] | None]]) -> list[dict]:
    if not rows:
        return []

    intervals = []
    start_s = rows[0][0]
    prev_s = rows[0][0]
    min_row = rows[0]

    for row in rows[1:]:
        time_s, distance, _pair = row
        if time_s - prev_s <= (1 / 60) + 1e-9:
            prev_s = time_s
            if distance < min_row[1]:
                min_row = row
            continue

        intervals.append(_collision_interval(start_s, prev_s, min_row))
        start_s = time_s
        prev_s = time_s
        min_row = row

    intervals.append(_collision_interval(start_s, prev_s, min_row))
    return intervals


def _collision_interval(start_s: float, end_s: float, min_row: tuple[float, float, tuple[int, int] | None]) -> dict:
    return {
        "start_s": round(start_s, 3),
        "end_s": round(end_s, 3),
        "min_time_s": round(min_row[0], 3),
        "min_distance_cm": round(min_row[1], 1),
        "pair": min_row[2],
    }


def _find_fii_dir(output_dir: Path) -> Path:
    if (output_dir / "动作组").exists():
        return output_dir
    for child in output_dir.iterdir():
        if child.is_dir() and (child / "动作组").exists():
            return child
    return output_dir


def _output_updated(output_dir: Path, started_at: float) -> bool:
    if not output_dir.exists():
        return False
    latest = 0.0
    for path in output_dir.rglob("*"):
        if path.is_file():
            latest = max(latest, path.stat().st_mtime)
    return latest >= started_at - 1.0
