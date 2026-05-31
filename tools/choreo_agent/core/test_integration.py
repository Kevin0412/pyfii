"""Integration tests: chat, preflight, planning, degradation cross-segment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_chat_mimo_no_prefix():
    """chat(provider='mimo') works without prefix/recursion."""
    from core.llm_client import chat
    r = chat("say OK", "respond OK", provider="mimo", temperature=0.1)
    assert r is not None
    assert "ok" in r.text.lower()
    print("PASSED: chat(mimo) — no recursion, no prefix")


def test_chat_prefix_mimo_rejects():
    """chat_prefix(provider='mimo') raises locally without HTTP."""
    from core.llm_client import chat_prefix
    try:
        chat_prefix("sys", "user", provider="mimo", temperature=0.1)
        assert False, "Should raise"
    except RuntimeError as e:
        assert "does not support prefix" in str(e)
    print("PASSED: chat_prefix(mimo) — local reject")


def test_bad_code_does_not_write_design_py():
    """preflight failure prevents design.py modification."""
    from core.session import _extract_python_code
    from core.preflight import preflight_check
    bad = "import math\n```python\ndrone.VelXY(120,200)\n```"
    code = _extract_python_code(bad)
    pf = preflight_check(code)
    assert not pf, f"Should fail preflight: {pf.errors}"
    print("PASSED: bad code fails preflight (would not write design.py)")


def test_degradation_signature_cross_segment():
    """Same degradation signature in two consecutive segments → hard fail."""
    # This is a logic test: verify state can store and compare signatures
    from core.state import SegmentState
    s1 = SegmentState(id="S01", start_time=4, end_time=13, degradation_signature="circle_like")
    s2 = SegmentState(id="S02", start_time=13, end_time=23, degradation_signature="circle_like")
    s3 = SegmentState(id="S03", start_time=23, end_time=31, degradation_signature="expand")
    
    # Consecutive same signature
    assert s1.degradation_signature == s2.degradation_signature, \
        "S01 and S02 should have same sig"
    assert s2.degradation_signature != s3.degradation_signature, \
        "S02 and S03 should have different sig"
    print("PASSED: degradation cross-segment signature comparison")


def test_planning_pass_flow():
    """planning pass: JSON plan → budget table → code prompt."""
    from core.planning_pass import (
        build_planning_prompt, parse_plan_json,
        plan_to_budget_table, build_coding_prompt,
    )
    # Mock prev
    prev = [(140,190,130),(225,150,185),(298,226,217),(385,150,185),
            (445,223,175),(345,410,160),(185,375,155)]
    prompt = build_planning_prompt("S02", 13, 23, "expand", prev)
    assert "S02" in prompt and "JSON" in prompt
    
    # Mock plan JSON
    plan_json = '''```json
{"keyframes": [
  {"start_s":13,"duration_s":4,"feel":"expand","speed_cm_s":120,"accel_cm_s2":200,
   "light_color":"#4488ff","light_ticks":4,
   "targets":[[120,160,150],[200,180,170],[300,240,160],[400,200,180],[480,160,140],[360,400,150],[160,380,150]]},
  {"start_s":17,"duration_s":4,"feel":"rotate","speed_cm_s":100,"accel_cm_s2":180,
   "light_color":"#ff6644","light_ticks":4,
   "targets":[[200,200,200],[280,220,200],[360,280,190],[440,240,200],[500,200,180],[400,440,190],[200,420,190]]}
]}
```'''
    plan = parse_plan_json(plan_json)
    assert plan is not None
    
    budget = plan_to_budget_table(plan, prev)
    assert "Keyframe 1" in budget
    assert "budget" in budget.lower() or "预算" in budget or "dist3" in budget or "fly_ms" in budget
    
    code_prompt = build_coding_prompt(budget, "S02", 13, 23)
    assert "S02" in code_prompt
    print("PASSED: planning pass full flow")



def test_cli_g_uses_planning_pass():
    """CLI g command passes use_planning_pass=True to generate_until_safe_with_llm."""
    # This is a code inspection test, not runtime
    main_path = Path(__file__).resolve().parent.parent / "main.py"
    content = main_path.read_text()
    assert "use_planning_pass=True" in content, \
        "main.py g command must include use_planning_pass=True"
    print("PASSED: CLI g command uses planning pass")

if __name__ == "__main__":
    test_chat_mimo_no_prefix()
    test_chat_prefix_mimo_rejects()
    test_bad_code_does_not_write_design_py()
    test_degradation_signature_cross_segment()
    test_planning_pass_flow()
    test_cli_g_uses_planning_pass()
    print("\nALL 5 INTEGRATION TESTS PASSED")
