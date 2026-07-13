from typing import Any, Dict, List, Optional, Sequence, Tuple
import re


_DISTANCE_RE = re.compile(
    r"In\s+(?P<seconds>\d+(?:\.\d+)?)s,\s*distance between d(?P<a>\d+) and d(?P<b>\d+) is less than (?P<threshold>\d+(?:\.\d+)?)cm",
    re.IGNORECASE,
)
_ACTION_INCOMPLETE_RE = re.compile(r"In\s+(?P<seconds>\d+(?:\.\d+)?)s,\s*action isn't completed", re.IGNORECASE)
_DRONE_PREFIX_RE = re.compile(r"^d(?P<drone>\d+)\s+无人机(?P=drone):")

CATEGORY_META = {
    "core_warning": {"label": "核心警告", "rank": 5},
    "action_incomplete": {"label": "动作未完成", "rank": 10},
    "distance_51": {"label": "距离过近", "rank": 20},
    "distance_34": {"label": "碰撞风险", "rank": 30},
    "distance_17": {"label": "碰撞警告", "rank": 40},
}


def _warning_time_ms(message: str) -> float:
    for pattern in (_DISTANCE_RE, _ACTION_INCOMPLETE_RE):
        match = pattern.search(message)
        if match:
            return float(match.group("seconds")) * 1000.0
    return 0.0


def _drone_from_prefix(message: str) -> Optional[int]:
    match = _DRONE_PREFIX_RE.search(message)
    if not match:
        return None
    return int(match.group("drone"))


def _event_category(category: str) -> Dict[str, Any]:
    meta = CATEGORY_META[category]
    return {
        "category": category,
        "category_label": meta["label"],
        "category_rank": meta["rank"],
    }


def _distance_category(threshold_cm: float) -> str:
    if threshold_cm <= 17:
        return "distance_17"
    if threshold_cm <= 34:
        return "distance_34"
    return "distance_51"


def _classify_core_warning(message: str) -> Dict[str, Any]:
    distance = _DISTANCE_RE.search(message)
    if distance:
        threshold_cm = float(distance.group("threshold"))
        category = _distance_category(threshold_cm)
        return {
            "level": "error",
            "type": "min_distance",
            "time_ms": float(distance.group("seconds")) * 1000.0,
            "drone_a": int(distance.group("a")),
            "drone_b": int(distance.group("b")),
            "distance_cm": None,
            "threshold_cm": threshold_cm,
            **_event_category(category),
            "dedupe_key": ("min_distance", int(distance.group("a")), int(distance.group("b"))),
        }

    action_incomplete = _ACTION_INCOMPLETE_RE.search(message)
    if action_incomplete:
        drone = _drone_from_prefix(message)
        return {
            "level": "warning",
            "type": "action_incomplete",
            "time_ms": float(action_incomplete.group("seconds")) * 1000.0,
            "drone_a": drone,
            "drone_b": None,
            "distance_cm": None,
            "threshold_cm": None,
            **_event_category("action_incomplete"),
            "dedupe_key": ("action_incomplete", drone),
        }

    drone = _drone_from_prefix(message)
    return {
        "level": "warning",
        "type": "core_warning",
        "time_ms": _warning_time_ms(message),
        "drone_a": drone,
        "drone_b": None,
        "distance_cm": None,
        "threshold_cm": None,
        **_event_category("core_warning"),
        "dedupe_key": ("core_warning", drone, message),
    }


def analyze_safety(
    data: Any,
    warnings: Sequence[str],
    source_fps: int,
    field: Optional[int],
    device: Optional[str],
) -> Dict[str, Any]:
    del data, field, device

    events: List[Dict[str, Any]] = []
    last_event_at: Dict[Tuple[Any, ...], float] = {}
    frame_interval_ms = 1000.0 / max(float(source_fps), 1.0)

    for message in warnings or []:
        classified = _classify_core_warning(str(message))
        time_ms = classified["time_ms"]
        dedupe_key = classified["dedupe_key"]
        last = last_event_at.get(dedupe_key)
        if last is not None and time_ms - last < 1000.0:
            continue
        last_event_at[dedupe_key] = time_ms

        events.append(
            {
                "id": "evt_%06d" % (len(events) + 1),
                "time_ms": round(time_ms, 3),
                "frame": int(round(time_ms / frame_interval_ms)),
                "level": classified["level"],
                "type": classified["type"],
                "drone_a": classified["drone_a"],
                "drone_b": classified["drone_b"],
                "distance_cm": classified["distance_cm"],
                "threshold_cm": classified["threshold_cm"],
                "category": classified["category"],
                "category_label": classified["category_label"],
                "category_rank": classified["category_rank"],
                "message": str(message),
                "details": {
                    "source": "pyfii_core_warning",
                    "distance_boundaries_cm": [51, 34, 17]
                    if classified["type"] == "min_distance"
                    else None,
                },
            }
        )

    error_count = sum(1 for event in events if event["level"] == "error")
    warning_count = sum(1 for event in events if event["level"] == "warning")
    category_counts = {
        category: sum(1 for event in events if event["category"] == category)
        for category in CATEGORY_META
    }
    max_category = None
    if events:
        max_category = max(events, key=lambda event: event["category_rank"])["category"]
    level = "error" if error_count else "warning" if warning_count else "ok"

    return {
        "summary": {
            "level": level,
            "error_count": error_count,
            "warning_count": warning_count,
            "min_distance_cm": None,
            "category_counts": category_counts,
            "max_category": max_category,
        },
        "events": events,
    }
