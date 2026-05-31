"""_measure_degradation 回归测试——确保不抛 NameError。"""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.validator import _measure_degradation


def test_degradation_no_name_error():
    """对空模板调用 _measure_degradation，确保不抛异常。"""
    output_dir = Path(__file__).resolve().parent.parent / "project_template" / "output"
    try:
        result = _measure_degradation(output_dir, window=(4.0, 13.0))
    except Exception as e:
        # 空模板可能无 .fii — 这 OK
        if "empty fii" in str(e).lower() or "list index" in str(e).lower():
            print(f"空模板无数据，跳过 (expected: {e})")
            return
        raise
    
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    print(f"result: {result}")
    print("PASSED")


if __name__ == "__main__":
    test_degradation_no_name_error()
    print("OK")
