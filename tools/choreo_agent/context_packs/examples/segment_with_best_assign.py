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
for i, drone in enumerate(drones):
    drone.intime(4)
    drone.VelXY(200, 400)
    drone.VelZ(200, 400)

prev = [(drone.x, drone.y, 110) for drone in drones]
for gi in range(len(geo)):
    # AI 离线调用 best_assign，硬编码结果
    prev_xy = [(p[0], p[1]) for p in prev]
    target_xy = [(t[0], t[1]) for t in geo[gi]]
    perm, _ = best_assign(prev_xy, target_xy)

    for i, drone in enumerate(drones):
        tx, ty, tz = geo[gi][perm[i]]
        dist_cm = math.dist((prev[i][0], prev[i][1]), (tx, ty))
        speed = min(200, max(150, int(dist_cm / 2.0)))
        drone.VelXY(speed, speed * 2)
        drone.VelZ(speed, speed * 2)
        drone.move2(clamp_xy(tx), clamp_xy(ty), clamp_z(tz + 20 * math.sin(i)))
        apply_light(drone, colors[gi], 15)
        drone.delay(1500)
    prev = [(geo[gi][perm[i]][0], geo[gi][perm[i]][1], geo[gi][perm[i]][2]) for i in range(N)]

# === PYFII_AGENT_SEGMENT_END S01 ===
