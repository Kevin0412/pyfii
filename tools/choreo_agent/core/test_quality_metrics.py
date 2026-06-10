"""Quality metric tests: mirror symmetry as readability proxy."""

from core.quality_report import mirror_symmetry_error


def test_mirror_pairs_score_near_zero():
    # dntg t=13 式 3-1-3 点阵：每点都有穿过中心的镜像伙伴
    pts = [
        (520, 465), (40, 95),
        (280, 465), (280, 95),
        (40, 465), (520, 95),
        (280, 280),
    ]
    assert mirror_symmetry_error(pts) < 1.0


def test_even_line_scores_low():
    # 等距直线是点对称的
    pts = [(100 + i * 60, 200 + i * 40) for i in range(9)]
    assert mirror_symmetry_error(pts) < 1.0


def test_ring_scores_low():
    from math import cos, pi, sin

    pts = [(280 + 170 * cos(2 * pi * k / 8), 280 + 170 * sin(2 * pi * k / 8)) for k in range(8)]
    assert mirror_symmetry_error(pts) < 1.0


def test_scatter_scores_high():
    # 我们 staticgeo run S02 帧的实际散点（来自帧分析）
    pts = [
        (157, 337), (464, 429), (384, 494), (288, 518), (517, 266),
        (504, 364), (213, 507), (443, 106), (488, 167),
    ]
    assert mirror_symmetry_error(pts) > 60


def test_small_sets_safe():
    assert mirror_symmetry_error([(100, 100)]) == 0.0
    assert mirror_symmetry_error([(100, 100), (200, 200)]) == 0.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL QUALITY METRIC TESTS PASSED")
