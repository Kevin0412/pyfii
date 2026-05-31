"""_measure_degradation 回归测试——确保进入 sample_frames 循环且不抛 NameError。"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.validator import _measure_degradation


def test_degradation_with_mock_data():
    """Mock read_fii 返回真实形状数据，确保函数进入 sample_frames 循环。"""
    # 构造 7 架无人机 × 180 帧的假数据（3秒 @ 60fps）
    frames = 180
    data = []
    for d_i in range(7):
        drone_frames = []
        # 不同的位置让检测不完全是中心
        base_x = 100 + d_i * 60
        base_y = 100 + d_i * 40
        for f in range(frames):
            x = base_x + 30 * (f % 10)   # 来回摆动
            y = base_y + 20 * (f % 8)
            z = 120 + 50 * ((f // 60) % 2)  # 两段高度
            drone_frames.append(
                (1.0, x, y, z, 0.0, (10.0, 8.0, 2.0), (0.5, 0.4, 0.1))
            )
        data.append(drone_frames)

    # Mock _find_fii_dir 和 read_fii
    from core.validator import _find_fii_dir

    with patch.object(__import__('core.validator', fromlist=['_find_fii_dir']), '_find_fii_dir') as mock_find:
        mock_find.return_value = Path('/fake/output')
        with patch('pyfii.read_fii') as mock_read:
            mock_read.return_value = (data, 0.0, None)

            result = _measure_degradation(
                output_dir=Path('/fake/output'),
                window=(0.0, 3.0),
            )

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    # 检查是否包含预期指标
    for key in ['circle_like_fraction', 'order_stable_fraction', 'fixed_height_drones']:
        assert key in result, f"Missing key: {key} (keys: {list(result.keys())})"
        assert isinstance(result[key], (int, float)), f"{key} should be numeric: {type(result[key])}"

    print(f"degradation: circle={result['circle_like_fraction']}, "
          f"order={result['order_stable_fraction']}, "
          f"fixed_height={result['fixed_height_drones']}")
    print("PASSED")


if __name__ == "__main__":
    test_degradation_with_mock_data()
    print("OK")
