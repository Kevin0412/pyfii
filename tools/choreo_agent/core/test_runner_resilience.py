"""Runner resilience tests — no real API calls."""

import sys, json, tempfile, shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_pipeline import run_full_flow, _failure_category_from_exception, _failure_category_from_validation
from core.script_editor import lock_segment
from core.session import (
    _compact_validation_feedback,
    _targeted_validation_repair_feedback,
    _validation_snapshot,
)
from core.validator import ValidationResult


def _fresh_project() -> Path:
    tmp = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent.parent))
    tmpl = Path(__file__).resolve().parent.parent / "project_template"
    shutil.copytree(tmpl, tmp, dirs_exist_ok=True)
    return tmp


def _fake_round(passed=True, min_d=200):
    """Build a fake GenerationRound that looks like a passed validation."""
    v = MagicMock()
    v.passed = passed
    v.min_distance_cm = min_d
    v.distance_warnings = 0
    v.action_warnings = 0
    v.dense_min_distance_cm = min_d
    v.collision_intervals = []
    v.code_quality_ok = True
    v.compile_ok = True
    v.run_ok = True
    v.read_fii_ok = True
    v.motion_envelope_ok = True
    v.effective_motion_ok = True
    v.motion_quality_ok = True
    v.degradation_ok = True
    v.hover_check_ok = True
    v.hover_segments = []
    v.motion_envelope_errors = []
    v.effective_motion_errors = []
    v.motion_quality_errors = []
    v.degradation_errors = []
    v.code_quality_errors = []
    v.error_message = ""
    v.exit_state = [[100, 100, 150]] * 7
    v.continuity_required = False
    v.compute_assign_feedback = MagicMock(return_value="")
    v.repair_feedback = MagicMock(return_value="")
    v.quality_window = (4, 13)
    v.motion_start_s = None
    v.motion_end_s = None
    v.effective_motion_start_s = None
    v.effective_motion_end_s = None
    r = MagicMock()
    r.index = 1
    r.response = MagicMock()
    r.response.model = "mock"
    r.response.text = "mock code"
    r.response.reasoning_text = ""
    r.response.input_tokens = 10
    r.response.output_tokens = 20
    r.validation = v
    return r


def test_api_exception_writes_partial_result():
    """API exception → stability_result.json written, completed=false."""
    proj = _fresh_project()
    try:
        def fail_after_cycle_start(self, *args, **kwargs):
            result_path = proj / "stability_result.json"
            assert result_path.exists(), "partial result should exist before API call"
            json.loads(result_path.read_text())
            raise RuntimeError("mock timeout")

        with patch('core.session.Session.generate_until_safe_with_llm', fail_after_cycle_start):
            result = run_full_flow(proj, provider="mock", max_cycles_per_segment=1,
                                   max_attempts_per_cycle=1, use_planning_pass=False,
                                   retry_sleep_s=0, max_api_exceptions_per_segment=1)

        assert not result["summary"]["completed"]
        assert result["summary"]["locked_segment_ids"] == []
        result_path = proj / "stability_result.json"
        assert result_path.exists(), "partial result not written"
        data = json.loads(result_path.read_text())
        assert not data["summary"]["completed"]
        assert data["summary"]["run"]["status"] == "failed"
        assert data["summary"]["attempt_counts"]["exceptions"] >= 1
        assert "validation_rounds" in data["summary"]["attempt_counts"]
        assert data["summary"]["convergence"]["round_limit_per_segment"] == 5
        state = json.loads((proj / "state.json").read_text())
        assert state["last_run"]["provider"] == "mock"
        assert state["last_run"]["status"] == "failed"
        records = data["summary"]["records"]
        assert len(records) >= 1
        seg = records[0]
        assert seg["failure_category"] in ("api_network", "exception"), f"bad category: {seg['failure_category']}"
        print("PASSED: api_exception_writes_partial_result")
    finally:
        shutil.rmtree(proj)


def test_exception_then_pass_continues():
    """First cycle exception, second passes → runner continues and locks."""
    proj = _fresh_project()
    try:
        call_count = [0]
        def mock_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("mock timeout")
            return [_fake_round(passed=True, min_d=200)]

        def mock_approve(self, allow_human_override=False):
            script_path = self.project_root / "scripts" / "design.py"
            for seg in self.state.segments:
                lock_segment(script_path, seg.id)
                seg.locked = True
                seg.exit_state = [[100, 100, 150]] * 7
            self.state.locked_segment_ids = [seg.id for seg in self.state.segments]
            self.state.current_segment_index = len(self.state.segments)
            self.state.save(self.project_root)
            return MagicMock(locked=True, reason="", validation=_fake_round().validation)

        with patch('core.session.Session.generate_until_safe_with_llm', mock_generate):
            # Also mock approve_and_lock to return success
            with patch('core.session.Session.approve_and_lock', mock_approve):
                result = run_full_flow(proj, provider="mock", max_cycles_per_segment=2,
                                       max_attempts_per_cycle=1, use_planning_pass=False,
                                       retry_sleep_s=0, max_api_exceptions_per_segment=5)

        assert call_count[0] == 2, f"expected 2 calls, got {call_count[0]}"
        assert result["summary"]["completed"], f"should complete: {result['summary']}"
        assert result["summary"]["attempt_counts"]["validation_rounds"] == 1
        assert result["summary"]["convergence"]["converged"]
        state = json.loads((proj / "state.json").read_text())
        assert state["last_run"]["status"] == "completed"
        assert state["last_run"]["convergence"]["converged"]
        print("PASSED: exception_then_pass_continues")
    finally:
        shutil.rmtree(proj)


def test_failure_category_from_exception():
    """_failure_category_from_exception recognizes API errors."""
    for exc, expected in [
        (RuntimeError("mock"), "exception"),
        (TimeoutError("connect timeout"), "api_network"),
        (ConnectionError("SSL handshake failed"), "api_network"),
        (OSError("peer closed connection"), "api_network"),
        (Exception("RemoteProtocolError"), "api_network"),
    ]:
        assert _failure_category_from_exception(exc) == expected, f"{type(exc).__name__} → {expected}"
    print("PASSED: failure_category_from_exception")


def test_failure_category_from_window_fill():
    v = _fake_round(passed=False).validation
    v.window_fill_ok = False
    v.window_fill_errors = ["段尾时间 15.5s 早于窗口尾 19.8s"]

    assert _failure_category_from_validation(v) == "window_fill"
    print("PASSED: failure_category_from_window_fill")


def test_window_fill_feedback_is_visible_to_llm_and_state():
    v = ValidationResult()
    v.window_fill_ok = False
    v.window_fill_errors = ["段未填满窗口：S03 内容止于 30.2s，窗口到 35.0s"]

    feedback = _compact_validation_feedback(v)
    assert "window:" in feedback
    assert "段未填满窗口" in feedback

    snapshot = _validation_snapshot(v)
    assert snapshot["window_fill_ok"] is False
    assert snapshot["window_fill_errors"] == v.window_fill_errors


def test_near_pass_quality_feedback_is_surgical():
    v = ValidationResult()
    v.compile_ok = True
    v.run_ok = True
    v.read_fii_ok = True
    v.distance_warnings = 0
    v.action_warnings = 0
    v.collision_intervals = []
    v.dense_min_distance_cm = 93.8
    v.motion_quality_errors = [
        "中位路径长度过短：76.4cm；当前 5.2s 段至少需要 80.0cm"
    ]
    v.motion_quality = {
        "median_path_cm": 76.4,
        "max_excursion_cm": 120.3,
        "moving_drones": 7,
    }

    feedback = _targeted_validation_repair_feedback(v)
    assert "不要重写整段" in feedback
    assert "外推 15-30cm" in feedback
    assert "relay" in feedback


def test_effective_motion_feedback_prefers_real_move():
    v = ValidationResult()
    v.compile_ok = True
    v.run_ok = True
    v.read_fii_ok = True
    v.distance_warnings = 0
    v.action_warnings = 0
    v.collision_intervals = []
    v.dense_min_distance_cm = 54.0
    v.effective_motion_errors = [
        "有效群体运动持续时间过短：1.28s；至少需要 2.5s。"
    ]

    feedback = _targeted_validation_repair_feedback(v)
    assert "3000-3400ms" in feedback
    assert "灯光不算有效群体运动" in feedback
    assert "不要重写整段" in feedback


def test_no_bad_patterns():
    """Runner has no force lock/fallback/static segments."""
    code = Path(__file__).resolve().parent.parent / "run_pipeline.py"
    text = code.read_text()
    assert "allow_human_override=True" not in text, "allow_human_override=True"
    assert "SEGMENTS_TO_PROCESS" not in text, "SEGMENTS_TO_PROCESS"
    assert "force_advance" not in text, "force_advance"
    print("PASSED: no_bad_patterns")


if __name__ == "__main__":
    test_api_exception_writes_partial_result()
    test_exception_then_pass_continues()
    test_failure_category_from_exception()
    test_failure_category_from_window_fill()
    test_window_fill_feedback_is_visible_to_llm_and_state()
    test_near_pass_quality_feedback_is_surgical()
    test_effective_motion_feedback_prefers_real_move()
    test_no_bad_patterns()
    print("\nALL RUNNER RESILIENCE TESTS PASSED")
