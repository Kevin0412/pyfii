"""Composition gate tests."""

from core.composition import evaluate_composition, extract_design_card, extract_code_features
from core.validator import ValidationResult


PLAN = {
    "segment_roles": {
        "S03": {
            "role": "卡农变奏：分组先后启动，形成交错呼应。",
            "motifs": ["分组卡农", "交叉换位"],
            "avoid": ["全队同步单调平移", "无高度差"],
        },
        "S05": {
            "role": "明亮高潮：全场尺度爆发。",
            "motifs": ["中心爆点", "边界扩张"],
            "avoid": ["保守小动作"],
        },
        "S04": {
            "role": "抒情中段：几何展开和高度层呼吸。",
            "motifs": ["抒情几何", "高低三层"],
            "avoid": ["同步大块移动"],
        },
        "S06": {
            "role": "尾声署名：从高潮回收到清晰、优雅、可识别的结束姿态。",
            "motifs": ["署名姿态", "温暖白光", "斜线/宽V母题回忆"],
            "avoid": ["新增随机主题", "长时间悬停", "挤到中心"],
        },
    }
}


def test_extract_design_card_from_leading_comments():
    card = extract_design_card(
        """
# role: 卡农变奏
# motifs: 分组卡农; 交叉换位
# beat: 两组错峰推进
# formation: 斜线到宽V
# lighting: 蓝白追光
auto_init(drones)
"""
    )

    assert card["role"] == "卡农变奏"
    assert "分组卡农" in card["motifs"]


def test_composition_gate_requires_design_card():
    _features, errors = evaluate_composition(
        "auto_init(drones)\nprev = []\n",
        PLAN,
        "S03",
    )

    assert errors
    assert "缺少设计卡" in errors[0]


def test_composition_gate_requires_stagger_for_canon_role():
    code = """
# role: 卡农变奏
# motifs: 分组卡农; 交叉换位
# beat: 两组错峰推进
# formation: 斜线到宽V
# lighting: 蓝白追光
auto_init(drones)
for i, drone in enumerate(drones):
    move2(drone, (100, 120, 150), 3000)
    apply_light(drone, "#44aaff", 4)
    drone.delay(2900)
"""

    _features, errors = evaluate_composition(code, PLAN, "S03")

    assert errors
    assert any("错峰" in item for item in errors)


def test_composition_gate_accepts_card_with_stagger_and_motif():
    code = """
# role: 卡农变奏
# motifs: 分组卡农; 交叉换位
# beat: 两组错峰推进
# formation: 斜线到宽V
# lighting: 蓝白追光
auto_init(drones)
for i, drone in enumerate(drones):
    drone.delay((i % 3) * 120)
    move2(drone, (100 + i * 40, 120, 120 + (i % 3) * 45), 3000)
    apply_light(drone, "#44aaff", 4)
    drone.delay(2900)
"""

    features, errors = evaluate_composition(
        code,
        PLAN,
        "S03",
        degradation={"window_z_range_cm": 120},
    )

    assert errors == []
    assert features["features"]["has_indexed_stagger"]


def test_composition_gate_blocks_group_only_execution_for_formal_segments():
    code = """
# role: 卡农变奏
# motifs: 分组卡农; 交叉换位
# beat: 三组错峰推进
# formation: 斜线到宽V
# lighting: 蓝白追光
auto_init(drones)
targets = best_assign(prev, geo)
prev = move_group_staggered(drones, targets, 3000, "#44aaff", 4, group_mod=3, stagger_ms=120)
"""

    features, errors = evaluate_composition(
        code,
        PLAN,
        "S03",
        degradation={"window_z_range_cm": 120},
    )

    assert any("只使用 move_group" in item for item in errors)
    assert features["features"]["uses_group_only_execution"]
    assert features["features"]["move_group_staggered_calls"] == 1


def test_composition_gate_blocks_geo_template_in_formal_body_segment():
    code = """
# role: 明亮高潮
# motifs: 中心爆点; 边界扩张
# beat: 爆发后回卷
# formation: geo模板箭头到宽V
# lighting: 暖金白爆闪
auto_init(drones)
geo = geo_arrow(len(drones), z_layers=(100, 160, 220), spread=1.2)
targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(3000))
prev = move_group(drones, targets, 3000, "#ffffff", 4)
"""

    features, errors = evaluate_composition(code, PLAN, "S05")

    assert features["features"]["geo_template_calls"]["geo_arrow"] == 1
    assert any("已下线几何模板" in item for item in errors)


def test_extract_code_features_detects_custom_points_as_handwritten_geometry():
    features = extract_code_features(
        """
geo = custom_points([
    (60,60,100),(180,60,160),(300,60,220),
    (420,60,120),(540,60,180),(120,240,240),
    (280,280,140),(440,240,200),(280,500,160),
], n=len(drones), min_xy_cm=90)
"""
    )

    assert features["uses_custom_points"]
    assert features["custom_points_calls"] == 1
    assert features["has_handwritten_geometry"]
    assert features["estimated_keyframe_count"] == 1
    assert features["xyz_literal_count"] == 9


def test_composition_gate_blocks_underdeveloped_s04():
    code = """
# role: 抒情中段
# motifs: 抒情几何; 高低三层
# beat: 两个同步大块
# formation: 边界到中心
# lighting: 蓝白
auto_init(drones)
geo = custom_points([
    (80,80,100),(80,280,160),(80,480,220),
    (280,100,120),(280,300,180),(280,500,240),
    (500,80,140),(500,280,200),(500,480,160),
], n=len(drones), min_xy_cm=90)
targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(3200))
for i, drone in enumerate(drones):
    move2(drone, targets[i], 3200)
    apply_light(drone, "#ffffff", 4)
    drone.delay(2900)
prev = [(t[0], t[1], t[2]) for t in targets]
"""

    _features, errors = evaluate_composition(code, PLAN, "S04")

    assert any("至少需要 4 个明确 keyframe" in item for item in errors)
    assert any("至少需要 3 种颜色" in item for item in errors)


def test_composition_gate_blocks_underpowered_climax():
    code = """
# role: 明亮高潮
# motifs: 中心爆点; 边界扩张
# beat: 爆发后回卷
# formation: 中心爆点到边界框线
# lighting: 暖金白爆闪
auto_init(drones)
for i, drone in enumerate(drones):
    move2(drone, (100 + i * 40, 120, 160), 3000)
    apply_light(drone, "#ffffff", 4)
    drone.delay(2900)
"""

    _features, errors = evaluate_composition(
        code,
        PLAN,
        "S05",
        motion_quality={"max_excursion_cm": 80},
    )

    assert any("高潮段动作幅度不足" in item for item in errors)


def test_composition_gate_does_not_treat_tail_recovery_as_climax():
    code = """
# role: 尾声署名
# motifs: 署名姿态; 温暖白光; 斜线/宽V母题回忆
# beat: 收束到结束姿态
# formation: 三列署名姿态
# lighting: 温暖白光
auto_init(drones)
geo = custom_points([
    (80,80,100),(80,280,160),(80,480,220),
    (280,100,120),(280,300,180),(280,500,240),
    (500,80,140),(500,280,200),(500,480,160),
], n=len(drones), min_xy_cm=90)
targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(3200))
for i, drone in enumerate(drones):
    move2(drone, targets[i], 3200)
    apply_light(drone, "#ffffff", 4)
    drone.delay(2900)
prev = [(t[0], t[1], t[2]) for t in targets]
"""

    _features, errors = evaluate_composition(
        code,
        PLAN,
        "S06",
        motion_quality={"max_excursion_cm": 80},
    )

    assert not any("高潮段动作幅度不足" in item for item in errors)
    assert not any("高潮/爆发段灯光过单一" in item for item in errors)


def test_composition_gate_requires_two_stage_s06_finish():
    code = """
# role: 尾声署名
# motifs: 署名姿态; 温暖白光; 斜线/宽V母题回忆
# beat: 单段收束
# formation: 三列署名姿态
# lighting: 温暖白光
auto_init(drones)
geo = custom_points([
    (80,80,100),(80,280,160),(80,480,220),
    (280,100,120),(280,300,180),(280,500,240),
    (500,80,140),(500,280,200),(500,480,160),
], n=len(drones), min_xy_cm=90)
targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(3200))
for i, drone in enumerate(drones):
    move2(drone, targets[i], 3200)
    apply_light(drone, "#ffffff", 4)
    drone.delay(2900)
prev = [(t[0], t[1], t[2]) for t in targets]
"""

    _features, errors = evaluate_composition(code, PLAN, "S06")

    assert any("两段式收尾" in item for item in errors)


def test_validation_result_passed_requires_composition_ok_for_formal_segments():
    result = ValidationResult()
    result.expected_drone_count = 7
    result.exit_state = [[100, 100, 150]] * 7
    result.compile_ok = True
    result.run_ok = True
    result.read_fii_ok = True
    result.distance_warnings = 0
    result.action_warnings = 0
    result.dense_min_distance_cm = 120
    result.code_quality_ok = True
    result.continuity_required = True
    result.hover_check_ok = True
    result.motion_envelope_ok = True
    result.effective_motion_ok = True
    result.motion_quality_ok = True
    result.composition_ok = False
    result.composition_errors = ["缺少设计卡"]

    assert not result.passed
    assert "章法失败" in result.repair_feedback()


def test_extract_code_features_detects_colors_and_stagger():
    features = extract_code_features(
        """
for i, drone in enumerate(drones):
    drone.delay((i % 2) * 100)
    move2(drone, (100, 120, 150), 3000)
    apply_light(drone, "#ffffff", 4)
    apply_light(drone, "#ffcc44", 2)
"""
    )

    assert features["has_indexed_stagger"]
    assert features["move2_calls"] == 1
    assert features["apply_light_calls"] == 2
    assert features["color_literals"] == ["#ffcc44", "#ffffff"]
