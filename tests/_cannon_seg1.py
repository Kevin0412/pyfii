#!/usr/bin/env python3
import sys,math,os,itertools
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT/"src"))
import pyfii as pf

N=7;OUT=REPO_ROOT/"output"/"deepseek_cannon";MUSIC=str(REPO_ROOT/"cannon_in_D.mp3")
ds=[pf.Drone(0,0,pf.drone_config_6m,f"192.168.51.{51+i}") for i in range(N)]

def cl(x):return max(10,min(550,int(round(x))))
def cz(z):return max(80,min(240,int(round(z))))
def hd(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])

def best_assign(starts, targets):
    best_score, best = -1e9, None
    for perm in itertools.permutations(range(N)):
        tt = [targets[i] for i in perm]
        md = 1e9
        for ratio in [0.2, 0.4, 0.6, 0.8]:
            for i in range(N):
                for j in range(i+1, N):
                    ai = tuple(starts[i][k]*ratio + tt[i][k]*(1-ratio) for k in range(2))
                    aj = tuple(starts[j][k]*ratio + tt[j][k]*(1-ratio) for k in range(2))
                    d = hd(ai, aj)
                    if d < md: md = d
        score = md*100 - max(math.dist(starts[i],tt[i]) for i in range(N))*0.5
        if score > best_score:
            best_score = score
            best = tt
    return best

S=[(60,120),(180,60),(350,60),(500,160),(500,380),(350,480),(160,480)]
for i,d in enumerate(ds):
    d.X=d.x=S[i][0];d.Y=d.y=S[i][1];d.takeoff(1,110)
for i,d in enumerate(ds): d.intime(4); d.VelXY(120,240); d.VelZ(120,240)

# 段1: 4几何
geo = [
    [(S[i][0]+20*math.sin(i), S[i][1]+20*math.cos(i), 120+5*i) for i in range(N)],
    [(280+140*math.cos(2*math.pi*i/N), 280+140*math.sin(2*math.pi*i/N), 135+5*i) for i in range(N)],
    [(80+i*120, 180, 145) if i<4 else (80+(i-3)*120, 400, 145) for i in range(N)],
    [(80,80,150+5*i),(480,80,150+5*i),(80,480,150+5*i),(480,480,150+5*i),(280,280,150+5*i),(200,200,150+5*i),(360,360,150+5*i)],
]
colors = ["#2266aa","#3388cc","#44aadd","#4dd7ff"]

prev_pos = [(d.x, d.y, 110) for d in ds]
for gi in range(4):
    targets = best_assign(prev_pos, geo[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        d.TurnOnAll(colors[gi])
        if gi < 3: d.delay(3000)
        else: d.delay(1500); d.TurnOffAll(); d.delay(1500)
    prev_pos = targets


# 段2: 4个安全几何
geo2 = [
    [(280+150*math.cos(2*math.pi*i/N), 280+150*math.sin(2*math.pi*i/N), 140+25*math.sin(2*math.pi*i/N)) for i in range(N)],  # 环
    [(60+120*i, 160, 140+10*i) if i<4 else (180+120*(i-3), 400, 160) for i in range(N)],  # 双排(120间距)
    [(80,80,165),(480,80,165),(80,480,165),(480,480,165),(280,280,165),(200,200,165),(360,360,165)],  # 四角+内
    [(280+150*math.cos(2*math.pi*i/N+math.pi/7), 280+150*math.sin(2*math.pi*i/N+math.pi/7), 150+20*math.sin(2*math.pi*i/N+math.pi/7)) for i in range(N)],  # 旋转环
]
colors2 = ["#ffbb33","#ffaa22","#ff9911","#ffdd59"]
for i,d in enumerate(ds): d.intime(16); d.VelXY(90,180); d.VelZ(90,180)
for gi in range(4):
    targets = best_assign(prev_pos, geo2[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        d.TurnOnAll(colors2[gi]); d.delay(4000)
    prev_pos = targets


# 段3: 4个安全几何
geo3 = [
    [(280+170*math.cos(2*math.pi*i/N), 280+170*math.sin(2*math.pi*i/N), 185) for i in range(N)],  # 大环
    [(60+120*i, 180, 190) if i<4 else (180+120*(i-3), 380, 190) for i in range(N)],  # 双排
    [(80,80,195),(480,80,195),(80,480,195),(480,480,195),(280,280,195),(200,200,195),(360,360,195)],  # 四角
    [(280+170*math.cos(2*math.pi*i/N+math.pi/7), 280+170*math.sin(2*math.pi*i/N+math.pi/7), 200) for i in range(N)],  # 旋转环
]
colors3 = ["#ff5588","#ff4477","#ff3366","#ff2266"]
for i,d in enumerate(ds): d.intime(32); d.VelXY(120,240); d.VelZ(120,240)
for gi in range(4):
    targets = best_assign(prev_pos, geo3[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        d.TurnOnAll(colors3[gi]); d.delay(4000)
    prev_pos = targets


# 段4: 4个几何
geo4 = [
    [(280+190*math.cos(2*math.pi*i/N), 280+190*math.sin(2*math.pi*i/N), 205) for i in range(N)],  # 大环
    [(60+120*i, 200, 210) if i<4 else (180+120*(i-3), 360, 210) for i in range(N)],  # 双排
    [(80,80,215),(480,80,215),(80,480,215),(480,480,215),(280,280,215),(200,200,215),(360,360,215)],  # 四角
    [(280+190*math.cos(2*math.pi*i/N+math.pi/7), 280+190*math.sin(2*math.pi*i/N+math.pi/7), 220) for i in range(N)],  # 旋转环
]
colors4 = ["#ffffff","#ffeeee","#ffdddd","#ffcccc"]
for i,d in enumerate(ds): d.intime(48); d.VelXY(160,320); d.VelZ(160,320)
for gi in range(4):
    targets = best_assign(prev_pos, geo4[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        d.TurnOnAll(colors4[gi]); d.delay(4000)
    prev_pos = targets

# 段5: 收束降落
for i,d in enumerate(ds): d.intime(64); d.VelXY(60,120); d.VelZ(60,120)
geo5 = [(280+100*math.cos(2*math.pi*i/N), 280+100*math.sin(2*math.pi*i/N), 150) for i in range(N)]
targets = best_assign(prev_pos, geo5)
for i,d in enumerate(ds):
    tx, ty, tz = targets[i]
    d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
    d.TurnOnAll("#48dbfb"); d.delay(2000); d.TurnOffAll(); d.delay(2000)
for i,d in enumerate(ds):
    d.intime(70); d.land()

for d in ds: d.end()
os.makedirs(str(OUT),exist_ok=True)
pf.Fii(str(OUT),ds,music=MUSIC).save(field=6)
print("saved")

import numpy as np,warnings;warnings.filterwarnings('ignore')
data,t0,music,field,dev=pf.read_fii(str(OUT),fps=60,ignore_acc=False)
ax=[p[1]for d in data for p in d if p[1]>0];ay=[p[2]for d in data for p in d if p[1]>0]
md=9999;mf=min(len(d)for d in data)
for t in range(0,mf,60):
    pos=[(data[i][t][1],data[i][t][2])for i in range(N)]
    for i in range(N):
        for j in range(i+1,N):
            dd=np.sqrt((pos[i][0]-pos[j][0])**2+(pos[i][1]-pos[j][1])**2)
            if 0<dd<md:md=dd
print(f"{N}d {dev} {t0/60:.1f}s XY({max(ax)-min(ax):.0f},{max(ay)-min(ay):.0f}) minD={md:.1f}cm")
with warnings.catch_warnings(record=True)as c:
    warnings.simplefilter('always')
    pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,show=False)
dw=[x for x in c if'distance between'in str(x.message)]
aw=[x for x in c if'completed'in str(x.message)]
print(f"dist:{len(dw)} act:{len(aw)}")
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/"2d"),FPS=25)
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/"3d"),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))
print("done")
