# === PYFII_AGENT_SEGMENT_START S01 locked=false ===
# intent: 初始展开，安全几何引导
# start_time: 4.0
# end_time: 14.0

geo = [
    [(S[i][0]+20*math.sin(i), S[i][1]+20*math.cos(i), 120) for i in range(N)],
    [(280+140*math.cos(2*math.pi*i/N), 280+140*math.sin(2*math.pi*i/N), 135) for i in range(N)],
    [(80+i*120, 180, 150) if i<4 else (90+(i-3)*120, 390, 160) for i in range(N)],
]

colors = ["#2255aa", "#3388cc", "#44aadd"]
intervals_s = [3.2, 3.4, 3.1]
prev = [(drone.x, drone.y, 110) for drone in drones]
assigned_layers = []
for gi, layer in enumerate(geo):
    prev_xy = [(p[0], p[1]) for p in prev]
    target_xy = [(t[0], t[1]) for t in layer]
    perm, _ = best_assign(prev_xy, target_xy)
    assigned = [layer[perm[i]] for i in range(N)]
    assigned_layers.append(assigned)
    prev = assigned

for i, drone in enumerate(drones):
    drone.inittime(4)
    current = (drone.x, drone.y, 110)
    for gi, targets in enumerate(assigned_layers):
        tx, ty, tz = targets[i]
        target = (clamp_xy(tx), clamp_xy(ty), clamp_z(tz + 20 * math.sin(i)))
        dist_cm = math.dist(current, target)
        interval_s = intervals_s[gi]
        speed = min(200, max(80, int(dist_cm / max(0.5, interval_s - 0.5))))
        accel = [130, 220, 170][gi]
        drone.VelXY(speed, accel)
        drone.VelZ(speed, accel)
        drone.move2(*target)
        apply_light(drone, colors[gi], 3)
        drone.delay(max(120, int(interval_s * 1000) - 300))
        current = target

prev = assigned_layers[-1]

# === PYFII_AGENT_SEGMENT_END S01 ===
