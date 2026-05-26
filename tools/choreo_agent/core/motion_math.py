"""Agent-side motion timing helpers.

These helpers are for prompt construction, diagnostics, and tests. Generated
choreography code should normally write concrete VelXY/VelZ/delay values rather
than defining these helper functions inside a segment.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


MIN_SPEED_CM_S = 20
MAX_SPEED_CM_S = 200
MIN_ACCEL_CM_S2 = 50
MAX_ACCEL_CM_S2 = 400


@dataclass(frozen=True)
class MotionBudget:
    distance_cm: float
    desired_s: float
    speed_cm_s: int
    accel_cm_s2: int
    flight_ms: int
    light_ticks: int
    delay_ms: int

    @property
    def command_budget_ms(self) -> int:
        return self.light_ticks * 100 + self.delay_ms


def clamp_speed(value: float) -> int:
    return max(MIN_SPEED_CM_S, min(MAX_SPEED_CM_S, int(round(value))))


def clamp_accel(value: float) -> int:
    return max(MIN_ACCEL_CM_S2, min(MAX_ACCEL_CM_S2, int(round(value))))


def dist3(p0: tuple[float, float, float], p1: tuple[float, float, float]) -> float:
    return math.sqrt(
        (p1[0] - p0[0]) ** 2
        + (p1[1] - p0[1]) ** 2
        + (p1[2] - p0[2]) ** 2
    )


def flight_time_s(distance_cm: float, speed_cm_s: float, accel_cm_s2: float) -> float:
    """Estimate PyFii movement duration with trapezoid/triangle speed curves."""
    if distance_cm <= 0:
        return 0.0
    speed = max(1e-6, float(speed_cm_s))
    accel = max(1e-6, float(accel_cm_s2))
    accel_dist = speed * speed / (2 * accel)
    if distance_cm >= 2 * accel_dist:
        return 2 * speed / accel + (distance_cm - 2 * accel_dist) / speed
    return 2 * math.sqrt(distance_cm / accel)


def flight_time_ms(distance_cm: float, speed_cm_s: float, accel_cm_s2: float) -> int:
    return int(math.ceil(flight_time_s(distance_cm, speed_cm_s, accel_cm_s2) * 1000))


def accel_for_feel(speed_cm_s: float, feel: str = "balanced") -> int:
    """Return a suggested acceleration; callers may override it freely."""
    profiles = {
        "soft": 1.25,
        "balanced": 1.8,
        "crisp": 2.4,
        "snap": 3.0,
    }
    factor = profiles.get(str(feel).strip().lower(), profiles["balanced"])
    return clamp_accel(speed_cm_s * factor)


def speed_for_interval(
    distance_cm: float,
    desired_s: float,
    *,
    accel_cm_s2: int | None = None,
    feel: str = "balanced",
    reserve_s: float = 0.12,
) -> int:
    """Pick a speed whose flight time fits the interval without finishing early.

    If accel_cm_s2 is omitted, a feel-based acceleration suggestion is used only
    as a default. The acceleration is not a fixed function of speed.
    """
    if distance_cm <= 1:
        return 45

    usable_s = max(0.35, float(desired_s) - reserve_s)
    low = MIN_SPEED_CM_S
    high = MAX_SPEED_CM_S
    chosen = high

    for _ in range(16):
        mid = (low + high) / 2
        accel = accel_cm_s2 if accel_cm_s2 is not None else accel_for_feel(mid, feel)
        if flight_time_s(distance_cm, mid, accel) <= usable_s:
            chosen = mid
            high = mid
        else:
            low = mid

    return clamp_speed(chosen)


def motion_budget(
    distance_cm: float,
    desired_s: float,
    *,
    accel_cm_s2: int | None = None,
    feel: str = "balanced",
    light_ticks: int = 3,
    settle_ms: int = 120,
) -> MotionBudget:
    speed = speed_for_interval(
        distance_cm,
        desired_s,
        accel_cm_s2=accel_cm_s2,
        feel=feel,
    )
    accel = clamp_accel(accel_cm_s2) if accel_cm_s2 is not None else accel_for_feel(speed, feel)
    flight_ms = flight_time_ms(distance_cm, speed, accel)
    delay_ms = max(settle_ms, flight_ms - light_ticks * 100 + settle_ms)
    return MotionBudget(
        distance_cm=float(distance_cm),
        desired_s=float(desired_s),
        speed_cm_s=speed,
        accel_cm_s2=accel,
        flight_ms=flight_ms,
        light_ticks=light_ticks,
        delay_ms=delay_ms,
    )


def prompt_budget_table() -> str:
    """Build a compact motion-math reference for the system prompt."""
    cases = [
        (80, 1.8, "soft"),
        (140, 2.2, "balanced"),
        (220, 2.8, "balanced"),
        (340, 3.4, "crisp"),
    ]
    rows = []
    for distance, desired_s, feel in cases:
        budget = motion_budget(distance, desired_s, feel=feel)
        rows.append(
            f"| {distance}cm | {desired_s:.1f}s | {feel} | "
            f"{budget.speed_cm_s} | {budget.accel_cm_s2} | "
            f"{budget.flight_ms} | {budget.delay_ms} |"
        )

    return "\n".join(
        [
            "# Agent-side Motion Math Tool",
            "",
            "这是 agent 内部运动学工具摘要，不是要写进 design.py 的 helper 代码。生成段代码时先用这里的梯形/三角速度模型估算，再把结果落实为具体 `VelXY(v, a)` / `VelZ(v, a)` / `delay(ms)` 数值；同一 keyframe 最好成对设置 `VelXY` 和 `VelZ`。",
            "",
            "- 距离用 3D distance；短距离是三角速度曲线，长距离才有匀速段。",
            "- acceleration 是独立编舞参数；`a = 2v` 只能当经验候选，不能当硬规则。",
            "- 如果想更柔，降低 acceleration；如果想更利落，提高 acceleration；最终仍必须在 50-400 cm/s^2 内。",
            "- 段代码里不要定义 `dist3` / `flight_time_ms` / `speed_for_interval` / `move_interval`。它们属于 agent 侧估算工具。",
            "",
            "| distance | interval | feel | speed | accel | flight_ms | delay_ms after 3 light ticks |",
            "|---:|---:|---|---:|---:|---:|---:|",
            *rows,
        ]
    )
