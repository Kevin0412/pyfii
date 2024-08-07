from typing import List, Tuple
import numpy as np

# 类型别名 为了兼容3.12以下Python版本没有使用type Alias = ...语法

Vec2 = np.ndarray | Tuple[float, float] | List[float]
Vec3 = np.ndarray | Tuple[float, float, float] | List[float]

Degree = float  # 角度制浮点数
Radian = float  # 弧度制浮点数
