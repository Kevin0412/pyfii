from typing import Any, Dict, List, Optional, Sequence, Tuple
import math


def _to_builtin_number(value: Any, default: float = 0.0) -> float:
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


def _json_number(value: Any, default: float = 0.0) -> Any:
    number = _to_builtin_number(value, default)
    rounded = round(number)
    if abs(number - rounded) < 1e-9:
        return int(rounded)
    return number


def _point_value(point: Any, index: int, default: float = 0.0) -> Any:
    try:
        return point[index]
    except (IndexError, TypeError):
        return default


def _as_triplet(value: Any) -> Tuple[float, float, float]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 3:
        return (
            _to_builtin_number(value[0]),
            _to_builtin_number(value[1]),
            _to_builtin_number(value[2]),
        )
    return (0.0, 0.0, 0.0)


def bgr_to_rgb(led: Any) -> Tuple[int, int, int]:
    if not isinstance(led, Sequence) or isinstance(led, (str, bytes)) or len(led) < 3:
        return (-1, -1, -1)

    b = int(_to_builtin_number(led[0], -1))
    g = int(_to_builtin_number(led[1], -1))
    r = int(_to_builtin_number(led[2], -1))
    if b < 0 and g < 0 and r < 0:
        return (-1, -1, -1)
    return (r, g, b)


def _serialize_point(point: Any) -> List[Any]:
    led_r, led_g, led_b = bgr_to_rgb(_point_value(point, 5, (-1, -1, -1)))
    acc_x, acc_y, acc_z = _as_triplet(_point_value(point, 6, (0, 0, 0)))
    return [
        _json_number(_point_value(point, 0)),
        _json_number(_point_value(point, 1)),
        _json_number(_point_value(point, 2)),
        _json_number(_point_value(point, 3)),
        _json_number(_point_value(point, 4)),
        led_r,
        led_g,
        led_b,
        _json_number(acc_x),
        _json_number(acc_y),
        _json_number(acc_z),
    ]


def compute_duration_ms(data: Any) -> float:
    duration = 0.0
    for track in data or []:
        if not track:
            continue
        for point in track:
            duration = max(duration, _to_builtin_number(_point_value(point, 0)))
    return duration


def compute_frame_count(data: Any) -> int:
    return max((len(track) for track in data or [] if track is not None), default=0)


def _music_files(music: Any) -> List[str]:
    if not music:
        return []
    if isinstance(music, Sequence) and not isinstance(music, (str, bytes)):
        return [str(item) for item in list(music)[1:] if str(item)]
    return [str(music)]


def serialize_project_meta(
    project_id: str,
    name: str,
    data: Any,
    music: Any,
    field: Optional[int],
    device: Optional[str],
    source_fps: int,
    duration_ms: float,
    frame_count: int,
    safety_summary: Dict[str, Any],
) -> Dict[str, Any]:
    files = _music_files(music)
    return {
        "project_id": project_id,
        "name": name,
        "field": field,
        "device": device,
        "drone_count": len(data or []),
        "duration_ms": _json_number(duration_ms),
        "source_fps": int(source_fps),
        "frame_count": int(frame_count),
        "music": {
            "available": len(files) > 0,
            "files": files,
        },
        "safety_summary": safety_summary,
    }


def serialize_tracks(
    data: Any,
    project_id: str,
    fps: int,
    source_fps: int,
    duration_ms: float,
    field: Optional[int],
    device: Optional[str],
) -> Dict[str, Any]:
    interval_ms = 1000.0 / float(fps)
    drones = []

    for drone_index, track in enumerate(data or [], start=1):
        samples = []
        next_time = 0.0
        track_list = list(track or [])
        for point_index, point in enumerate(track_list):
            time_ms = _to_builtin_number(_point_value(point, 0))
            should_emit = point_index == 0 or time_ms + 1e-6 >= next_time or point_index == len(track_list) - 1
            if not should_emit:
                continue

            sample = _serialize_point(point)
            if not samples or samples[-1][0] != sample[0]:
                samples.append(sample)
            while next_time <= time_ms + 1e-6:
                next_time += interval_ms

        drones.append({"id": drone_index, "samples": samples})

    return {
        "project_id": project_id,
        "fps": int(fps),
        "duration_ms": _json_number(duration_ms),
        "field": field,
        "device": device,
        "drones": drones,
    }
