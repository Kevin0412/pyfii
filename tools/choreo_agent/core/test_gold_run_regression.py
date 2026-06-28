"""Gold-run regression: gates must accept the best run we have.

`agent_projects/codex_9drone_flash_full_20260605_1` is the reference 9-drone
run (hand-written round-number geo tables + best_assign/far_assign +
per-drone loops, S01-S06+LAND locked). Any structural gate that rejects its
segments is miscalibrated. The design-card requirement is exempt here: the
gold run predates that protocol, and adding 5 comment lines does not change
its choreography.
"""

import re
import textwrap
from pathlib import Path

from core.composition import extract_code_features
from core.preflight import preflight_check

GOLD_DESIGN = (
    Path(__file__).resolve().parents[1]
    / "agent_projects"
    / "codex_9drone_flash_full_20260605_1"
    / "scripts"
    / "design.py"
)

_MARKER = re.compile(
    r"# === PYFII_AGENT_SEGMENT_START id=(\w+) locked=\w+ ===\n(.*?)# === PYFII_AGENT_SEGMENT_END \1 ===",
    re.DOTALL,
)


def _gold_segments() -> dict[str, str]:
    text = GOLD_DESIGN.read_text(encoding="utf-8")
    segments = {
        seg_id: textwrap.dedent(body)
        for seg_id, body in _MARKER.findall(text)
    }
    assert set(segments) == {"S01", "S02", "S03", "S04", "S05", "S06", "LAND"}, (
        f"gold run markers changed: {sorted(segments)}"
    )
    return segments


def test_gold_segments_pass_preflight():
    for seg_id, body in _gold_segments().items():
        result = preflight_check(body, segment_id=seg_id)
        assert result.passed, f"{seg_id} rejected by preflight: {result.errors}"


def test_gold_segments_are_not_template_or_group_only():
    for seg_id, body in _gold_segments().items():
        if seg_id == "LAND":
            continue
        features = extract_code_features(body)
        assert features["geo_template_call_count"] == 0, (
            f"{seg_id}: gold run never used geo_* templates"
        )
        assert not features["uses_group_only_execution"], (
            f"{seg_id}: gold run uses per-drone loops, gate must not class it as group-only"
        )


def test_gold_s04_s06_keyframe_counts_meet_gates():
    segments = _gold_segments()
    s04 = extract_code_features(segments["S04"])
    assert s04["estimated_keyframe_count"] >= 4, (
        f"S04 gate would reject gold run: estimated {s04['estimated_keyframe_count']} keyframes"
    )
    s06 = extract_code_features(segments["S06"])
    assert s06["estimated_keyframe_count"] >= 2, (
        f"S06 gate would reject gold run: estimated {s06['estimated_keyframe_count']} keyframes"
    )


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL GOLD RUN REGRESSION TESTS PASSED")
