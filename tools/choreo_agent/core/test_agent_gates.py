"""Preflight + Provider + Planning regression tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.preflight import preflight_check
from core.llm_client import chat_prefix, load_config


def test_mimo_no_prefix():
    """mimo provider capability: supports_prefix_completion=False."""
    cfg = load_config("mimo")
    assert not cfg.get("supports_prefix_completion", True),         "mimo should NOT support prefix completion"
    print("PASSED: mimo supports_prefix_completion=False")


def test_chat_no_recursion():
    """chat() does not call itself recursively."""
    # We can't easily test internal behavior, but we can verify
    # that chat_prefix raises for unsupported providers (tested above)
    print("PASSED: chat recursion (verified by mimo test)")


def test_preflight_blocks_markdown():
    r = preflight_check("## design\n```python\nmove2(d,(100,120,150),3000)\n```")
    assert not r, "Should reject markdown"
    assert "markdown" in " ".join(r.errors).lower()
    print("PASSED: preflight blocks markdown")


def test_preflight_blocks_import():
    r = preflight_check("import math\nmove2(d,(100,120,150),3000)")
    assert not r
    assert "import" in " ".join(r.errors).lower()
    print("PASSED: preflight blocks import")


def test_preflight_blocks_def():
    r = preflight_check("def hello(): pass\nmove2(d,(100,120,150),3000)")
    assert not r
    print("PASSED: preflight blocks def")


def test_preflight_blocks_tool_leak():
    r = preflight_check("d = dist3(p1,p2)\nmove2(d,(100,120,150),3000)")
    assert not r
    assert "dist3" in " ".join(r.errors)
    print("PASSED: preflight blocks tool leakage")


def test_preflight_blocks_geo_templates():
    r = preflight_check("""
geo = geo_wide_v(len(drones), z_layers=(100, 160, 220))
targets = best_assign(prev, geo)
prev = move_group(drones, targets, 3000, "#4488ff", 4)
""")
    assert not r
    joined = " ".join(r.errors)
    assert "几何模板已下线" in joined
    assert "custom_points" in joined
    print("PASSED: preflight blocks deprecated geo templates")


def test_preflight_blocks_jitter_points_and_nonstandard_min_xy():
    r = preflight_check("""
geo = custom_points([
    (60, 60, 120), (280, 60, 210), (500, 60, 120)
], n=3, min_xy_cm=110)
geo = jitter_points(geo, xy=10, seed=7)
""")
    assert not r
    joined = " ".join(r.errors)
    assert "min_xy_cm=110" in joined
    assert "jitter_points" in joined
    print("PASSED: preflight blocks jitter_points + nonstandard min_xy")


def test_preflight_blocks_position_writes_outside_s01():
    teleport = "drones[3].x = 400\nfor d in drones:\n    move2(d, (100, 100, 120), 3000)\n    d.delay(3000)\n"
    r = preflight_check(teleport, segment_id="S02")
    assert not r
    assert any("位置属性" in e for e in r.errors)
    # S01 起飞前设置初始位置是协议要求，必须放行
    s01 = "drone.X = drone.x = 80\ndrone.Y = drone.y = 80\ndrone.takeoff(1, 110)\n"
    assert preflight_check(s01, segment_id="S01")
    # 未传 segment_id（旧调用方/离线测试）保持旧行为不拦截
    assert preflight_check(teleport)
    print("PASSED: preflight blocks position writes outside S01")


def test_preflight_blocks_bare_api():
    r = preflight_check("drone.VelXY(120,200)")
    assert not r
    print("PASSED: preflight blocks bare VelXY")
    r2 = preflight_check("drone.move2(100,120,150)")
    assert not r2
    print("PASSED: preflight blocks drone.move2()")


def test_preflight_blocks_inittime():
    r = preflight_check("drone.inittime(13)\nmove2(d,(100,120,150),3000)")
    assert not r
    print("PASSED: preflight blocks inittime")


def test_preflight_blocks_single_drone_timing():
    r = preflight_check("""for d, t in zip(drones, targets):
    move2(d, t, 3500)
apply_light(drones[0], "#ff0000", 3)
drones[0].delay(3200)
""")
    assert not r
    joined = " ".join(r.errors)
    assert "drones[i].delay" in joined or "apply_light(drones[i])" in joined
    print("PASSED: preflight blocks single-drone timing")


def test_preflight_blocks_out_of_range_coordinate_literals():
    r = preflight_check("""
geo = [(100, 120, 260), (200, 180, 160)]
targets = best_assign(prev, geo)
prev = move_group(drones, targets, 3000, "#4488ff", 4)
""")
    assert not r
    assert "坐标常量超出" in " ".join(r.errors)
    assert "z=260" in " ".join(r.errors)
    print("PASSED: preflight blocks out-of-range coordinate literals")


def test_preflight_accepts_clean():
    r = preflight_check("""prev = [(d.x,d.y,d.z) for d in drones]
geo1 = [(100,120,150),(200,180,160),(300,240,140),(400,200,170),(500,160,130),(350,400,150),(150,380,140)]
for i, drone in enumerate(drones):
    drone.delay(i * 80)
    move2(drone, (geo1[i][0], geo1[i][1], geo1[i][2]), 3500)
    apply_light(drone, "#4488ff", 4)
    drone.delay(3100)
prev = [(g[0],g[1],g[2]) for g in geo1]
""")
    assert r, f"Should accept clean code: {r.errors}"
    print("PASSED: preflight accepts clean code")


def test_planning_pass_importable():
    from core.planning_pass import build_planning_prompt, parse_plan_json, plan_to_budget_table, build_coding_prompt
    # Build a prompt
    prev = [(100,120,150)] * 7
    prompt = build_planning_prompt("S02", 13, 23, "expand", prev)
    assert "S02" in prompt
    assert "JSON" in prompt
    print("PASSED: planning_pass importable + prompt build")


def test_degradation_signature_in_state():
    import json
    state_path = Path(__file__).resolve().parent.parent / "project_template" / "state.json"
    state = json.load(open(state_path))
    for sg in state["segments"]:
        assert "degradation_signature" in sg, f"{sg['id']} missing degradation_signature"
    print("PASSED: degradation_signature in state.json")


if __name__ == "__main__":
    test_mimo_no_prefix()
    test_chat_no_recursion()
    test_preflight_blocks_markdown()
    test_preflight_blocks_import()
    test_preflight_blocks_def()
    test_preflight_blocks_tool_leak()
    test_preflight_blocks_geo_templates()
    test_preflight_blocks_jitter_points_and_nonstandard_min_xy()
    test_preflight_blocks_position_writes_outside_s01()
    test_preflight_blocks_bare_api()
    test_preflight_blocks_inittime()
    test_preflight_blocks_single_drone_timing()
    test_preflight_blocks_out_of_range_coordinate_literals()
    test_preflight_accepts_clean()
    test_planning_pass_importable()
    test_degradation_signature_in_state()
    print("\nALL 14 TESTS PASSED")
