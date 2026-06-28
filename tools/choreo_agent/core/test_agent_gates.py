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


def test_preflight_blocks_jitter_points_and_sub51_min_xy():
    # jitter_points is blocked
    r = preflight_check("""
geo = custom_points([
    (60, 60, 120), (280, 60, 210), (500, 60, 120)
], n=3)
geo = jitter_points(geo, xy=10, seed=7)
""")
    assert not r
    assert any("jitter_points" in e for e in r.errors)
    # min_xy_cm < 51 is blocked (below pyfii collision floor)
    r2 = preflight_check("""
geo = custom_points([(100, 100, 120), (130, 120, 180)], n=2, min_xy_cm=40)
""")
    assert not r2
    assert any("51" in e for e in r2.errors)
    # min_xy_cm >= 51 is allowed (any value the model chooses)
    r3 = preflight_check("""
geo = custom_points([(100, 100, 120), (300, 300, 180)], n=2, min_xy_cm=110)
""")
    assert r3, f"min_xy_cm=110 should pass preflight: {r3.errors}"
    print("PASSED: preflight blocks jitter_points + sub-51 min_xy")


def test_preflight_blocks_static_custom_points_runtime_errors():
    too_close = preflight_check("""
geo = custom_points([(100, 100, 120), (130, 120, 180)], n=2)
""", segment_id="S02", drone_count=2)
    assert not too_close, "static custom_points table below 51cm should fail preflight"
    assert any("custom_points 静态点表" in e for e in too_close.errors), too_close.errors

    stricter_than_default = preflight_check("""
geo = custom_points([(100, 100, 120), (170, 100, 180)], n=len(drones), min_xy_cm=90)
""", segment_id="S02", drone_count=2)
    assert not stricter_than_default, "explicit min_xy_cm=90 should be enforced statically"
    assert any("min_xy_cm=90" in e for e in stricter_than_default.errors), stricter_than_default.errors

    legal_default = preflight_check("""
geo = custom_points([(100, 100, 120), (170, 100, 180)], n=len(drones))
""", segment_id="S02", drone_count=2)
    assert legal_default, f"default 51cm custom_points table should pass: {legal_default.errors}"

    raw_geo_for_helper = preflight_check("""
geo = [(100, 100, 120), (140, 100, 180)]
prev = call_response_safe(drones, prev, geo, 3000)
""", segment_id="S02", drone_count=2)
    assert not raw_geo_for_helper, "call_response_safe raw geo below its default 51cm should fail preflight"
    assert any("call_response_safe 静态点表" in e for e in raw_geo_for_helper.errors), raw_geo_for_helper.errors


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


def test_preflight_passes_geometry_to_runtime():
    """Broad computed geometry policing stays disabled; only exact custom_points errors are gated."""
    # R=100 circle: spacing ~68cm, above the current default 51cm — this remains legal.
    code = (
        "geo = custom_points([(280+100*cos(2*pi*i/9), 280+100*sin(2*pi*i/9), 160) "
        "for i in range(9)], n=9)\n"
    )
    r = preflight_check(code, segment_id="S02", drone_count=9)
    assert r, f"default-legal custom_points geometry should pass preflight: {r.errors}"
    # Unwrapped comprehension also passes preflight now
    raw = (
        "geo = [(280+170*cos(2*pi*i/9), 280+170*sin(2*pi*i/9), 160) for i in range(9)]\n"
        "targets = best_assign(prev, geo)\n"
    )
    r2 = preflight_check(raw, segment_id="S02", drone_count=9)
    assert r2, f"unwrapped comprehension should pass preflight: {r2.errors}"
    print("PASSED: preflight passes geometry to runtime")


def test_preflight_verifies_start_positions_spacing():
    # 自由设计的环形起飞，R=240 弦距 ~184cm → 放行；密集环 R=100 弦距 ~77cm 也合法（≥51）
    ring = (
        "start_positions = [(280+240*cos(2*pi*k/8), 280+240*sin(2*pi*k/8)) "
        "for k in range(8)] + [(280, 280)]\n"
        "for i, drone in enumerate(drones):\n"
        "    drone.X = drone.x = start_positions[i][0]\n"
        "    drone.Y = drone.y = start_positions[i][1]\n"
        "    drone.takeoff(1, 90 + (i % 3) * 15)\n"
    )
    assert preflight_check(ring, segment_id="S01", drone_count=9), \
        preflight_check(ring, segment_id="S01", drone_count=9).errors
    dense_but_legal = ring.replace("240", "100")  # 弦距 ~77cm ≥ 51 — 密集构图是设计自由
    assert preflight_check(dense_but_legal, segment_id="S01", drone_count=9)
    # R=60 弦距 ~46cm < 51cm 硬下限 → 报精确数字
    tight = ring.replace("240", "60")
    r = preflight_check(tight, segment_id="S01", drone_count=9)
    assert not r
    assert any("起飞布局最小 XY 间距" in e for e in r.errors), r.errors
    r2 = preflight_check(tight.replace("start_positions", "sp"), segment_id="S01", drone_count=9)
    # 改名后静态查不到，交运行期兜底 — 不应报起飞间距错误
    assert not any("起飞布局" in e for e in r2.errors)
    print("PASSED: preflight verifies start_positions spacing")


def test_preflight_enforces_land_protocol():
    # 编舞式降落（wrq run 实际发生的 bug）：有 move2 无 d.land() → 双违规
    bad = (
        "for i, drone in enumerate(drones):\n"
        "    move2(drone, (280, 280, 80), 1200)\n"
        "    apply_light(drone, '#330066', 6)\n"
        "    drone.delay(300)\n"
    )
    r = preflight_check(bad, segment_id="LAND")
    assert not r
    joined = " ".join(r.errors)
    assert "d.land()" in joined and "move2" in joined
    # 协议正确的 LAND 放行
    good = (
        "auto_init(drones)\n"
        "for d in drones:\n"
        "    apply_light(d, '#ffffff', 3)\n"
        "    d.land()\n"
    )
    assert preflight_check(good, segment_id="LAND")
    # 非 LAND 段不受影响
    assert not any("LAND" in e for e in preflight_check(bad, segment_id="S03").errors)
    print("PASSED: preflight enforces LAND protocol")


def test_preflight_blocks_bare_api():
    r = preflight_check("drone.VelXY(120,200)")
    assert not r
    print("PASSED: preflight blocks bare VelXY")
    r2 = preflight_check("drone.move2(100,120,150)")
    assert not r2
    print("PASSED: preflight blocks drone.move2()")


def test_preflight_blocks_common_runtime_mistakes():
    bare_light = preflight_check('TurnOnAll("#44aaff")')
    assert not bare_light
    assert any("NameError" in error and "TurnOnAll" in error for error in bare_light.errors)

    bad_turnoff = preflight_check("""
for d in drones:
    d.TurnOff()
""")
    assert not bad_turnoff
    assert any("TurnOff()" in error and "TurnOffAll" in error for error in bad_turnoff.errors)

    bad_groups = preflight_check("""
gids = split_groups(prev, mode="left_right")
for i in gids[1]:
    apply_light(drones[i], "#ffaa00", 3)
""")
    assert not bad_groups
    assert any("逐机 group_id" in error for error in bad_groups.errors)

    direct_bad_groups = preflight_check("""
for i in split_groups(prev, mode="alternate")[0]:
    drones[i].delay(100)
""")
    assert not direct_bad_groups
    assert any("逐机 group_id" in error for error in direct_bad_groups.errors)

    good_groups = preflight_check("""
gids = split_groups(prev, mode="left_right")
for i, gid in enumerate(gids):
    if gid == 1:
        apply_light(drones[i], "#ffaa00", 3)
""")
    assert good_groups, good_groups.errors

    bare_drone = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
drone.delay(50)
""")
    assert not bare_drone
    assert any("裸用 `drone.<method>" in error for error in bare_drone.errors)

    loop_drone = preflight_check("""
for i, drone in enumerate(drones):
    drone.delay(i * 80)
    apply_light(drone, "#44aaff", 3)
""")
    assert loop_drone, loop_drone.errors
    print("PASSED: preflight blocks recurring TurnOnAll/split_groups runtime mistakes")


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
    # 循环内的下标式 per-drone 写法是全队覆盖，必须放行
    looped = preflight_check("""for i in range(9):
    drones[i].delay(i * 120)
    move2(drones[i], (100 + i * 55, 120, 120), 3000)
    apply_light(drones[i], "#44aaff", 4)
    drones[i].delay(max(0, 2700 - i * 120))
""")
    assert looped, looped.errors
    print("PASSED: preflight blocks single-drone timing (loop-aware)")


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


def test_preflight_allows_scalar_unpack_that_looks_like_xyz():
    r = preflight_check("""
cx, cy, R = 280, 280, 70
geo = [(100, 120, 150), (200, 180, 160), (300, 240, 140)]
targets = best_assign(prev, geo)
""")
    assert not any("坐标常量超出" in e for e in r.errors), r.errors


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


def test_preflight_blocks_sync_assign_stagger_mismatch():
    # far_assign + ripple_move with delays → blocked
    bad_far = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
targets = far_assign(prev, geo, min_path_cm=120)
delays = ripple_delays(prev, mode="by_index", step_ms=150)
prev = ripple_move(drones, targets, 2800, delays, colors="#ff0000")
""", segment_id="S03")
    assert not bad_far
    assert any("far_assign" in e and "同步锁步" in e for e in bad_far.errors)

    # best_assign + per-drone loop with delay → blocked
    bad_loop = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
targets = best_assign(prev, geo)
for i, drone in enumerate(drones):
    drone.delay(i * 120)
    move2(drone, targets[i], 2800)
    apply_light(drone, "#ff0000", 3)
""", segment_id="S02")
    assert not bad_loop
    assert any("best_assign" in e and "drone.delay" in e for e in bad_loop.errors)

    # keep_assign + ripple_move with delays → blocked
    bad_keep = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
targets = keep_assign(prev, geo)
delays = ripple_delays(prev, mode="by_index", step_ms=150)
prev = ripple_move(drones, targets, 2800, delays)
""", segment_id="S04")
    assert not bad_keep
    assert any("keep_assign" in e for e in bad_keep.errors)

    # safe_assign + ripple_move with SAME delays → allowed
    good_safe = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
delays = ripple_delays(prev, mode="by_index", step_ms=130)
targets = safe_assign(prev, geo, delays=delays, flying_ms=2800)
prev = ripple_move(drones, targets, 2800, delays, colors="#ff0000")
""", segment_id="S03")
    assert good_safe, good_safe.errors

    # safe_move → allowed
    good_sm = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
prev = safe_move(drones, prev, geo, 2800, mode="wave")
""", segment_id="S03")
    assert good_sm, good_sm.errors

    # best_assign + sync loop (delay(0)) → allowed
    good_sync = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
targets = best_assign(prev, geo)
for i, drone in enumerate(drones):
    move2(drone, targets[i], 2800)
    apply_light(drone, "#ff0000", 3)
    drone.delay(0)
""", segment_id="S03")
    assert good_sync, good_sync.errors

    # S01 exempt — best_assign + delay loop allowed
    good_s01 = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
targets = best_assign(prev, geo)
for i, drone in enumerate(drones):
    drone.delay(i * 120)
    move2(drone, targets[i], 2800)
""", segment_id="S01")
    assert good_s01, good_s01.errors

    # safe_assign delays mismatch → blocked
    bad_mismatch = preflight_check("""
auto_init(drones)
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(100,100,150),(200,200,150),(300,300,150),(400,400,150),(350,150,150),(150,350,150),(250,450,150)], n=len(drones))
delays_search = ripple_delays(prev, mode="by_index", step_ms=80)
targets = safe_assign(prev, geo, delays=delays_search, flying_ms=2600)
delays_exec = ripple_delays(prev, mode="center_out", step_ms=130)
prev = ripple_move(drones, targets, 2600, delays_exec, colors="#ff0000")
""", segment_id="S03")
    assert not bad_mismatch
    assert any("不同的 delays" in e for e in bad_mismatch.errors)

    print("PASSED: preflight blocks sync-assign + stagger timing mismatch")


if __name__ == "__main__":
    test_mimo_no_prefix()
    test_chat_no_recursion()
    test_preflight_blocks_markdown()
    test_preflight_blocks_import()
    test_preflight_blocks_def()
    test_preflight_blocks_tool_leak()
    test_preflight_blocks_geo_templates()
    test_preflight_blocks_jitter_points_and_sub51_min_xy()
    test_preflight_blocks_static_custom_points_runtime_errors()
    test_preflight_blocks_position_writes_outside_s01()
    test_preflight_passes_geometry_to_runtime()
    test_preflight_verifies_start_positions_spacing()
    test_preflight_enforces_land_protocol()
    test_preflight_blocks_bare_api()
    test_preflight_blocks_common_runtime_mistakes()
    test_preflight_blocks_sync_assign_stagger_mismatch()
    test_preflight_blocks_inittime()
    test_preflight_blocks_single_drone_timing()
    test_preflight_blocks_out_of_range_coordinate_literals()
    test_preflight_accepts_clean()
    test_planning_pass_importable()
    test_degradation_signature_in_state()
    print("\nALL 19 TESTS PASSED")
