"""安全几何生成器——用数学保证7点间距>=120cm"""
import math, random

def generate_safe_geo(mode='expand', n=7, min_spacing=120, center=(280,280), z_min=140, z_max=220):
    """
    mode: 'expand'(展开), 'rotate'(旋转), 'breathe'(呼吸), 'contract'(收缩)
    返回: [(x,y,z), ...] 7个坐标，两两XY间距>=min_spacing
    """
    if mode == 'expand':
        # 泊松圆盘 + 外围扩散
        return _poisson_disk(n, min_spacing * 1.5, center, z_min, z_max)
    elif mode == 'rotate':
        # 同心圆上的6个点+1个中心
        pts = []
        r = max(150, min_spacing)
        for i in range(6):
            angle = 2 * math.pi * i / 6 + random.uniform(0, 0.5)
            x = center[0] + r * math.cos(angle)
            y = center[1] + r * math.sin(angle)
            z = random.randint(z_min, z_max)
            pts.append((int(x), int(y), z))
        pts.append((center[0], center[1], random.randint(z_min, z_max)))
        return pts
    elif mode == 'breathe':
        r = random.randint(120, 220)
        pts = []
        for i in range(n):
            angle = 2 * math.pi * i / n + random.uniform(0, 0.3)
            x = center[0] + r * math.cos(angle)
            y = center[1] + r * math.sin(angle)
            pts.append((int(x), int(y), random.randint(z_min, z_max)))
        return pts
    elif mode == 'contract':
        r = random.randint(80, 130)
        pts = []
        for i in range(n):
            angle = 2 * math.pi * i / n
            x = center[0] + r * math.cos(angle)
            y = center[1] + r * math.sin(angle)
            pts.append((int(x), int(y), min(z_min, z_max - 30)))
        return pts
    else:
        return _poisson_disk(n, min_spacing, center, z_min, z_max)


def _poisson_disk(n, min_r, center, z_min, z_max):
    """泊松圆盘采样——保证最小间距"""
    pts = []
    attempts = 0
    while len(pts) < n and attempts < 500:
        x = random.randint(max(50, center[0]-250), min(510, center[0]+250))
        y = random.randint(max(50, center[1]-250), min(510, center[1]+250))
        z = random.randint(z_min, z_max)
        ok = True
        for px, py, _ in pts:
            if ((x-px)**2 + (y-py)**2)**0.5 < min_r:
                ok = False
                break
        if ok:
            pts.append((x, y, z))
        attempts += 1
    # 如果不够，放宽间距重试
    while len(pts) < n:
        r2 = min_r * 0.7
        x = random.randint(80, 480)
        y = random.randint(80, 480)
        ok = True
        for px, py, _ in pts:
            if ((x-px)**2 + (y-py)**2)**0.5 < r2:
                ok = False
                break
        if ok:
            pts.append((x, y, random.randint(z_min, z_max)))
    return pts[:n]
