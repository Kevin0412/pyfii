"""黑洞熔断（P6）：连续同类失败 cycle 触发方案重置；Phase 5 起 auto-compact 会话过长
也是另一个独立的重置触发条件（默认关闭，需要显式传 max_conversation_chars）。"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run_pipeline  # noqa: E402
from core import Session  # noqa: E402
from core import conversation  # noqa: E402
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


def test_conversation_size_cap_triggers_scheme_reset_independent_of_category():
    """auto-compact（默认关闭）：显式设置 max_conversation_chars 后，会话长度本身
    成为触发重置的另一个理由——即便每个 cycle 的失败类别都不一样（category_repeat
    从不触发），纯粹因为超限也要清空重置，且要记进 scheme_reset_reasons['size_cap']
    而不是 ['category_repeat']。"""
    tmp = Path(tempfile.mkdtemp(prefix="reset_size_cap_test_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    call_count = {"n": 0}
    # 每个 cycle 用不同的验证失败字段，category 逐 cycle 不同，排除 category_repeat 干扰
    category_triggers = [
        {"action_warnings": 1},  # action_incomplete
        {"distance_warnings": 1},  # collision
        {"motion_envelope_errors": ["stalled"]},  # hover_or_low_activity
    ]

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        seg = self.state.current_segment
        i = call_count["n"]
        call_count["n"] += 1
        validation = ValidationResult(
            compile_ok=True, run_ok=True, read_fii_ok=True,
            distance_warnings=0, action_warnings=0,
            dense_min_distance_cm=63.0, expected_drone_count=7,
        )
        for key, value in category_triggers[min(i, len(category_triggers) - 1)].items():
            setattr(validation, key, value)
        validation.exit_state = [[100 + 60 * j, 120, 150] for j in range(7)]
        # 每轮真实追加一大段内容，模拟会话持续增长
        conversation.append_user(seg.conversation, "x" * 80, stage="direct_generation")
        conversation.append_assistant(seg.conversation, "y" * 80, stage="direct_generation")
        round_item = MagicMock()
        round_item.index = 1
        round_item.response = MagicMock(model="mock")
        round_item.validation = validation
        round_item.code = "mock code"
        return [round_item]

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            result = run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=3,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
                max_conversation_chars=150,  # 2 轮（320 字符）后就超限
            )
        summary = result["summary"]
        seg_record = summary["records"][0]
        assert seg_record["scheme_resets"] >= 1, seg_record
        assert seg_record["scheme_reset_reasons"]["size_cap"] >= 1, seg_record
        assert seg_record["scheme_reset_reasons"]["category_repeat"] == 0, (
            "this scenario deliberately varies category every cycle -- only size_cap "
            "should have fired"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: conversation size cap triggers scheme reset independent of category")


def test_size_cap_disabled_by_default():
    """max_conversation_chars 不传时（默认 None）不应该因为会话长度触发重置——
    该功能默认关闭，只有类别连续重复才会重置。"""
    tmp = Path(tempfile.mkdtemp(prefix="reset_size_cap_off_test_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    call_count = {"n": 0}
    category_triggers = [
        {"action_warnings": 1},
        {"distance_warnings": 1},
        {"motion_envelope_errors": ["stalled"]},
    ]

    def fake_generate(self, provider=None, feedback="", **_kwargs):
        seg = self.state.current_segment
        i = call_count["n"]
        call_count["n"] += 1
        validation = ValidationResult(
            compile_ok=True, run_ok=True, read_fii_ok=True,
            distance_warnings=0, action_warnings=0,
            dense_min_distance_cm=63.0, expected_drone_count=7,
        )
        for key, value in category_triggers[min(i, len(category_triggers) - 1)].items():
            setattr(validation, key, value)
        validation.exit_state = [[100 + 60 * j, 120, 150] for j in range(7)]
        conversation.append_user(seg.conversation, "x" * 80, stage="direct_generation")
        conversation.append_assistant(seg.conversation, "y" * 80, stage="direct_generation")
        round_item = MagicMock()
        round_item.index = 1
        round_item.response = MagicMock(model="mock")
        round_item.validation = validation
        round_item.code = "mock code"
        return [round_item]

    try:
        with patch.object(Session, "generate_until_safe_with_llm", fake_generate):
            result = run_pipeline.run_full_flow(
                project_root=project,
                provider="mock",
                max_cycles_per_segment=3,
                max_attempts_per_cycle=1,
                retry_sleep_s=0,
                # max_conversation_chars 不传，默认 None
            )
        seg_record = result["summary"]["records"][0]
        assert seg_record["scheme_resets"] == 0, seg_record
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASSED: size cap stays off by default")


if __name__ == "__main__":
    test_repeated_same_category_triggers_scheme_reset()
    test_conversation_size_cap_triggers_scheme_reset_independent_of_category()
    test_size_cap_disabled_by_default()
    print("\nALL SCHEME RESET TESTS PASSED")
