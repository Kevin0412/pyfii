#!/usr/bin/env python3
"""
flight_log_analysis.py — 真实飞行遥测 vs pyfii 运动模型 对照分析

用法:  python3 tools/flight_log_analysis.py
依赖:  numpy, matplotlib（CJK 字体 Noto Sans CJK 或回退英文）
输入:  flight_logs/<flight>/telemetry.csv（本地，未入仓库）
输出:  doc/images/fig1..6_*.png, doc/images/metrics.json

见 doc/flight_log_trajectory_analysis.md。
"""
import csv, os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
# register a CJK font so Chinese labels render (not tofu boxes)
for _fp in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/home/kevin0412/.local/share/fonts/NotoSansCJKSC-Regular.ttf"]:
    if os.path.exists(_fp):
        fm.fontManager.addfont(_fp)
        plt.rcParams["font.family"] = fm.FontProperties(fname=_fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

LOGDIR = "flight_logs"
OUT = "doc/images"
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------
# 1. Load telemetry
# ----------------------------------------------------------------------------
def load(flight):
    p = os.path.join(LOGDIR, flight, "telemetry.csv")
    rows = list(csv.DictReader(open(p)))
    t = np.array([float(r["elapsed_ms"]) for r in rows]) / 1000.0
    x = np.array([float(r["x_cm"]) for r in rows])
    y = np.array([float(r["y_cm"]) for r in rows])
    z = np.array([float(r["z_cm"]) for r in rows])
    yaw = np.array([float(r["yaw_cdeg"]) for r in rows]) / 100.0
    mode = [r["flightmode"] for r in rows]
    return dict(t=t, x=x, y=y, z=z, yaw=yaw, mode=mode)

# ----------------------------------------------------------------------------
# 2. Faithful pyfii trapezoidal segment simulator
# ----------------------------------------------------------------------------
def sim_segment(P0, P1, vel, acc, fps=200):
    """Straight-line trapezoidal move P0->P1, full stop at P1. Matches read.py."""
    P0 = np.asarray(P0, float); P1 = np.asarray(P1, float)
    D = P1 - P0; R = float(np.linalg.norm(D))
    if R == 0:
        return [], 0.0
    u = D / R
    alenth = vel**2 / (2*acc)          # accel distance
    if R >= 2*alenth:                  # full trapezoid
        acctime = vel/acc
        total = 2*acctime + (R - 2*alenth)/vel
        sacc = alenth
    else:                              # triangle (never reaches vel)
        acctime = (R/acc)**0.5         # sqrt(2*(R/2)/acc)
        total = 2*acctime
        sacc = R/2
    dt = 1.0/fps
    pts = []
    t = 0.0
    while t < total:
        if t <= acctime:
            r = 0.5*acc*t*t
        elif t < total - acctime:
            r = sacc + vel*(t - acctime)
        else:
            r = R - 0.5*acc*(total - t)**2
        p = P0 + u*max(0.0, min(R, r))
        pts.append((t, p[0], p[1], p[2]))
        t += dt
    pts.append((total, P1[0], P1[1], P1[2]))
    return pts, total

def sim_route(cmds, start=(0,0,0), fps=200):
    """cmds: list of ('move', x,y,z, vel,acc) or ('hold', seconds).
    Returns global timeline arrays t,x,y,z and list of waypoint arrival (t, xyz)."""
    T=[]; X=[]; Y=[]; Z=[]; wpts=[]
    cur = np.array(start, float); tg = 0.0
    for c in cmds:
        if c[0] == 'move':
            _,x,y,z,vel,acc = c
            seg,dur = sim_segment(cur,(x,y,z),vel,acc,fps)
            for (tt,px,py,pz) in seg:
                T.append(tg+tt); X.append(px); Y.append(py); Z.append(pz)
            cur = np.array([x,y,z],float); tg += dur
            wpts.append((tg,x,y,z))
        elif c[0] == 'hold':
            dur = c[1]; dt=1.0/fps; tt=0.0
            while tt < dur:
                T.append(tg+tt); X.append(cur[0]); Y.append(cur[1]); Z.append(cur[2])
                tt += dt
            tg += dur
    return np.array(T),np.array(X),np.array(Y),np.array(Z),wpts

# ----------------------------------------------------------------------------
# 3. Reconstruct routes from trajectory_collect.py
# ----------------------------------------------------------------------------
# pyfii rule: takeoff & land use vel=200, acc=400 (hardcoded in read.py)
TO_V, TO_A = 200, 400

def route_grid(vel_xy, acc_xy, alt=120):
    c = [('move',0,0,alt,TO_V,TO_A), ('hold',3.0)]
    last=(0,0)
    for row in range(4):
        yt = min(40+row*80, 320); xt = 320 if row%2==0 else 40
        c += [('move',xt,yt,alt,vel_xy,acc_xy), ('hold',2.5)]
        last=(xt,yt)
    c += [('move',last[0],last[1],0,TO_V,TO_A)]   # land (pyfii: vel200 acc400)
    return c

def route_spiral(acc, alt=120, center=(180,180)):
    c = [('move',center[0],center[1],alt,50,acc), ('hold',3.0)]
    speeds=[50,100,150,150]
    for i,r in enumerate([40,80,120,160]):
        v=speeds[i]
        for cx,cy in [(center[0]+r,center[1]+r),(center[0]-r,center[1]+r),
                      (center[0]-r,center[1]-r),(center[0]+r,center[1]-r)]:
            c += [('move',cx,cy,alt,v,acc), ('hold',1.5)]
    return c

def route_zstairs(acc):
    # slow horizontal 50; pyfii ignores VelZ so uses 50 for vertical too
    c = [('move',180,180,60,TO_V,TO_A), ('hold',2.0)]
    for z in [80,120,160,200]:
        c += [('move',180,180,z,50,acc), ('hold',2.0)]
    return c

def route_rectangle(acc, alt=100):
    c = [('move',300,300,alt,150,acc), ('hold',3.0)]  # takeoff handled as move up before; approx
    for x,y in [(300,300),(40,300),(40,40),(300,40),(40,40)]:
        c += [('move',x,y,alt,150,acc), ('hold',2.0)]
    return c

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def speed_series(t,x,y,z):
    dt=np.diff(t)
    v=np.sqrt(np.diff(x)**2+np.diff(y)**2+np.diff(z)**2)/np.where(dt==0,1e-9,dt)
    return t[1:], v

def clean_glitches(x,y,z,thresh=60):
    """flag samples whose jump from previous > thresh cm (localization glitches)"""
    d=np.sqrt(np.diff(x)**2+np.diff(y)**2+np.diff(z)**2)
    flags=np.zeros(len(x),bool)
    flags[1:]=d>thresh
    return flags

print("Loaded modules OK")


import matplotlib.pyplot as plt

plt.rcParams.update({"figure.dpi":120,"font.size":10,"axes.grid":True,
                     "grid.alpha":0.3,"axes.axisbelow":True})
C_REAL="#e8543f"; C_MODEL="#2b6cb0"; C_CMD="#111"
metrics={}

# ============================================================ GRID (162500)
g = load("flight_20260709_162500")
cmds = route_grid(120,300,alt=120)
mt,mx,my,mz,wp = sim_route(cmds, start=(0,0,0))
corners=[(320,40),(40,120),(320,200),(40,280)]
gl = clean_glitches(g['x'],g['y'],g['z'],60)

# --- Fig 1: XY top view ---
fig,ax=plt.subplots(figsize=(7.2,6.6))
ax.plot(mx,my,'-',color=C_MODEL,lw=2.2,label="pyfii 模型 (直线+全停)",zorder=3)
# real path, break at glitches
xr=g['x'].copy(); yr=g['y'].copy()
seg_x=np.where(gl,np.nan,xr); seg_y=np.where(gl,np.nan,yr)
ax.plot(seg_x,seg_y,'-',color=C_REAL,lw=2.2,label="真实飞行 (平滑+切角)",zorder=4)
ax.scatter([c[0] for c in corners],[c[1] for c in corners],s=140,marker='*',
           color=C_CMD,zorder=5,label="指令航点")
for i,(cx,cy) in enumerate(corners):
    d=np.sqrt((g['x']-cx)**2+(g['y']-cy)**2); j=np.argmin(d)
    ax.annotate(f"欠冲 {d[j]:.0f}cm",(cx,cy),(cx+6,cy+10),fontsize=8,color=C_CMD)
    ax.plot([cx,g['x'][j]],[cy,g['y'][j]],':',color='gray',lw=1)
ax.scatter([22],[24],s=60,color='green',zorder=6,label="真实起点(22,24)≠(0,0)")
ax.set_xlabel("X (cm)"); ax.set_ylabel("Y (cm)")
ax.set_title("网格航线 俯视图：pyfii 模型 vs 真实飞行 (162500)")
ax.legend(loc="upper left",fontsize=8.5); ax.set_aspect('equal')
ax.set_xlim(-20,360); ax.set_ylim(-20,360)
plt.tight_layout(); plt.savefig(f"{OUT}/fig1_grid_xy.png"); plt.close()

# --- Fig 2: Z vs time (align takeoff) ---
i_to=np.argmax(g['z']>25); t0_real=g['t'][i_to]
fig,ax=plt.subplots(figsize=(8,3.6))
ax.plot(mt+ (t0_real-1.10), mz,color=C_MODEL,lw=2,label="pyfii 模型 Z")
ax.plot(g['t'], g['z'], color=C_REAL,lw=2,label="真实 Z")
ax.scatter(g['t'][gl],g['z'][gl],s=25,color='orange',zorder=5,label="定位跳变")
ax.set_xlabel("时间 (s)"); ax.set_ylabel("Z 高度 (cm)")
ax.set_title("高度剖面：起飞—巡航—降落 (162500)")
ax.legend(fontsize=8.5); plt.tight_layout()
plt.savefig(f"{OUT}/fig2_grid_z.png"); plt.close()

# --- Fig 3: Speed vs time ---
mts,mv = speed_series(mt,mx,my,mz)
rts,rv = speed_series(g['t'],g['x'],g['y'],g['z'])
rv_clean=rv.copy(); rv_clean[gl[1:]]=np.nan
fig,ax=plt.subplots(figsize=(8,3.6))
ax.plot(mts+(t0_real-1.10),mv,color=C_MODEL,lw=1.8,label="pyfii 模型速度 (梯形)")
ax.plot(rts,rv_clean,color=C_REAL,lw=1.8,label="真实速度 (平滑)")
ax.axhline(120,ls='--',color='gray',lw=1,label="配置 MaxVelXY=120")
ax.set_ylim(0,220); ax.set_xlabel("时间 (s)"); ax.set_ylabel("速度 (cm/s)")
ax.set_title("速度剖面：梯形(瞬时变加速) vs 真实(S形/连续) (162500)")
ax.legend(fontsize=8.5,ncol=2); plt.tight_layout()
plt.savefig(f"{OUT}/fig3_grid_speed.png"); plt.close()

# grid metrics
misses=[float(np.min(np.sqrt((g['x']-cx)**2+(g['y']-cy)**2))) for cx,cy in corners]
metrics['grid']=dict(model_dur=float(mt[-1]),real_dur=float(g['t'][-1]),
    corner_miss_cm=[round(m,1) for m in misses],mean_miss=round(float(np.mean(misses)),1),
    n_glitch=int(gl.sum()),start_offset_cm=round(float(np.hypot(22,24)),1))

# ============================================================ COMPLEX (162913)
c = load("flight_20260709_162913")
cl = clean_glitches(c['x'],c['y'],c['z'],70)
# full route: grid -> spiral -> zstairs -> rectangle  (acc 400; grid vel100)
cmds2 = (route_grid(100,400,alt=120)+route_spiral(400)+route_zstairs(400)+route_rectangle(400))
mt2,mx2,my2,mz2,wp2 = sim_route(cmds2,start=(0,0,0))

# --- Fig 4: complex XY path ---
fig,ax=plt.subplots(figsize=(7.4,6.8))
ax.plot(mx2,my2,'-',color=C_MODEL,lw=1.4,alpha=0.85,label="pyfii 模型(全程)")
xr=np.where(cl,np.nan,c['x']); yr=np.where(cl,np.nan,c['y'])
ax.plot(xr,yr,'-',color=C_REAL,lw=1.6,label="真实飞行(全程)")
ax.set_xlabel("X (cm)"); ax.set_ylabel("Y (cm)")
ax.set_title("复合航线 俯视图：网格+螺旋+阶梯+矩形 (162913)")
ax.legend(fontsize=9); ax.set_aspect('equal')
plt.tight_layout(); plt.savefig(f"{OUT}/fig4_complex_xy.png"); plt.close()

# --- Fig 5: z-stairs vertical speed (VelZ ignored) -- real data only, avoid timeline mismatch ---
vz=np.abs(np.diff(c['z'])/np.diff(c['t']))
fig,ax=plt.subplots(2,1,figsize=(8,5.4),sharex=True)
ax[0].axvspan(50,59,color='gold',alpha=0.15,label="阶梯高度段")
ax[0].plot(c['t'],c['z'],color=C_REAL,lw=1.6,label="真实 Z")
ax[0].set_ylabel("Z (cm)"); ax[0].legend(fontsize=8.5,loc="upper left")
ax[0].set_title("复合航线 高度与垂直速度：真实数据 (162913)")
ax[1].axvspan(50,59,color='gold',alpha=0.15)
ax[1].plot(c['t'][1:],vz,color=C_REAL,lw=1.2,label="真实 |vZ|")
ax[1].axhline(60,ls='--',color='green',lw=1.2,label="配置 MaxVelZ=60")
ax[1].axhline(50,ls='-',color=C_MODEL,lw=1.2,label="pyfii 用 VelXY=50 建模垂直")
ax[1].axhline(30,ls=':',color='purple',lw=1.2,label="slow VelZ=30")
ax[1].set_ylabel("|vZ| (cm/s)"); ax[1].set_xlabel("时间 (s)")
ax[1].set_ylim(0,160); ax[1].legend(fontsize=8,ncol=2,loc="upper left")
ax[1].annotate("起飞/降落定位跳变尖峰",(6,150),(15,140),fontsize=8,
               arrowprops=dict(arrowstyle="->",color='gray'))
plt.tight_layout(); plt.savefig(f"{OUT}/fig5_zstairs.png"); plt.close()

# --- Fig 6: glitch / noise characterization ---
allv=[]
fig,ax=plt.subplots(figsize=(8,3.6))
for f,name,col in [("flight_20260709_162500","162500 grid","#e8543f"),
                   ("flight_20260709_162913","162913 complex","#2b6cb0"),
                   ("flight_20260709_163106","163106 complex","#38a169")]:
    d=load(f); ts,v=speed_series(d['t'],d['x'],d['y'],d['z']); allv.append(v)
    ax.plot(ts,v,lw=1.1,color=col,alpha=0.8,label=name)
ax.axhline(200,ls='--',color='gray',label="物理上限≈200cm/s")
ax.set_yscale('log'); ax.set_xlabel("时间 (s)"); ax.set_ylabel("采样间速度 (cm/s, log)")
ax.set_title("真实数据中的定位跳变：单帧速度尖峰 (>1000cm/s 物理不可能)")
ax.legend(fontsize=8.5,ncol=2); plt.tight_layout()
plt.savefig(f"{OUT}/fig6_glitches.png"); plt.close()

# complex metrics
allv=np.concatenate(allv)
metrics['complex']=dict(model_dur=float(mt2[-1]),real_dur=float(c['t'][-1]),
    n_glitch_162913=int(cl.sum()),
    glitch_pct=round(100*float(cl.sum())/len(cl),1),
    vz_max_real=round(float(np.nanmax(vz)),0))
metrics['noise']=dict(
    frac_speed_gt_250=round(100*float(np.mean(allv>250)),1),
    max_speed_spike=round(float(np.nanmax(allv)),0))

# z-stairs real vertical climb rate: isolate the staircase window (x,y near 180, z rising)
zwin=(c['t'][1:]>50)&(c['t'][1:]<59)
climb=vz[zwin & (vz>12) & (vz<80)]   # active-climb frames, drop glitches
metrics['vertical']=dict(
    real_climb_cm_s=[round(float(np.percentile(climb,25)),0),
                     round(float(np.median(climb)),0),
                     round(float(np.percentile(climb,75)),0)] if len(climb) else [],
    pyfii_vertical_vel=50.0,   # z-stairs sets VelXY=50; pyfii uses it for vertical (VelZ ignored)
    config_MaxVelZ=[30,60],
    note="pyfii ignores VelZ/AccZ -> vertical moves use last VelXY; here 50 vs real ~25-44")

json.dump(metrics,open(f"{OUT}/metrics.json","w"),ensure_ascii=False,indent=2)
print(json.dumps(metrics,ensure_ascii=False,indent=2))
print("\nFIGS:",sorted(os.listdir(OUT)))
