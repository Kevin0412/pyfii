#!/usr/bin/env python3
"""Cannon v6: 4-14s 复杂安全动作, agent模式测试"""
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
        score = md*500 - max(math.dist(starts[i],tt[i]) for i in range(N))*0.1
        if score > best_score: best_score = score; best = tt
    return best

def light(d, color, ticks):
    for tick in range(ticks):
        bright = int(100+155*math.sin(tick*math.pi/ticks))
        r = int(color[1:3],16)*bright//255; g = int(color[3:5],16)*bright//255; b = int(color[5:7],16)*bright//255
        d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}"); d.delay(100)

S=[(60,120),(180,60),(350,60),(500,160),(500,380),(350,480),(160,480)]
for i,d in enumerate(ds):
    d.X=d.x=S[i][0];d.Y=d.y=S[i][1];d.takeoff(1,110)

# 3个目标几何 (仅为排列搜索用)
geo = [
    [(S[i][0]+30*math.sin(i), S[i][1]+30*math.cos(i), 120) for i in range(N)],  # 散布呼吸
    [(280+140*math.cos(2*math.pi*i/N), 280+140*math.sin(2*math.pi*i/N), 135) for i in range(N)],  # 环
    [(80+i*120, 180, 150) if i<4 else (90+(i-3)*120, 390, 160) for i in range(N)],  # 双排
]

for i,d in enumerate(ds): d.intime(4); d.VelXY(120,240); d.VelZ(120,240)
prev = [(d.x, d.y, 110) for d in ds]
colors = ["#2255aa","#3388cc","#44aadd"]

for gi in range(3):
    targets = geo[gi] if gi==0 else best_assign(prev, geo[gi])
    
    # 阶段1: 飞到中点 (直飞自己的50%路径)
    mid = [((prev[i][0]+targets[i][0])/2, (prev[i][1]+targets[i][1])/2, (prev[i][2]+targets[i][2])/2+20*math.sin(i)) for i in range(N)]
    mids = mid
    for i,d in enumerate(ds):
        dd = math.dist((prev[i][0],prev[i][1]),(mids[i][0],mids[i][1]))
        spd = min(200, max(100, int(dd/1.2))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(mids[i][0]), cl(mids[i][1]), cz(mids[i][2]))
        light(d, colors[gi], 8); d.delay(500)
    prev_mid = mids
    
    # 阶段2: 飞到终点 (直飞)
    finals = targets
    for i,d in enumerate(ds):
        dd = math.dist((prev_mid[i][0],prev_mid[i][1]),(finals[i][0],finals[i][1]))
        spd = min(200, max(100, int(dd/1.2))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(finals[i][0]), cl(finals[i][1]), cz(finals[i][2]+20*math.sin(i)))
        light(d, colors[gi], 8); d.delay(700)
    prev = finals


# ---- 段2: 14-24s, 3几何 ----
geo2 = [
    [(80+80*i, 80+80*i, 160) for i in range(N)],  # 对角线
    [(280+150*math.cos(2*math.pi*i/N), 280+150*math.sin(2*math.pi*i/N), 170) for i in range(N)],  # 大环
    [(80,80,180),(480,80,180),(80,480,180),(480,480,180),(280,280,185),(200,200,180),(360,360,180)],  # 四角
]
colors2 = ["#cc6600","#cc8800","#ddaa00"]
for i,d in enumerate(ds): d.intime(13); d.VelXY(120,240); d.VelZ(120,240); d.delay(i*100)
for gi in range(3):
    targets = best_assign(prev, geo2[gi])
    mid = [((prev[i][0]+targets[i][0])/2, (prev[i][1]+targets[i][1])/2, (prev[i][2]+targets[i][2])/2+15*math.sin(i)) for i in range(N)]
    for i,d in enumerate(ds):
        dd = math.dist((prev[i][0],prev[i][1]),(mid[i][0],mid[i][1]))
        spd = min(200, max(100, int(dd/1.2))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(mid[i][0]), cl(mid[i][1]), cz(mid[i][2]))
        light(d, colors2[gi], 8); d.delay(500)
    for i,d in enumerate(ds):
        dd = math.dist((mid[i][0],mid[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(100, int(dd/1.2))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(targets[i][0]), cl(targets[i][1]), cz(targets[i][2]+15*math.sin(i)))
        light(d, colors2[gi], 8); d.delay(700)
    prev = targets




# ---- 段3: 24-34s 排队大转移 ----
geo3 = [
    [(160+60*i, 200+120*math.sin(i), 195) for i in range(N)],  # 对角线大扫
]
for i,d in enumerate(ds): d.intime(23); d.VelXY(180,360); d.VelZ(180,360)
# 排队错峰: 每机延迟i*500ms出发
for i,d in enumerate(ds): d.delay(i*700)
targets = best_assign(prev, geo3[0])
for i,d in enumerate(ds):
    dd = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
    spd = min(200, max(150, int(dd/3.5))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
    d.move2(cl(targets[i][0]), cl(targets[i][1]), cz(targets[i][2]+15*math.sin(i)))
    light(d, "#cc2244", 30);  # 3s灯光
prev = targets


# ---- 段4: 34-48s 数学几何美 ----
geo4 = [
    [(280+190*math.cos(2*math.pi*i/N+math.pi/6), 280+190*math.sin(2*math.pi*i/N+math.pi/6), 205) for i in range(N)],
    [(280+180*math.cos(4*math.pi*i/N), 280+180*math.sin(4*math.pi*i/N), 215) for i in range(N)],
    [(280+120*math.cos(2*math.pi*i/N), 280+120*math.sin(2*math.pi*i/N), 220) for i in range(N)],
]
colors4 = ["#ffffff","#ffddee","#ffbbdd"]
for i,d in enumerate(ds): d.intime(31); d.VelXY(150,300); d.VelZ(150,300); d.delay(i*600)
for gi in range(3):
    targets = best_assign(prev, geo4[gi])
    for i,d in enumerate(ds):
        dd = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(140, int(dd/3.0))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(targets[i][0]), cl(targets[i][1]), cz(targets[i][2]+15*math.sin(i)))
        light(d, colors4[gi], 25)
    prev = targets

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
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'2d'),FPS=25)
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'3d'),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))

# ---- 段4: 34-48s 数学几何美 ----
geo4 = [
    [(280+190*math.cos(2*math.pi*i/N+math.pi/6), 280+190*math.sin(2*math.pi*i/N+math.pi/6), 205) for i in range(N)],
    [(280+180*math.cos(4*math.pi*i/N), 280+180*math.sin(4*math.pi*i/N), 215) for i in range(N)],
    [(280+120*math.cos(2*math.pi*i/N), 280+120*math.sin(2*math.pi*i/N), 220) for i in range(N)],
]
colors4 = ["#ffffff","#ffddee","#ffbbdd"]
for i,d in enumerate(ds): d.intime(31); d.VelXY(150,300); d.VelZ(150,300); d.delay(i*600)
for gi in range(3):
    targets = best_assign(prev, geo4[gi])
    for i,d in enumerate(ds):
        dd = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(140, int(dd/3.0))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(targets[i][0]), cl(targets[i][1]), cz(targets[i][2]+15*math.sin(i)))
        light(d, colors4[gi], 25)
    prev = targets

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
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'2d'),FPS=25)
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'3d'),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))

# ---- 段4: 34-48s 数学几何美 ----
geo4 = [
    [(280+190*math.cos(2*math.pi*i/N+math.pi/6), 280+190*math.sin(2*math.pi*i/N+math.pi/6), 205) for i in range(N)],
    [(280+180*math.cos(4*math.pi*i/N), 280+180*math.sin(4*math.pi*i/N), 215) for i in range(N)],
    [(280+120*math.cos(2*math.pi*i/N), 280+120*math.sin(2*math.pi*i/N), 220) for i in range(N)],
]
colors4 = ["#ffffff","#ffddee","#ffbbdd"]
for i,d in enumerate(ds): d.intime(31); d.VelXY(150,300); d.VelZ(150,300); d.delay(i*600)
for gi in range(3):
    targets = best_assign(prev, geo4[gi])
    for i,d in enumerate(ds):
        dd = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(140, int(dd/3.0))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(targets[i][0]), cl(targets[i][1]), cz(targets[i][2]+15*math.sin(i)))
        light(d, colors4[gi], 25)
    prev = targets

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
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'2d'),FPS=25)
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'3d'),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))

# ---- 段4: 34-48s 数学几何美 ----
geo4 = [
    [(280+190*math.cos(2*math.pi*i/N+math.pi/6), 280+190*math.sin(2*math.pi*i/N+math.pi/6), 205) for i in range(N)],
    [(280+180*math.cos(4*math.pi*i/N), 280+180*math.sin(4*math.pi*i/N), 215) for i in range(N)],
    [(280+120*math.cos(2*math.pi*i/N), 280+120*math.sin(2*math.pi*i/N), 220) for i in range(N)],
]
colors4 = ["#ffffff","#ffddee","#ffbbdd"]
for i,d in enumerate(ds): d.intime(31); d.VelXY(150,300); d.VelZ(150,300); d.delay(i*600)
for gi in range(3):
    targets = best_assign(prev, geo4[gi])
    for i,d in enumerate(ds):
        dd = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(140, int(dd/3.0))); d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(targets[i][0]), cl(targets[i][1]), cz(targets[i][2]+15*math.sin(i)))
        light(d, colors4[gi], 25)
    prev = targets

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
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'2d'),FPS=25)
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'3d'),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))
print("done")
