"""human_preferences 缓存失效（Phase 0a）：run_pipeline.py 的人工评审分支记录新偏好后，
同一进程内后续 segment 必须能看到它——不能像 patch 前那样只写盘、缓存却继续吃旧值。

main.py 的 `g`/`o` 命令一直有做 `session._human_preferences = None`；run_pipeline.py 的
"验证通过但导演要改" 分支（review_segments + director_script）此前没有对应的失效。
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_pipeline  # noqa: E402
from core import Session  # noqa: E402
from core.validator import ValidationResult  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "project_template"
MARKER_TEXT = "偏好标记_9f3a_只用纯色不要渐变"


def _passing_round():
    validation = ValidationResult(
        compile_ok=True, run_ok=True, read_fii_ok=True,
        distance_warnings=0, action_warnings=0,
        dense_min_distance_cm=63.0, expected_drone_count=7,
    )
    validation.exit_state = [[100 + 60 * i, 100, 150] for i in range(7)]
    round_item = MagicMock()
    round_item.index = 1
    round_item.response = MagicMock(model="mock")
    round_item.validation = validation
    round_item.code = "prev = [(d.x, d.y, d.z) for d in drones]\n"
    return [round_item]


def test_scripted_review_feedback_invalidates_preferences_cache():
    tmp = Path(tempfile.mkdtemp(prefix="human_pref_cache_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    seen_preferences: list[str] = []

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        # 每次生成前先读一次 human_preferences，观察缓存是否已经失效刷新
        seen_preferences.append(self.human_preferences)
        return _passing_round()

    director_script = {"segments": {"S01": {"feedback": [MARKER_TEXT]}}}

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=2,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
                review_segments=True,
                director_script=director_script,
            )
        assert len(seen_preferences) >= 2, f"expected S01 to regenerate at least once, got {seen_preferences}"
        # 第 1 次生成时偏好还没记录；记录+continue 之后，S01 重做那一轮必须已经看到新偏好
        assert MARKER_TEXT not in seen_preferences[0]
        assert any(MARKER_TEXT in p for p in seen_preferences[1:]), (
            "human_preferences cache was not invalidated after the scripted-review "
            "feedback branch recorded a new preference — later generation calls in "
            "the same run are still reading the stale cached value"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: scripted-review feedback invalidates human_preferences cache")


if __name__ == "__main__":
    test_scripted_review_feedback_invalidates_preferences_cache()
    print("\nALL HUMAN PREFERENCES CACHE TESTS PASSED")
