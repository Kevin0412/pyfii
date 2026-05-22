from typing import Any, Dict, List, Optional, Sequence, Tuple
import math


def _num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if hasattr(value, "item"):
        value = value.item()
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _point_value(point: Any, index: int, default: float = 0.0) -> Any:
    try:
        return point[index]
    except (IndexError, TypeError):
        return default


def _position(point: Any) -> Tuple[float, float, float]:
    return (
        _num(_point_value(point, 1)),
        _num(_point_value(point, 2)),
        _num(_point_value(point, 3)),
    )


def _threshold_for_device(device: Optional[str]) -> float:
    normalized = (device or "").upper()
    if normalized == "F600":
        return 33.0
    return 51.0


def _field_range(field: Optional[int]) -> Optional[Tuple[float, float]]:
    if field == 6:
        return (0.0, 560.0)
    if field == 4:
        return (0.0, 360.0)
    return None


def analyze_safety(
    data: Any,
    warnings: Sequence[str],
    source_fps: int,
    field: Optional[int],
    device: Optional[str],
) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    last_event_at: Dict[Tuple[Any, ...], float] = {}
    min_distance: Optional[float] = None
    frame_interval_ms = 1000.0 / max(float(source_fps), 1.0)
    threshold = _threshold_for_device(device)
    field_range = _field_range(field)

    def add_event(
        *,
        time_ms: float,
        level: str,
        event_type: str,
        message: str,
        key: Tuple[Any, ...],
        drone_a: Optional[int] = None,
        drone_b: Optional[int] = None,
        distance_cm: Optional[float] = None,
        threshold_cm: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        last = last_event_at.get(key)
        if last is not None and time_ms - last < 1000.0:
            return
        last_event_at[key] = time_ms
        events.append(
            {
                "id": "evt_%06d" % (len(events) + 1),
                "time_ms": round(time_ms, 3),
                "frame": int(round(time_ms / frame_interval_ms)),
                "level": level,
                "type": event_type,
                "drone_a": drone_a,
                "drone_b": drone_b,
                "distance_cm": None if distance_cm is None else round(distance_cm, 3),
                "threshold_cm": threshold_cm,
                "message": message,
                "details": details or {},
            }
        )

    for index, warning in enumerate(warnings or []):
        add_event(
            time_ms=0.0,
            level="warning",
            event_type="core_warning",
            message=str(warning),
            key=("core_warning", index),
        )

    tracks = [list(track or []) for track in data or []]
    max_frames = max((len(track) for track in tracks), default=0)

    for frame_index in range(max_frames):
        frame_time = frame_index * frame_interval_ms
        positions: List[Tuple[int, float, float, float]] = []

        for drone_index, track in enumerate(tracks, start=1):
            if not track:
                continue
            point = track[min(frame_index, len(track) - 1)]
            frame_time = max(frame_time, _num(_point_value(point, 0), frame_time))
            x, y, z = _position(point)
            positions.append((drone_index, x, y, z))

            if z < 0:
                add_event(
                    time_ms=frame_time,
                    level="error",
                    event_type="negative_height",
                    message="%.2fs: 无人机 %d 高度 %.1fcm 低于 0cm" % (frame_time / 1000.0, drone_index, z),
                    key=("negative_height", drone_index),
                    drone_a=drone_index,
                    details={"z_cm": round(z, 3)},
                )

            if field_range is not None:
                lower, upper = field_range
                if x < lower or x > upper or y < lower or y > upper:
                    add_event(
                        time_ms=frame_time,
                        level="warning",
                        event_type="field_range",
                        message=(
                            "%.2fs: 无人机 %d 坐标 (%.1f, %.1f) 超出 %dm 场地推荐范围 %.0f..%.0fcm"
                            % (frame_time / 1000.0, drone_index, x, y, field or 0, lower, upper)
                        ),
                        key=("field_range", drone_index),
                        drone_a=drone_index,
                        details={"x_cm": round(x, 3), "y_cm": round(y, 3), "range_cm": [lower, upper]},
                    )

        for left_index in range(len(positions)):
            for right_index in range(left_index + 1, len(positions)):
                drone_a, x_a, y_a, _z_a = positions[left_index]
                drone_b, x_b, y_b, _z_b = positions[right_index]
                distance = math.hypot(x_a - x_b, y_a - y_b)
                min_distance = distance if min_distance is None else min(min_distance, distance)
                if distance < threshold:
                    add_event(
                        time_ms=frame_time,
                        level="error",
                        event_type="min_distance",
                        message=(
                            "%.2fs: 无人机 %d 和 %d 水平距离 %.1fcm，低于 %s 安全阈值 %.0fcm"
                            % (frame_time / 1000.0, drone_a, drone_b, distance, device or "默认", threshold)
                        ),
                        key=("min_distance", min(drone_a, drone_b), max(drone_a, drone_b)),
                        drone_a=drone_a,
                        drone_b=drone_b,
                        distance_cm=distance,
                        threshold_cm=threshold,
                    )

    error_count = sum(1 for event in events if event["level"] == "error")
    warning_count = sum(1 for event in events if event["level"] == "warning")
    level = "error" if error_count else "warning" if warning_count else "ok"

    return {
        "summary": {
            "level": level,
            "error_count": error_count,
            "warning_count": warning_count,
            "min_distance_cm": None if min_distance is None else round(min_distance, 3),
        },
        "events": events,
    }
