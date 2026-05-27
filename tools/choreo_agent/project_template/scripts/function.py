"""Agent 自定义函数库

用法: from function import *
纯 Python 标准库 + math，不依赖 pyfii。
agent 可自定义添加函数。
"""

import math

# ---------- 坐标裁剪 ----------
def clamp_xy(v): return max(0, min(560, int(round(v))))
def clamp_z(v):  return max(80, min(250, int(round(v))))

# ---------- 距离与飞行时间 ----------
def distance_3d(p1, p2):
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2 + (p2[2]-p1[2])**2)

def flight_time_ms(d, v, a):
    if d <= 0: return 0
    accel_dist = v*v/(2*a)
    t = 2*v/a + (d-2*accel_dist)/v if d >= 2*accel_dist else 2*math.sqrt(d/a)
    return int(math.ceil(t*1000))

def flight_time_s(d, v, a):
    """返回秒"""
    if d <= 0: return 0.0
    accel_dist = v*v/(2*a)
    return 2*v/a + (d-2*accel_dist)/v if d >= 2*accel_dist else 2*math.sqrt(d/a)

# ---------- 反算速度 (DNTG 模式) ----------
def vel_for_distance_time(distance_cm, time_s):
    """给定距离和时间，反算最小可用速度(cm/s)。a=2v。"""
    for v in range(50, 201):
        if time_s > flight_time_s(distance_cm, v, v*2):
            return v
    return 200  # 超出范围用最大值

# ---------- 几何辅助 ----------
def radial_point(cx, cy, r, angle_deg, z):
    rad = math.radians(angle_deg)
    return (clamp_xy(cx+r*math.cos(rad)), clamp_xy(cy+r*math.sin(rad)), clamp_z(z))

# ---------- 灯光 ----------
def apply_light(drone, color, ticks, interval_ms=100):
    """正弦渐变: drone是pyfii Drone, color='#RRGGBB'"""
    for tick in range(ticks):
        bright = int(100 + 155*math.sin(tick*math.pi/max(ticks,1)))
        r = int(color[1:3],16)*bright//255
        g = int(color[3:5],16)*bright//255
        b = int(color[5:7],16)*bright//255
        drone.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}")
        drone.delay(interval_ms)

# ---------- 颜色预设 ----------
COLORS_WARM  = ["#FFD700","#FF8C00","#FF6347","#FFB6C1","#FFA500"]
COLORS_COOL  = ["#87CEEB","#00CED1","#7B68EE","#00FF7F","#4169E1"]
COLORS_BRIGHT = ["#FF1493","#FFFF00","#00FFFF","#FF4500","#ADFF2F"]
COLORS_AMBER = ["#2255aa","#3388cc","#44aadd"]

# ---------- 排列 (如果core.best_assign可用则导入，否则本地实现) ----------
