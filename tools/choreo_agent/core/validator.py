"""Validator — 四层验证 + 连贯性检测"""
import ast
import math
import os
import re
import subprocess
import sys
import time
import warnings
from statistics import median
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
EFFECTIVE_MOVE_THRESHOLD_CM_PER_FRAME = 0.35
MIN_EFFECTIVE_TOTAL_MOVE_CM_PER_FRAME = 1.0
MIN_EFFECTIVE_ACTIVE_DRONES = 2
MAX_GLOBAL_HOVER_S = 1.0
SEGMENT_EDGE_BUFFER_S = 1.0
MIN_MEANINGFUL_EXCURSION_CM = 30.0
MIN_MOVING_DRONE_FRACTION = 0.7
AGENT_SIDE_HELPERS = {
    "assign_targets",
    "best_assign",
    "budget_layer",
    "budget_layers",
    "dist3",
    "flight_time_s",
    "flight_time_ms",
    "speed_for_interval",
    "timeline_cues",
    "to_xyz",
    "move_interval",
}


@dataclass
class ValidationResult:
    compile_ok: bool = False
    run_ok: bool = False
    read_fii_ok: bool = False
    distance_warnings: int = -1
    action_warnings: int = -1
    action_details: list[str] = field(default_factory=list)
    min_distance_cm: float | None = None
    dense_min_distance_cm: float | None = None
    collision_intervals: list[dict] = field(default_factory=list)
    xy_span: tuple[float, float] | None = None
    quality_window: tuple[float, float] | None = None
    continuity_required: bool = False
    hover_check_ok: bool = False
    hover_segments: list[tuple[float, float]] = field(default_factory=list)
    motion_start_s: float | None = None
    motion_end_s: float | None = None
    motion_envelope_ok: bool = True
    motion_envelope_errors: list[str] = field(default_factory=list)
    effective_motion_start_s: float | None = None
    effective_motion_end_s: float | None = None
    effective_motion_ok: bool = True
    effective_motion_errors: list[str] = field(default_factory=list)
    low_activity_segments: list[tuple[float, float]] = field(default_factory=list)
    motion_quality_ok: bool = True
    motion_quality: dict = field(default_factory=dict)
    motion_quality_errors: list[str] = field(default_factory=list)
    degradation_ok: bool = True
    degradation: dict = field(default_factory=dict)
    degradation_errors: list[str] = field(default_factory=list)
    code_quality_ok: bool = True
    code_quality_errors: list[str] = field(default_factory=list)
    exit_state: list[list[int]] | None = None
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
            and self.code_quality_ok
            and (
                not self.continuity_required
                or (
                    self.hover_check_ok
                    and not self.hover_segments
                    and self.motion_envelope_ok
                    and self.effective_motion_ok
                    and not self.low_activity_segments
                    and self.motion_quality_ok
                    and self.degradation_ok
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
            "这通常是时间线建模问题：真实移动已经结束，后面只剩无运动覆盖的 apply_light/delay。"
            "修复时不要只改颜色；请把段落重排成 move2 -> 短灯光/执行等待 -> move2 的 per-drone 链，"
            "按 3D 距离和速度/加速度计算每个移动的执行时间，并用分组错峰或真实 keyframe 移动覆盖该区间。"
            "如果确实需要呼吸停顿，把全体静止压到 0.8s 内。"
        )

    def repair_feedback(self) -> str:
        """把验证失败转成可直接喂给 LLM 的修复反馈。"""
        hard_gate = (
            "硬门要求：compile=True, run=True, read_fii=True, distance warnings=0, "
            "action warnings=0, minD > 51cm"
        )
        if self.continuity_required:
            hard_gate += (
                f", 无超过 {MAX_GLOBAL_HOVER_S:.1f}s 的整体悬停"
                f", 无超过 {MAX_GLOBAL_HOVER_S:.1f}s 的低活动区间"
            )
        lines = [
            "自动验证未通过，禁止进入下一步。请只重写当前未锁定段，不要修改 locked 段，不要输出 marker。",
            hard_gate + "。",
        ]
        if not self.compile_ok:
            lines.append(f"语法失败：{self.error_message[-500:]}")
            return "\n".join(lines)
        if self.code_quality_errors:
            lines.append("代码结构失败：")
            lines.extend(f"- {item}" for item in self.code_quality_errors)
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
            details = ", ".join(self.action_details[:10]) if self.action_details else "unknown"
            lines.append(
                f"动作未完成风险：{self.action_warnings} 个警告。受影响: {details}。"
                "每个 move2 后 delay 必须基于距离计算：\n"
                "  d = sqrt((tx-prev_x)^2+(ty-prev_y)^2+(tz-prev_z)^2)\n"
                "  drone.move2(tx, ty, tz)\n"
                "  apply_light(drone, color, ticks)\n"
                "  drone.delay(flight_time_ms(d, v, a) - ticks*100 + 200)\n"
                "不要用固定 delay 混过去。"
            )
        

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
    result.quality_window = quality_window
    result.continuity_required = quality_window is not None

    # 1. 语法层
    try:
        code = script_path.read_text(encoding="utf-8")
        compile(code, str(script_path), "exec")
        result.compile_ok = True
    except SyntaxError as e:
        result.error_message = f"Syntax error: {e}"
        return result

    active_code = _extract_first_unlocked_segment_code(code) or code
    result.code_quality_errors = _check_static_code_quality(active_code)
    result.code_quality_ok = not result.code_quality_errors

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
        # 解析动作详情
        result.action_details = _parse_action_warnings(output)
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
            result.exit_state = _sample_exit_state(
                output_dir,
                time_s=quality_window[1] if quality_window is not None else None,
            )

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
                (
                    result.effective_motion_start_s,
                    result.effective_motion_end_s,
                    result.low_activity_segments,
                ) = _measure_effective_motion(
                    output_dir,
                    window=quality_window,
                )
                result.effective_motion_errors = _check_effective_motion(
                    quality_window,
                    result.effective_motion_start_s,
                    result.effective_motion_end_s,
                    result.low_activity_segments,
                )
                result.effective_motion_ok = not result.effective_motion_errors
                result.motion_quality = _measure_motion_quality(
                    output_dir,
                    window=quality_window,
                )
                result.motion_quality_errors = _check_motion_quality(
                    quality_window,
                    result.motion_quality,
                )
                result.motion_quality_ok = not result.motion_quality_errors
                result.degradation = _measure_degradation(
                    output_dir,
                    window=quality_window,
                )
                result.degradation_errors = _check_degradation(
                    quality_window,
                    result.degradation,
                )
                result.degradation_ok = not result.degradation_errors
            except Exception as e:
                result.motion_envelope_ok = False
                result.effective_motion_ok = False
                result.motion_quality_ok = False
                result.degradation_ok = False
                result.continuity_error = str(e)
        else:
            result.hover_check_ok = True

    except subprocess.TimeoutExpired:
        result.error_message = "Script timed out"
    except Exception as e:
        result.error_message = str(e)

    return result


def _check_static_code_quality(code: str) -> list[str]:
    tree = ast.parse(code)
    return [
        *_check_segment_imports(tree),
        *_check_agent_helper_leak_from_tree(tree),
        *_check_inittime_arguments(tree),
        *_check_velocity_pairing(tree),
    ]


def _check_agent_helper_leak(code: str) -> list[str]:
    return _check_agent_helper_leak_from_tree(ast.parse(code))


def _check_agent_helper_leak_from_tree(tree: ast.AST) -> list[str]:
    leaked = sorted(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in AGENT_SIDE_HELPERS
    )
    if not leaked:
        return []
    names = ", ".join(leaked)
    return [
        f"不要在 design.py/segment 中定义 agent 侧运动学工具函数：{names}。"
        "请先在 agent 侧估算 3D distance/flight time，再把具体 speed/accel/delay 写入段代码。"
    ]


def _check_segment_imports(tree: ast.AST) -> list[str]:
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            errors.append(
                f"line {node.lineno}: 当前 segment 不要新增 import。"
                "design.py 模板已提供 math/numpy/pyfii 等基础依赖；排列和运动预算应在 agent 侧完成。"
            )
    return errors


def _repair_timing_plan(
    quality_window: tuple[float, float] | None,
    motion_start_s: float | None,
    motion_end_s: float | None,
) -> str:
    if quality_window is None:
        return ""
    start_s, end_s = quality_window
    finish_floor = end_s - SEGMENT_EDGE_BUFFER_S
    lines = []
    if motion_start_s is not None and motion_start_s >= start_s + SEGMENT_EDGE_BUFFER_S:
        lines.append(
            f"- 启动晚了 {motion_start_s - (start_s + SEGMENT_EDGE_BUFFER_S):.2f}s："
            f"首个正式 move2 应在 {start_s:.2f}s 后尽快发起，通常使用 inittime({int(start_s)})。"
        )
    if motion_end_s is not None and motion_end_s <= finish_floor:
        missing_s = finish_floor - motion_end_s
        lines.append(
            f"- 收束早了约 {missing_s:.2f}s：不要补纯 delay；"
            "请把这段时间分配给真实移动，做法是降低 speed/accel、加入第 4/5 个有构图意义的 keyframe，"
            "或拉长弧线路径/高度层变化。"
        )
    if not lines:
        return ""
    lines.append(
        f"- 重新规划时，所有无人机的 move/light/delay 累计预算应让有效群体运动结束在 "
        f"{finish_floor:.2f}-{end_s:.2f}s。"
    )
    return "段落时间预算修复建议：\n" + "\n".join(lines)


def _check_inittime_arguments(tree: ast.AST) -> list[str]:
    errors = []
    constants = _constant_assignments(tree)
    for node in ast.walk(tree):
        if not _is_method_call(node, "inittime") or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, float):
            errors.append(
                f"line {node.lineno}: inittime() 必须使用整数秒，不要写 {arg.value!r}。"
                "例如写 drone.inittime(4)，不要写 drone.inittime(4.0) 或 6.2。"
            )
        if isinstance(arg, ast.Name) and isinstance(constants.get(arg.id), float):
            errors.append(
                f"line {node.lineno}: inittime({arg.id}) 使用了浮点变量 {arg.id}={constants[arg.id]!r}。"
                f"请把 {arg.id} 定义为整数秒，例如 {arg.id} = {int(constants[arg.id])}。"
            )
    return errors


def _constant_assignments(tree: ast.AST) -> dict[str, object]:
    values = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                values[target.id] = node.value.value
    return values


def _check_velocity_pairing(tree: ast.AST) -> list[str]:
    calls = [
        {
            "line": node.lineno,
            "method": node.func.attr,
            "receiver": _node_key(node.func.value),
            "display": _node_display(node.func.value),
            "args": [_node_key(arg) for arg in node.args[:2]],
        }
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"VelXY", "VelZ"}
    ]
    errors = []
    for call in calls:
        if call["method"] != "VelXY":
            continue
        paired = [
            other
            for other in calls
            if other["method"] == "VelZ"
            and other["receiver"] == call["receiver"]
            and 0 <= other["line"] - call["line"] <= 3
        ]
        if not paired:
            errors.append(
                f"line {call['line']}: {call['display']}.VelXY(...) 后应在附近成对设置 "
                "VelZ(...), 并使用同一组 speed/accel，以兼容原始 XML/回放速度语义。"
            )
            continue
        nearest = min(paired, key=lambda item: item["line"] - call["line"])
        if len(call["args"]) == 2 and len(nearest["args"]) == 2 and call["args"] != nearest["args"]:
            errors.append(
                f"line {call['line']}: VelXY 与 line {nearest['line']} 的 VelZ 参数不同；"
                "同一 keyframe 最好使用同一组 speed/accel。"
            )
    return errors


def _is_method_call(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    )


def _node_key(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=False, include_attributes=False)


def _node_display(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return _node_key(node)


def _extract_first_unlocked_segment_code(code: str) -> str:
    match = re.search(
        r"^# === PYFII_AGENT_SEGMENT_START[^\n]*locked=false[^\n]* ===\n"
        r"(?P<body>.*?)"
        r"^# === PYFII_AGENT_SEGMENT_END[^\n]* ===",
        code,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group("body") if match else ""


def _detect_hover(
    output_dir: Path,
    threshold_cm: float = HOVER_MOVE_THRESHOLD_CM_PER_FRAME,
    min_duration_s: float = MAX_GLOBAL_HOVER_S,
    window: tuple[float, float] | None = None,
) -> list[tuple[float, float]]:
    """检测整体悬停：所有机 3D 位移都低于 threshold 且持续超过 min_duration_s。"""
    import pyfii as pf

    fii_dir = _find_fii_dir(output_dir)

    data, _t0, *_ = _cached_read_fii(str(fii_dir))

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
    data, _t0, *_ = _cached_read_fii(str(fii_dir))

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


def _measure_effective_motion(
    output_dir: Path,
    window: tuple[float, float],
) -> tuple[float | None, float | None, list[tuple[float, float]]]:
    """检测有效群体运动：过滤单机慢挪、小幅抖动和尾部凑时长。"""
    import pyfii as pf

    fii_dir = _find_fii_dir(output_dir)
    data, _t0, *_ = _cached_read_fii(str(fii_dir))

    fps = 60
    min_len = min(len(d) for d in data)
    start_s, end_s = window
    start_frame = max(1, int(start_s * fps))
    end_frame = min(min_len, int(end_s * fps) + 1)
    if end_frame <= start_frame:
        return None, None, []

    min_frames = int(MAX_GLOBAL_HOVER_S * fps)
    first_effective = None
    last_effective = None
    low_segments = []
    low_start = None

    for frame in range(start_frame, end_frame):
        active_drones = 0
        total_move = 0.0
        for drone in data:
            if frame >= len(drone):
                continue
            move = _frame_move_cm(drone, frame)
            total_move += move
            if move >= EFFECTIVE_MOVE_THRESHOLD_CM_PER_FRAME:
                active_drones += 1

        effective = (
            active_drones >= MIN_EFFECTIVE_ACTIVE_DRONES
            and total_move >= MIN_EFFECTIVE_TOTAL_MOVE_CM_PER_FRAME
        )
        if effective:
            time_s = frame / fps
            if first_effective is None:
                first_effective = time_s
            last_effective = time_s
            if low_start is not None and (frame - low_start) >= min_frames:
                low_segments.append((low_start / fps, frame / fps))
            low_start = None
        elif low_start is None:
            low_start = frame

    if low_start is not None and (end_frame - low_start) >= min_frames:
        low_segments.append((low_start / fps, end_frame / fps))

    return (
        round(first_effective, 3) if first_effective is not None else None,
        round(last_effective, 3) if last_effective is not None else None,
        low_segments,
    )


def _frame_move_cm(drone, frame: int) -> float:
    dx = abs(drone[frame][1] - drone[frame - 1][1])
    dy = abs(drone[frame][2] - drone[frame - 1][2])
    dz = abs(drone[frame][3] - drone[frame - 1][3])
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _check_effective_motion(
    window: tuple[float, float],
    effective_start_s: float | None,
    effective_end_s: float | None,
    low_activity_segments: list[tuple[float, float]],
) -> list[str]:
    start_s, end_s = window
    errors = []
    start_deadline = start_s + SEGMENT_EDGE_BUFFER_S
    end_floor = end_s - SEGMENT_EDGE_BUFFER_S

    if effective_start_s is None or effective_end_s is None:
        return [f"当前段 {start_s:.2f}-{end_s:.2f}s 内没有检测到有效群体运动。"]
    if effective_start_s >= start_deadline:
        errors.append(
            f"有效群体运动启动过晚：{effective_start_s:.2f}s；应在 {start_deadline:.2f}s 前开始。"
        )
    if effective_end_s <= end_floor:
        errors.append(
            f"有效群体运动收束过早：{effective_end_s:.2f}s；应在 {end_floor:.2f}s 后、{end_s:.2f}s 前完成。"
        )
    if low_activity_segments:
        errors.append(
            f"检测到 {len(low_activity_segments)} 个超过 {MAX_GLOBAL_HOVER_S:.1f}s 的低活动区间；"
            "这些区间虽然可能有少量位移，但不足以算整体编舞运动。"
        )
    return errors


def _measure_motion_quality(
    output_dir: Path,
    window: tuple[float, float],
) -> dict:
    """衡量有效动作幅度，防止用小范围抖动通过连续性门。"""
    import pyfii as pf

    fii_dir = _find_fii_dir(output_dir)
    data, _t0, *_ = _cached_read_fii(str(fii_dir))

    fps = 60
    min_len = min(len(d) for d in data)
    start_s, end_s = window
    start_frame = max(1, int(start_s * fps))
    end_frame = min(min_len, int(end_s * fps) + 1)
    if end_frame <= start_frame:
        return {}

    paths = []
    excursions = []
    xy_excursions = []
    for drone in data:
        start = _point3(drone[start_frame])
        last = start
        path_len = 0.0
        max_excursion = 0.0
        max_xy_excursion = 0.0
        for frame in range(start_frame + 1, end_frame):
            current = _point3(drone[frame])
            path_len += math.dist(last, current)
            max_excursion = max(max_excursion, math.dist(start, current))
            max_xy_excursion = max(
                max_xy_excursion,
                math.hypot(current[0] - start[0], current[1] - start[1]),
            )
            last = current
        paths.append(path_len)
        excursions.append(max_excursion)
        xy_excursions.append(max_xy_excursion)

    moving_drones = sum(1 for value in excursions if value >= MIN_MEANINGFUL_EXCURSION_CM)
    return {
        "drone_count": len(data),
        "moving_drones": moving_drones,
        "median_path_cm": round(median(paths), 1) if paths else 0.0,
        "median_excursion_cm": round(median(excursions), 1) if excursions else 0.0,
        "max_excursion_cm": round(max(excursions), 1) if excursions else 0.0,
        "median_xy_excursion_cm": round(median(xy_excursions), 1) if xy_excursions else 0.0,
        "path_lengths_cm": [round(value, 1) for value in paths],
        "excursions_cm": [round(value, 1) for value in excursions],
    }


def _point3(row) -> tuple[float, float, float]:
    return (float(row[1]), float(row[2]), float(row[3]))


def _check_motion_quality(
    window: tuple[float, float],
    quality: dict,
) -> list[str]:
    if not quality:
        return ["无法计算有效动作质量。"]

    start_s, end_s = window
    duration = max(0.1, end_s - start_s)
    drone_count = int(quality.get("drone_count", 0))
    min_moving = max(1, math.ceil(drone_count * MIN_MOVING_DRONE_FRACTION))
    min_median_path = max(80.0, min(180.0, duration * 8.0))
    min_median_excursion = max(45.0, min(90.0, duration * 4.0))
    min_max_excursion = max(90.0, min(180.0, duration * 8.0))

    errors = []
    moving_drones = int(quality.get("moving_drones", 0))
    median_path = float(quality.get("median_path_cm", 0.0))
    median_excursion = float(quality.get("median_excursion_cm", 0.0))
    max_excursion = float(quality.get("max_excursion_cm", 0.0))

    if moving_drones < min_moving:
        errors.append(
            f"有效运动无人机过少：{moving_drones}/{drone_count}；至少 {min_moving} 架需要离入口位置超过 {MIN_MEANINGFUL_EXCURSION_CM:.0f}cm。"
        )
    if median_path < min_median_path:
        errors.append(
            f"中位路径长度过短：{median_path:.1f}cm；当前 {duration:.1f}s 段至少需要 {min_median_path:.1f}cm，避免小范围抖动。"
        )
    if median_excursion < min_median_excursion:
        errors.append(
            f"中位最大位移过小：{median_excursion:.1f}cm；至少需要 {min_median_excursion:.1f}cm 的离位动作。"
        )
    if max_excursion < min_max_excursion:
        errors.append(
            f"全队最大位移过小：{max_excursion:.1f}cm；至少需要一组展开到 {min_max_excursion:.1f}cm 以上。"
        )
    return errors


def _measure_degradation(
    output_dir: Path,
    window: tuple[float, float],
) -> dict:
    """检测车道/刚性圆等结构性退化。"""
    import pyfii as pf

    fii_dir = _find_fii_dir(output_dir)
    data, _t0, *_ = _cached_read_fii(str(fii_dir))
    if not data:
        return {}

    fps = 60
    min_len = min(len(d) for d in data)
    start_s, end_s = window
    start_frame = max(1, int(start_s * fps))
    end_frame = min(min_len, int(end_s * fps) + 1)
    if end_frame <= start_frame:
        return {}

    drone_count = len(data)
    x_spans = []
    y_spans = []
    z_spans = []
    all_x = []
    all_y = []
    all_z = []
    for drone in data:
        xs = [float(drone[frame][1]) for frame in range(start_frame, end_frame)]
        ys = [float(drone[frame][2]) for frame in range(start_frame, end_frame)]
        zs = [float(drone[frame][3]) for frame in range(start_frame, end_frame)]
        x_spans.append(max(xs) - min(xs))
        y_spans.append(max(ys) - min(ys))
        z_spans.append(max(zs) - min(zs))
        all_x.extend(xs)
        all_y.extend(ys)
        all_z.extend(zs)

    sample_step = max(1, int(fps / 2))
    sample_frames = list(range(start_frame, end_frame, sample_step))
    circle_like = 0
    order_stable = 0
    flat_height = 0
    order_ref = None
    radius_medians = []
    centers = []

    for frame in sample_frames:
        positions = [
            (float(drone[frame][1]), float(drone[frame][2]))
            for drone in data
        ]
        z_values = [float(drone[frame][3]) for drone in data]
        if max(z_values) - min(z_values) < 20:
            flat_height += 1
        center = (
            sum(p[0] for p in positions) / drone_count,
            sum(p[1] for p in positions) / drone_count,
        )
        centers.append(center)
        radii = [math.hypot(p[0] - center[0], p[1] - center[1]) for p in positions]
        mean_radius = sum(radii) / max(1, drone_count)
        radius_medians.append(median(radii))
        if mean_radius > 1:
            variance = sum((r - mean_radius) ** 2 for r in radii) / max(1, drone_count)
            radial_cv = math.sqrt(variance) / mean_radius
        else:
            radial_cv = 999.0
        if mean_radius >= 70 and radial_cv <= 0.22:
            circle_like += 1

        order = tuple(
            index for index, _angle in sorted(
                (
                    (i, math.atan2(p[1] - center[1], p[0] - center[0]))
                    for i, p in enumerate(positions)
                ),
                key=lambda item: item[1],
            )
        )
        if order_ref is None:
            order_ref = order
            order_stable += 1
        elif _same_circular_order(order_ref, order):
            order_stable += 1

    center_path = 0.0
    for prev, current in zip(centers, centers[1:]):
        center_path += math.hypot(current[0] - prev[0], current[1] - prev[1])

    sample_count = max(1, len(sample_frames))
    return {
        "drone_count": drone_count,
        "window_xy_span": (
            round(max(all_x) - min(all_x), 1),
            round(max(all_y) - min(all_y), 1),
        ),
        "window_z_range_cm": round(max(all_z) - min(all_z), 1),
        "lane_x_locked_drones": sum(1 for span in x_spans if span < 35),
        "lane_y_locked_drones": sum(1 for span in y_spans if span < 35),
        "fixed_height_drones": sum(1 for span in z_spans if span < 18),
        "median_x_span_cm": round(median(x_spans), 1),
        "median_y_span_cm": round(median(y_spans), 1),
        "median_z_span_cm": round(median(z_spans), 1),
        "flat_height_fraction": round(flat_height / sample_count, 3),
        "circle_like_fraction": round(circle_like / sample_count, 3),
        "order_stable_fraction": round(order_stable / sample_count, 3),
        "median_radius_cm": round(median(radius_medians), 1) if radius_medians else 0.0,
        "radius_range_cm": round(max(radius_medians) - min(radius_medians), 1) if radius_medians else 0.0,
        "center_path_cm": round(center_path, 1),
    }


def _check_degradation(
    window: tuple[float, float],
    degradation: dict,
) -> list[str]:
    if not degradation:
        return ["无法计算结构性退化。"]

    start_s, end_s = window
    duration = max(0.1, end_s - start_s)
    drone_count = int(degradation.get("drone_count", 0))
    lane_limit = max(1, math.ceil(drone_count * 0.7))
    lane_x = int(degradation.get("lane_x_locked_drones", 0))
    lane_y = int(degradation.get("lane_y_locked_drones", 0))
    fixed_height = int(degradation.get("fixed_height_drones", 0))
    flat_height = float(degradation.get("flat_height_fraction", 0.0))
    z_range = float(degradation.get("window_z_range_cm", 0.0))
    circle_like = float(degradation.get("circle_like_fraction", 0.0))
    order_stable = float(degradation.get("order_stable_fraction", 0.0))

    errors = []
    if duration >= 6.0 and lane_x >= lane_limit:
        errors.append(
            f"车道退化：{lane_x}/{drone_count} 架无人机 X 方向变化小于 35cm，不能把安全退化成固定竖向车道。"
        )
    if duration >= 6.0 and lane_y >= lane_limit:
        errors.append(
            f"车道退化：{lane_y}/{drone_count} 架无人机 Y 方向变化小于 35cm，不能把安全退化成固定横向车道。"
        )
    if (
        duration >= 8.0
        and circle_like >= 0.75
        and order_stable >= 0.85
    ):
        errors.append(
            "刚性圆退化：大部分时间保持同一圆形排序；需要引入非圆几何、分组交换或明显叙事变化。"
        )
    if duration >= 5.0 and fixed_height >= lane_limit:
        errors.append(
            f"固定高度退化：{fixed_height}/{drone_count} 架无人机本段 Z 变化小于 18cm；需要真实 low/mid/high 高度层。"
        )
    if duration >= 5.0 and (z_range < 35.0 or flat_height >= 0.75):
        errors.append(
            f"高度层不足：全段 Z range={z_range:.1f}cm, flat_height_fraction={flat_height:.2f}；"
            "不能把编舞压在单一高度平面。"
        )
    return errors


def _same_circular_order(reference: tuple[int, ...], current: tuple[int, ...]) -> bool:
    if len(reference) != len(current):
        return False
    doubled = reference + reference
    return any(tuple(doubled[i:i + len(current)]) == current for i in range(len(reference)))


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


def _sample_exit_state(output_dir: Path, time_s: float | None = None) -> list[list[int]] | None:
    """从读回轨迹采样段尾位置，作为下一段 prev_state。"""
    import pyfii as pf

    try:
        fii_dir = _find_fii_dir(output_dir)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data, *_ = _cached_read_fii(str(fii_dir))
    except Exception:
        return None

    if not data:
        return None

    fps = 60
    sampled = []
    for drone in data:
        if not drone:
            continue
        if time_s is None:
            frame = len(drone) - 1
        else:
            frame = max(0, min(len(drone) - 1, int(round(time_s * fps))))
        row = drone[frame]
        sampled.append([
            int(round(float(row[1]))),
            int(round(float(row[2]))),
            int(round(float(row[3]))),
        ])

    return sampled or None


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



import functools

@functools.lru_cache(maxsize=1)
def _cached_read_fii(fii_dir_str: str):
    import pyfii as pf
    return pf.read_fii(fii_dir_str, fps=60, ignore_acc=True)

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


def _parse_action_warnings(output: str) -> list[str]:
    """解析 pyfii 动作未完成警告，提取简洁摘要"""
    import re
    details = []
    # 格式: In Xs,action isn't completed.在Xs秒动作未完成。
    pattern = re.compile(r'[Dd](\d+).*?[Ii]n\s*(\d+)s,action isn')
    for line in output.split('\n'):
        m = pattern.search(line)
        if m:
            details.append(f"d{m.group(1)} at {m.group(2)}s")
    return details
