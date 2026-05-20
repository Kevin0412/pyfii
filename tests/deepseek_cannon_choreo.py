#!/usr/bin/env python3
"""Cannon v4: 16种不同几何 + 飞行中嵌灯 + 距离调速 + 异步"""
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

def light_gradient(d, color, ticks, total=40):
    """飞行中嵌灯: 100ms正弦渐变"""
    for tick in range(ticks):
        bright = int(100+155*math.sin(tick*math.pi/total))
        r = int(color[1:3],16)*bright//255
        g = int(color[3:5],16)*bright//255
        b = int(color[5:7],16)*bright//255
        d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}"); d.delay(100)

# ====== 段1: 4-16s, 4几何 ======
geo1 = [
    [(S[i][0]+20*math.sin(i), S[i][1]+20*math.cos(i), 115+i*5) for i in range(N)],  # 呼吸
    [(280+130*math.cos(2*math.pi*i/N), 280+130*math.sin(2*math.pi*i/N), 130+25*math.sin(2*math.pi*i/N)) for i in range(N)],  # 环
    [(80+i*115, 170, 140) if i<4 else (90+(i-3)*120, 390, 155) for i in range(N)],  # 双排错位
    [(80,80,145),(480,80,155),(80,480,160),(480,480,150),(280,280,170),(200,200,145),(360,360,155)],  # 四角
]
for i,d in enumerate(ds): d.intime(4); d.VelXY(120,240); d.VelZ(120,240)
prev = [(d.x, d.y, 110) for d in ds]
for gi in range(4):
    targets = geo1[gi] if gi==0 else best_assign(prev, geo1[gi])
    for i,d in enumerate(ds):
        dist = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        v = min(200, max(150, int(dist/2.5)))  # 距离调速
        d.VelXY(v, v*2); d.VelZ(v, v*2)
        tx,ty,tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        light_gradient(d, "#2266aa" if gi<2 else "#44aadd", 15, 30)
        d.delay(1500)
    prev = targets

# ====== 段2: 16-33s, 4不同几何 ======
geo2 = [
    [(80+90*i, 80+90*i, 155) for i in range(N)],  # 对角线
    [(480-90*i, 80+90*i, 160) for i in range(N)],  # 反对角
    [(100+70*i, 240+80*math.sin(i), 165) for i in range(N)],  # 波动线
    [(80,80,170),(480,80,170),(80,480,170),(480,480,170),(280,160,180),(280,400,175),(160,280,185)],  # 十字+中
]
for i,d in enumerate(ds): d.intime(16); d.VelXY(100,200); d.VelZ(100,200); d.delay(i*120)
for gi in range(4):
    targets = best_assign(prev, geo2[gi])
    for i,d in enumerate(ds):
        dist = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        v = min(200, max(100, int(dist/3.5)))
        d.VelXY(v, v*2); d.VelZ(v, v*2)
        tx,ty,tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        light_gradient(d, "#ffbb33", 20, 35)
        d.delay(1500)
    prev = targets

# ====== 段3: 33-50s, 4几何 ======
geo3 = [
    [(280+160*math.cos(2*math.pi*i/N), 280+160*math.sin(2*math.pi*i/N), 180) for i in range(N)],  # 大环
    [(100+80*i, 440-80*i, 185) for i in range(N)],  # 反斜线
    [(180+i*65, 200+120*math.sin(i), 190) for i in range(N)],  # 之字
    [(60,60,195),(500,60,195),(60,500,195),(500,500,195),(280,280,205),(180,180,200),(380,380,200)],  # 四角内收
]
for i,d in enumerate(ds): d.intime(33); d.VelXY(130,260); d.VelZ(130,260); d.delay(i*80)
for gi in range(4):
    targets = best_assign(prev, geo3[gi])
    for i,d in enumerate(ds):
        dist = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        v = min(200, max(100, int(dist/3.5)))
        d.VelXY(v, v*2); d.VelZ(v, v*2)
        tx,ty,tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        light_gradient(d, "#ff5588", 20, 35)
        d.delay(1500)
    prev = targets

# ====== 段4: 50-67s, 4几何 ======
geo4 = [
    [(120+70*i, 120+70*i, 200) for i in range(N)],  # 对角展开
    [(440-70*i, 120+70*i, 205) for i in range(N)],  # 反斜展开
    [(280+180*math.cos(2*math.pi*i/N+0.3), 280+180*math.sin(2*math.pi*i/N+0.3), 210) for i in range(N)],  # 偏转环
    [(60,200,215),(500,200,215),(280,60,220),(280,500,215),(200,200,225),(360,360,220),(280,280,230)],  # 十字爆发
]
for i,d in enumerate(ds): d.intime(50); d.VelXY(150,300); d.VelZ(150,300); d.delay(i*80)
for gi in range(4):
    targets = best_assign(prev, geo4[gi])
    for i,d in enumerate(ds):
        dist = math.dist((prev[i][0],prev[i][1]),(targets[i][0],targets[i][1]))
        v = min(200, max(120, int(dist/3.5)))
        d.VelXY(v, v*2); d.VelZ(v, v*2)
        tx,ty,tz = targets[i]
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        light_gradient(d, "#ffffff", 20, 35)
        d.delay(1500)
    prev = targets

# 段5: 收束降落
for i,d in enumerate(ds): d.intime(67); d.VelXY(60,120); d.VelZ(60,120)
geo5 = [(280+100*math.cos(2*math.pi*i/N), 280+100*math.sin(2*math.pi*i/N), 150) for i in range(N)]
targets = best_assign(prev, geo5)
for i,d in enumerate(ds):
    tx,ty,tz = targets[i]
    d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
    light_gradient(d, "#48dbfb", 20, 40)
for i,d in enumerate(ds): d.intime(73); d.land()
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
