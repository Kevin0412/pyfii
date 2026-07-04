"""黑洞熔断（P6）：连续同类失败 cycle 触发方案重置，而不是继续灌同类反馈。"""

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


def _colliding_round():
    validation = ValidationResult(
        compile_ok=True, run_ok=True, read_fii_ok=True,
        distance_warnings=0, action_warnings=0,
        dense_min_distance_cm=42.0, expected_drone_count=7,
    )
    validation.exit_state = [[100 + 60 * i, 120, 150] for i in range(7)]
    round_item = MagicMock()
    round_item.index = 1
    round_item.response = MagicMock(model="mock")
    round_item.validation = validation
    round_item.code = "mock code"
    return [round_item]


def test_repeated_same_category_triggers_scheme_reset():
    tmp = Path(tempfile.mkdtemp(prefix="reset_test_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    feedbacks: list[str] = []

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        feedbacks.append(feedback)
        return _colliding_round()

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            result = run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=3,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
            )
        summary = result["summary"]
        seg_record = summary["records"][0]
        assert seg_record["scheme_resets"] >= 1, seg_record
        assert any("方案重置" in fb and "作废" in fb for fb in feedbacks), (
            "重置反馈没有进入下一 cycle 的 feedback"
        )
        # 重置块替换累积反馈（从段基础反馈重建），不是无限叠加
        reset_fb = next(fb for fb in feedbacks if "方案重置" in fb)
        assert "继续修复 validator 反馈" not in reset_fb
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: repeated same-category failure triggers scheme reset")


if __name__ == "__main__":
    test_repeated_same_category_triggers_scheme_reset()
    print("\nALL SCHEME RESET TESTS PASSED")
