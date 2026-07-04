"""物理/协议常量单一来源（P1）。

规则：门代码（validator/preflight/composition/session/planning_pass）与
prompt 散文（prompt_builder/planning_pass/skills 的 f-string）一律从这里取值；
project_template/scripts/function.py 因"零依赖纯标准库"是承重属性（六处
spec_from_file_location 加载，含生产 skills.py 的注册表校验）**不 import 本模块**，
其内部字面量由 core/test_limits_sync.py 的 AST 同步测试钉死；pyfii_guide.md 的
三行结构化数字由锚定 regex 同步测试钉死。

改动任何值 = 门判定/prompt 字节双通道变更 → 必须走 STABILITY_TEST_PLAN 双模型矩阵。
"""

# 碰撞硬下限（pyfii core 物理线）：任意两机 XY 距离必须 > 此值。
# 门判定统一用严格大于（dense_min > FLOOR）；等于 51.0 视为不通过。
COLLISION_FLOOR_CM = 51.0

# 场地边界（cm）
FIELD_XY_MIN = 0.0
FIELD_XY_MAX = 560.0
Z_MIN_CM = 80.0
Z_MAX_CM = 250.0

# 演出结构
MIN_SHOW_END_S = 60.0  # LAND 结束不得早于此（session 动态追加 S07+ 的依据）

# 速度/加速度物理界（单一来源在 motion_math，这里 re-export 供 prompt/门统一取用）
from .motion_math import (  # noqa: E402,F401
    MAX_ACCEL_CM_S2,
    MAX_SPEED_CM_S,
    MIN_ACCEL_CM_S2,
    MIN_SPEED_CM_S,
)
