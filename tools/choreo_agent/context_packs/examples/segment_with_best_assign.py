# === PYFII_AGENT_SEGMENT_START S01 locked=false ===
# intent: 初始展开，安全几何引导
# start_time: 4.0
# end_time: 14.0
#
# Agent planning notes, not runtime code:
# - keyframe intervals, safe assignments, and motion budgets were computed before writing this segment.
# - perms / speeds / accels / delays below are hard-coded planning results.

geo_layers = [
    [
        (90, 145, 115),
        (175, 110, 135),
        (270, 150, 170),
        (365, 115, 135),
        (455, 155, 115),
        (235, 280, 195),
        (345, 320, 155),
    ],
    [
        (70, 230, 130),
        (160, 315, 165),
        (250, 405, 205),
        (335, 380, 165),
        (450, 300, 135),
        (225, 145, 115),
        (375, 175, 185),
    ],
    [
        (85, 430, 140),
        (165, 330, 180),
        (260, 245, 210),
        (350, 245, 155),
        (455, 335, 125),
        (225, 465, 165),
        (365, 455, 195),
    ],
]

perms = [
    (0, 1, 2, 3, 4, 5, 6),
    (5, 0, 1, 2, 3, 6, 4),
    (0, 1, 2, 3, 4, 5, 6),
]
assigned_layers = [
    [geo_layers[gi][perms[gi][i]] for i in range(7)]
    for gi in range(3)
]

speeds = [
    [75, 85, 92, 88, 78, 100, 96],
    [130, 145, 150, 138, 120, 132, 148],
    [95, 105, 112, 108, 90, 118, 122],
]
accels = [
    [95, 110, 120, 115, 100, 130, 125],
    [230, 260, 280, 250, 220, 240, 270],
    [135, 150, 165, 155, 130, 170, 180],
]
light_ticks = [4, 5, 4]
delays_ms = [
    [2250, 2150, 2100, 2150, 2200, 2050, 2100],
    [2500, 2400, 2350, 2450, 2550, 2450, 2350],
    [2650, 2550, 2500, 2550, 2650, 2450, 2400],
]
colors = ["#2255aa", "#33aadd", "#ffcc66"]

for i, drone in enumerate(drones):
    drone.inittime(4)
    for gi, targets in enumerate(assigned_layers):
        tx, ty, tz = targets[i]
        drone.VelXY(speeds[gi][i], accels[gi][i])
        drone.VelZ(speeds[gi][i], accels[gi][i])
        drone.move2(clamp_xy(tx), clamp_xy(ty), clamp_z(tz))
        apply_light(drone, colors[gi], light_ticks[gi])
        drone.delay(delays_ms[gi][i])

prev = assigned_layers[-1]

# === PYFII_AGENT_SEGMENT_END S01 ===
