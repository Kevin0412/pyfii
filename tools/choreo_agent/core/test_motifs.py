"""动作/灯光母题库测试：波次计算器、母题执行器、灯光母题、门适配、preflight 适配。"""

import importlib.util
from pathlib import Path

from core.composition import evaluate_composition, extract_code_features
from core.preflight import preflight_check


def _load_fn():
    path = Path(__file__).resolve().parent.parent / "project_template" / "scripts" / "function.py"
    spec = importlib.util.spec_from_file_location("template_function_motifs", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeDrone:
    def __init__(self, x=0, y=0, z=120, t=0):
        self.x, self.y, self.z = x, y, z
        self.time = t
        self.lights = []  # (time_ms, color)
        self.offs = []    # time_ms
        self.moves = []   # (time_ms, x, y, z)

    def VelXY(self, _v, _a):
        pass

    def VelZ(self, _v, _a):
        pass

    def move2(self, x, y, z):
        self.moves.append((self.time, x, y, z))
        self.x, self.y, self.z = x, y, z

    def delay(self, ms):
        self.time += ms

    def TurnOnAll(self, color):
        self.lights.append((self.time, color))

    def TurnOffAll(self):
        self.offs.append(self.time)


# ---------- 波次/分组计算器 ----------

def test_spatial_ranks_modes():
    fn = _load_fn()
    # 十字队形：中心 + 四个等距臂
    cross = [(280, 280, 150), (380, 280, 150), (180, 280, 150), (280, 380, 150), (280, 180, 150)]
    ranks = fn.spatial_ranks(cross, mode="center_out")
    assert ranks[0] == 0, "中心机必须是第一波"
    assert ranks[1] == ranks[2] == ranks[3] == ranks[4] == 1, "等距臂应合并为同一波"
    edge_in = fn.spatial_ranks(cross, mode="center_out", reverse=True)
    assert edge_in[0] == 1 and edge_in[1] == 0, "reverse 即 edge_in"

    line = [(100, 280, 150), (250, 280, 150), (400, 280, 150)]
    assert fn.spatial_ranks(line, mode="sweep_x") == [0, 1, 2]
    assert fn.spatial_ranks(line, mode="sweep_x", reverse=True) == [2, 1, 0]
    assert fn.spatial_ranks(line, mode="by_index") == [0, 1, 2]

    ring = [(380, 280, 150), (280, 380, 150), (180, 280, 150), (280, 180, 150)]
    spiral = fn.spatial_ranks(ring, mode="spiral")
    assert sorted(spiral) == [0, 1, 2, 3], "spiral 每机一个波次"

    try:
        fn.spatial_ranks(line, mode="nope")
    except ValueError as exc:
        assert "center_out" in str(exc)
    else:
        raise AssertionError("非法 mode 应当抛错")


def test_ripple_delays_steps():
    fn = _load_fn()
    line = [(100, 280, 150), (250, 280, 150), (400, 280, 150)]
    assert fn.ripple_delays(line, mode="sweep_x", step_ms=150) == [0, 150, 300]


def test_split_groups_modes():
    fn = _load_fn()
    line = [(100 + 50 * i, 280, 150) for i in range(9)]
    gid = fn.split_groups(line, mode="left_right")
    assert gid[:5] == [0] * 5 and gid[5:] == [1] * 4, "左 5 右 4"
    ring = [(380, 280, 150), (280, 380, 150), (180, 280, 150), (280, 180, 150)]
    alt = fn.split_groups(ring, mode="alternate")
    assert sorted(alt) == [0, 0, 1, 1]
    cross = [(280, 280, 150), (480, 280, 150), (80, 280, 150), (280, 480, 150)]
    inner = fn.split_groups(cross, mode="inner_outer")
    assert inner[0] == 0, "质心附近的机在 inner 组"
    try:
        fn.split_groups(line, mode="nope")
    except ValueError:
        pass
    else:
        raise AssertionError("非法 mode 应当抛错")


# ---------- 母题执行器 ----------

def test_ripple_move_aligns_and_lights_in_wave_order():
    fn = _load_fn()
    drones = [FakeDrone(100, 280), FakeDrone(250, 280), FakeDrone(400, 280)]
    targets = [(150, 200, 140), (250, 120, 160), (350, 200, 180)]
    prev = fn.ripple_move(drones, targets, 1000, [0, 200, 400], colors="#ff8800", hold_ticks=4)

    assert prev == [tuple(map(int, t)) for t in targets]
    assert [d.time for d in drones] == [1400, 1400, 1400], "段尾必须对齐 span+fly"
    assert [d.moves[0][0] for d in drones] == [0, 200, 400], "波次启动时刻"
    assert [d.lights[0][0] for d in drones] == [0, 200, 400], "先动的先亮"


def test_light_wave_alignment():
    fn = _load_fn()
    drones = [FakeDrone(), FakeDrone(), FakeDrone()]
    consumed = fn.light_wave(drones, [0, 150, 300], ["#ff0000", "#00ff00", "#0000ff"], hold_ticks=5)
    assert consumed == 300 + 500
    assert [d.time for d in drones] == [800, 800, 800]
    assert [d.lights[0][0] for d in drones] == [0, 150, 300], "光波按 delays 扫过"
    assert drones[1].lights[0][1] == "#00ff00"


def test_group_relay_two_phase_alignment():
    fn = _load_fn()
    drones = [FakeDrone(100, 100), FakeDrone(200, 100), FakeDrone(300, 100), FakeDrone(400, 100)]
    targets = [(100, 300, 140), (200, 300, 150), (300, 300, 160), (400, 300, 170)]
    prev = fn.group_relay(drones, targets, [0, 1, 0, 1], 1000, colors=("#aa0000", "#0000aa"), gap_ms=200)

    assert prev == targets
    assert [d.time for d in drones] == [2200] * 4, "总时长 2*fly+gap 全员对齐"
    assert drones[0].moves[0][0] == 0 and drones[2].moves[0][0] == 0, "0 组先动"
    assert drones[1].moves[0][0] == 1200 and drones[3].moves[0][0] == 1200, "1 组等 fly+gap 再动"
    assert drones[1].lights[0][0] == 0, "1 组等待期间亮灯应答"
    assert drones[1].lights[0][1] == "#0000aa" and drones[0].lights[0][1] == "#aa0000", "组色对话"


def test_group_relay_accepts_gids_keyword_alias():
    fn = _load_fn()
    drones = [FakeDrone(100, 100), FakeDrone(200, 100), FakeDrone(300, 100), FakeDrone(400, 100)]
    targets = [(100, 300, 140), (200, 300, 150), (300, 300, 160), (400, 300, 170)]

    prev = fn.group_relay(drones, targets, gids=[0, 1, 0, 1], flying_ms=900)

    assert prev == targets
    assert [d.time for d in drones] == [2000] * 4


def test_call_response_safe_wraps_safe_relay_alignment():
    fn = _load_fn()
    drones = [
        FakeDrone(60, 120, 140),
        FakeDrone(500, 120, 150),
        FakeDrone(60, 440, 160),
        FakeDrone(500, 440, 170),
    ]
    prev = [(d.x, d.y, d.z) for d in drones]
    geo = fn.custom_points(
        [(120, 120, 150), (440, 120, 180), (120, 440, 160), (440, 440, 200)],
        n=len(drones),
        min_xy_cm=90,
    )

    out = fn.call_response_safe(
        drones, prev, geo, 1000, gap_ms=200,
        relay_split="left_right", colors=("#aa0000", "#0000aa"),
    )

    assert sorted(tuple(p[:2]) for p in out) == sorted(tuple(g[:2]) for g in geo)
    assert [d.time for d in drones] == [2200] * 4, "总时长 2*fly+gap 全员对齐"
    delays = [0 if g == 0 else 1200 for g in fn.split_groups(prev, mode="left_right")]
    ok, min_cm, _pair = fn.verify_timed_clearance(prev, out, delays=delays, flying_ms=1000)
    assert ok and min_cm >= 51, f"call_response_safe flew an unverified relay: {min_cm}cm"


def test_follow_chain_alignment_order_and_ends():
    fn = _load_fn()
    drones = [FakeDrone(300, 280), FakeDrone(100, 280), FakeDrone(200, 280)]
    wps = [(80, 280, 150), (180, 280, 160), (280, 280, 170), (380, 280, 160), (480, 280, 150)]
    ends = fn.follow_chain(drones, wps, 600, lag_hops=1, colors=["#ffffff", "#8888ff", "#4444aa"])

    assert [d.time for d in drones] == [3000] * 3, "总时长 = len(waypoints)*hop_ms 全员对齐"
    # 进链顺序按离 wps[0] 远近：drone1(x=100) 头机，drone2(x=200) 次，drone0(x=300) 尾
    assert drones[1].moves[0][0] == 0
    assert drones[2].moves[0][0] == 600
    assert drones[0].moves[0][0] == 1200
    # 结束位置：头机停在末端，依次回退 lag
    assert ends[1] == (480, 280, 150)
    assert ends[2] == (380, 280, 160)
    assert ends[0] == (280, 280, 170)
    assert drones[1].lights[0][1] == "#ffffff", "头机用 colors[0]"


def test_follow_chain_rejects_bad_paths():
    fn = _load_fn()
    drones = [FakeDrone(), FakeDrone(), FakeDrone()]
    try:
        fn.follow_chain(drones, [(100, 100, 120), (200, 100, 120), (300, 100, 120), (400, 100, 120)], 600, lag_hops=2)
    except ValueError as exc:
        assert "至少 5 个波点" in str(exc)
    else:
        raise AssertionError("波点不足应当抛错")

    tight = [(100 + 40 * k, 100, 120) for k in range(5)]
    try:
        fn.follow_chain(drones, tight, 600, lag_hops=1)
    except ValueError as exc:
        assert "链上间距不足" in str(exc) and "40.0cm" in str(exc)
    else:
        raise AssertionError("链上间距不足应当抛错")


def test_chain_follow_safe_expands_control_points_and_aligns():
    fn = _load_fn()
    drones = [
        FakeDrone(520, 520),
        FakeDrone(470, 500),
        FakeDrone(420, 480),
        FakeDrone(370, 460),
        FakeDrone(320, 440),
        FakeDrone(270, 420),
        FakeDrone(220, 400),
        FakeDrone(170, 380),
        FakeDrone(120, 360),
    ]
    ctrl = [(40, 520, 180), (280, 300, 160), (540, 40, 190)]

    ends = fn.chain_follow_safe(drones, ctrl, hop_ms=580, lag_hops=1, spacing_cm=65, colors="#66ccff")

    assert [d.time for d in drones] == [5800] * 9, "默认 10 个波点，9 机总耗时 10*hop_ms"
    assert len(ends) == 9
    assert all(len(d.moves) >= 1 for d in drones)
    assert all(d.lights and d.lights[0][1] == "#66ccff" for d in drones)


def test_chain_lane_rejects_short_control_path():
    fn = _load_fn()
    try:
        fn.chain_lane([(100, 100, 150), (180, 100, 150)], count=10, spacing_cm=65)
    except ValueError as exc:
        assert "路径太短" in str(exc)
    else:
        raise AssertionError("太短的 control path 应当抛错")


def test_gradient_to_enriches_color_without_breaking_alignment():
    """gradient_to 让执行器在同一耗时内逐 tick 渐变（dntg 持续变色），保持段尾对齐。"""
    fn = _load_fn()
    # 纯色基线
    a = [FakeDrone(100, 280), FakeDrone(250, 280)]
    fn.ripple_move(a, [(150, 200, 140), (350, 200, 160)], 2000, [0, 200],
                   colors=["#ff0000", "#0000ff"], hold_ticks=8)
    solid_colors = len({c for _, c in a[0].lights})
    # 同参数 + gradient_to
    b = [FakeDrone(100, 280), FakeDrone(250, 280)]
    fn.ripple_move(b, [(150, 200, 140), (350, 200, 160)], 2000, [0, 200],
                   colors=["#ff0000", "#0000ff"], hold_ticks=8, gradient_to=["#ffff00", "#00ffff"])
    grad_colors = {c for _, c in b[0].lights}
    assert solid_colors == 1, "纯色应只有一种颜色"
    assert len(grad_colors) > solid_colors, "渐变必须产生更多颜色"
    assert [d.time for d in a] == [d.time for d in b], "渐变不得改变段尾对齐"
    assert b[0].lights[0][1] == (255, 0, 0) and b[0].lights[-1][1] == (255, 255, 0), "渐变端点精确"

    # light_wave 与 group_relay 也接受 gradient_to
    w = [FakeDrone(), FakeDrone()]
    fn.light_wave(w, [0, 150], colors=["#ff0000", "#00ff00"], hold_ticks=6,
                  gradient_to=["#0000ff", "#ffff00"])
    assert w[0].lights[-1][1] == (0, 0, 255), "light_wave 渐变端点"
    g = [FakeDrone(100, 100), FakeDrone(300, 100)]
    fn.group_relay(g, [(100, 300, 140), (300, 300, 160)], [0, 1], 1000,
                   colors=("#aa0000", "#0000aa"), gradient_to=("#ffaa00", "#00aaff"))
    assert [d.time for d in g] == [2200, 2200], "group_relay 渐变保持两段对齐"


def test_composition_gate_counts_gradient_as_dynamic_lighting():
    code = """\
delays = ripple_delays(prev, mode="spiral", step_ms=150)
prev = ripple_move(drones, targets, 2600, delays, colors=warm, hold_ticks=12, gradient_to=cool)
"""
    features = extract_code_features(code)
    assert features["uses_gradient"]
    assert features["has_dynamic_lighting"], "gradient_to= 必须算动态灯光"


# ---------- 灯光母题 ----------

def test_fade_breathe_flash_and_beat():
    fn = _load_fn()
    d = FakeDrone()
    consumed = fn.fade_rgb(d, "#000000", (100, 200, 50), steps=5, interval_ms=100)
    assert consumed == 500 and len(d.lights) == 5
    assert d.lights[0][1] == (0, 0, 0) and d.lights[-1][1] == (100, 200, 50), "渐变端点精确"

    drones = [FakeDrone(), FakeDrone()]
    assert fn.fade_group(drones, "#220011", "#ff8844", duration_ms=1500) == 1500
    assert drones[0].time == drones[1].time == 1500

    drones = [FakeDrone()]
    consumed = fn.breathe_group(drones, (200, 100, 50), cycles=1, period_ms=400, floor=0.5)
    assert consumed == 400
    rgbs = [c for _, c in drones[0].lights]
    assert rgbs[0] == (200, 100, 50), "呼吸从满亮开始（衔接前一拍）"
    assert min(sum(c) for c in rgbs) >= sum((100, 50, 25)), "凹谷不低于 floor，亮灯不间断"

    drones = [FakeDrone(), FakeDrone()]
    consumed = fn.flash_group(drones, "#ffffff", times=3, on_ms=200, off_ms=100, alt_color="#ff0000")
    assert consumed == 900
    assert len(drones[0].offs) == 3, "3 次亮-灭"
    assert drones[0].lights[1][1] == (255, 0, 0), "双色交替"
    assert drones[0].lights[-1][1] == (255, 255, 255), "结束自动回亮"
    assert drones[0].time == drones[1].time == 900

    assert fn.beat_ms(120) == 500
    assert fn.beat_ms(120, 4) == 2000


# ---------- composition 门适配 ----------

def test_composition_recognizes_motif_features():
    code = """\
delays = ripple_delays(prev, mode="center_out", step_ms=150)
geo = custom_points([(120, 120, 120), (280, 120, 160), (440, 120, 200), (120, 280, 140), (280, 280, 180), (440, 280, 220), (120, 440, 130), (280, 440, 170), (440, 440, 210)], n=len(drones), min_xy_cm=90)
prev = ripple_move(drones, best_assign(prev, geo), 2600, delays, colors=palette)
prev = follow_chain(drones, wps, 700, lag_hops=1, colors=palette)
"""
    features = extract_code_features(code)
    assert features["has_time_stagger"], "ripple_move/follow_chain 计入时间错峰"
    assert features["has_indexed_stagger"]
    assert not features["uses_group_only_execution"]
    assert features["motif_move_calls"] == 2
    assert features["estimated_keyframe_count"] == 1 + 1 + 3, "custom_points + ripple + chain bonus"


def test_composition_recognizes_motif_lighting():
    code = """\
light_wave(drones, delays, palette, hold_ticks=6)
fade_group(drones, (255, 80, 40), (10, 0, 60), 2000)
flash_group(drones, "#ffffff", 4, 250, 150)
breathe_group(drones, (120, 40, 255))
"""
    features = extract_code_features(code)
    assert features["has_dynamic_lighting"], "灯光母题就是动态灯光"
    assert features["motif_light_calls"] == 4
    assert features["apply_light_calls"] >= 4, "灯光声明门通过"
    # tick 估算：light_wave 6+4 / fade 2000/100 / flash 4*(400)/100 / breathe 2*1600/100
    assert features["lighting_tick_estimate"] == 10 + 20 + 16 + 32
    assert features["rgb_tuple_color_count"] >= 3, "母题参数里的 RGB 三元组计入颜色数"
    assert features["z_range_cm"] is None, "颜色三元组不得污染 Z 范围统计"


def test_sync_gate_accepts_ripple_move():
    code = """\
# role: 波次展开
# motifs: 波次涟漪
# beat: 中速推进
# formation: 双排
# lighting: 光波扫过，rank 配色
delays = ripple_delays(prev, mode="sweep_x", step_ms=150)
geo = custom_points([(120, 120, 120), (280, 120, 160), (440, 120, 200), (120, 280, 140), (280, 280, 180), (440, 280, 220), (120, 440, 130), (280, 440, 170), (440, 440, 210)], n=len(drones), min_xy_cm=90)
prev = ripple_move(drones, best_assign(prev, geo), 2600, delays, colors=palette)
light_wave(drones, delays, palette, hold_ticks=6)
"""
    _result, errors = evaluate_composition(code, None, "S03")
    assert errors == [], f"母题写法应当全过: {errors}"


# ---------- preflight 适配 ----------

def test_preflight_rejects_static_follow_chain_too_dense():
    """Static raw follow_chain paths are now rejected before expensive runtime."""
    code = """\
wps = [(80 + 50 * k, 280, 150) for k in range(9)]
prev = follow_chain(drones, wps, 700, lag_hops=1)
"""
    r = preflight_check(code, segment_id="S03", drone_count=9)
    assert not r
    assert any("follow_chain 链上间距不足" in e for e in r.errors), r.errors


def test_preflight_accepts_chain_follow_safe_control_points():
    code = """\
ctrl = [(40,520,180), (280,300,160), (540,40,190)]
prev = chain_follow_safe(drones, ctrl, hop_ms=580, lag_hops=1, spacing_cm=65)
"""
    r = preflight_check(code, segment_id="S03", drone_count=9)
    assert r, r.errors


def test_preflight_rejects_light_wave_duplicate_delays():
    code = """\
prev = [(d.x, d.y, d.z) for d in drones]
delays3 = ripple_delays(prev, mode="by_index", step_ms=150)
golden_palette = ["#ffd080"] * len(drones)
light_wave(drones, prev, delays=delays3, palette=golden_palette, hold_ticks=8)
"""
    r = preflight_check(code, segment_id="S02", drone_count=9)
    assert not r
    assert any("light_wave 参数重复" in e for e in r.errors), r.errors


def test_preflight_rejects_nonexistent_drone_turn_on():
    code = """\
for d in drones:
    d.turn_on('#44aaff')
    d.delay(200)
"""
    r = preflight_check(code, segment_id="S03", drone_count=9)
    assert not r
    assert any("turn_on" in e for e in r.errors), r.errors


def test_preflight_rejects_apply_light_ticks_times_100():
    code = """\
ticks1 = 3
for d in drones:
    apply_light(d, '#ffaa44', ticks1 * 100)
"""
    r = preflight_check(code, segment_id="S06", drone_count=9)
    assert not r
    assert any("apply_light 第三个参数是 ticks" in e for e in r.errors), r.errors


def test_preflight_rejects_fade_group_unknown_color_keywords():
    code = """\
fade_group(drones, color1="#ffe4b5", color2="#303030", duration_ms=800)
"""
    r = preflight_check(code, segment_id="S06", drone_count=9)
    assert not r
    assert any("fade_group 不支持关键字参数" in e for e in r.errors), r.errors


def test_preflight_rejects_apply_light_same_duration_as_move():
    code = """\
flying_ms1 = 1800
ticks1 = flying_ms1 // 100
for i, drone in enumerate(drones):
    move2(drone, targets1[i], flying_ms1)
    apply_light(drone, '#ffcc66', ticks1)
"""
    r = preflight_check(code, segment_id="S06", drone_count=9)
    assert not r
    assert any("动作预算翻倍" in e for e in r.errors), r.errors


def test_preflight_rejects_group_relay_with_sync_assignment():
    code = """\
prev = [(d.x, d.y, d.z) for d in drones]
geo = custom_points([(80,120,140),(180,120,150),(280,120,160),(380,120,170),(480,120,180),
                     (80,440,140),(180,440,150),(280,440,160),(380,440,170)], n=len(drones))
gids = split_groups(prev, mode="left_right")
targets = best_assign(prev, geo)
prev = group_relay(drones, targets, gids, 2800, colors=("#ff6040","#4060ff"), gap_ms=250)
"""
    r = preflight_check(code, segment_id="S02", drone_count=9)
    assert not r
    assert any("group_relay 只是底层接力执行器" in e for e in r.errors), r.errors


def test_preflight_rgb_tuples_are_not_coordinates():
    code = """\
fade_group(drones, (255, 80, 40), (10, 0, 60), 2000)
flash_group(drones, (255, 255, 255), times=3, alt_color=(255, 0, 0))
palette = [(255, 60, 60), (60, 60, 255)]
light_wave(drones, delays, colors=palette, hold_ticks=6)
"""
    r = preflight_check(code, segment_id="S03", drone_count=9)
    assert not any("坐标常量" in e for e in r.errors), r.errors

    bad = "targets = [(600, 100, 50)]\n"
    r2 = preflight_check(bad, segment_id="S03", drone_count=9)
    assert any("坐标常量" in e for e in r2.errors), "真实坐标越界仍须拦截"


if __name__ == "__main__":
    for name, fn_obj in sorted(globals().items()):
        if name.startswith("test_") and callable(fn_obj):
            fn_obj()
            print(f"PASSED: {name}")
    print("\nALL MOTIF TESTS PASSED")
