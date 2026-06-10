"""Lit-hold exemption tests: still+lit = legitimate pose, still+dark = violation."""

from core.validator import (
    LIT_HOLD_MIN_ON_RATIO,
    SEGMENT_EDGE_BUFFER_S,
    _filter_unlit_intervals,
    _lights_on_ratio,
)


def _fake_data(n_drones, n_frames, rgb):
    """Synthetic read_fii rows: (t_ms, x, y, z, pad, live_rgb, rgb2)."""
    return [
        [(f * 16.7, 100.0 + i * 60, 100.0, 120.0, 0.0, rgb, (0, 0, 0)) for f in range(n_frames)]
        for i in range(n_drones)
    ]


def test_lights_on_ratio_lit_vs_dark():
    lit = _fake_data(4, 120, (255, 80, 0))
    dark = _fake_data(4, 120, (-1, -1, -1))
    assert _lights_on_ratio(lit, 0, 120) == 1.0
    assert _lights_on_ratio(dark, 0, 120) == 0.0
    # 黑色 (0,0,0) 也算灭灯
    black = _fake_data(4, 120, (0, 0, 0))
    assert _lights_on_ratio(black, 0, 120) == 0.0


def test_filter_keeps_dark_holds_drops_lit_holds():
    fps = 60
    segments = [(0.0, 2.0)]
    lit = _fake_data(4, 120, (255, 80, 0))
    dark = _fake_data(4, 120, (-1, -1, -1))
    assert _filter_unlit_intervals(lit, segments, fps) == []  # dntg 式亮灯定格合法
    assert _filter_unlit_intervals(dark, segments, fps) == segments  # 黑灯静止仍违规


def test_mixed_fleet_uses_ratio_threshold():
    fps = 60
    segments = [(0.0, 2.0)]
    # 4 机中 1 机亮灯 → 25% < 50% 阈值 → 仍违规
    data = _fake_data(3, 120, (-1, -1, -1)) + _fake_data(1, 120, (255, 255, 255))
    assert _filter_unlit_intervals(data, segments, fps) == segments
    # 4 机中 3 机亮灯 → 75% → 合法定格
    data2 = _fake_data(1, 120, (-1, -1, -1)) + _fake_data(3, 120, (255, 255, 255))
    assert _filter_unlit_intervals(data2, segments, fps) == []


def test_edge_buffer_covers_sanctioned_stagger():
    # delay(i*120) 9 机最大错峰 960ms + 起步坡 < 1.3s 缓冲
    assert SEGMENT_EDGE_BUFFER_S >= 1.3
    assert 0 < LIT_HOLD_MIN_ON_RATIO <= 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL LIT HOLD TESTS PASSED")
