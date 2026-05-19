#!/usr/bin/env python3
"""DeepSeek Cannon v6 — 全机活动，不悬停，不绕圈
设计草稿:
  段1 0-16s: 散布呼吸(各机独立区域, 间距>120)
  段2 16-32s: 对角线交换(3对互换, d6起伏)
  段3 32-48s: 左右分区扫场(不交叉)
  段4 48-64s: 汇聚+展开
  段5 64-68s: 原地降落
速度: 段1=60/120, 段2=100/200, 段3=140/280, 段4=180/360, 段5=60/120
"""
import sys,math,os
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT/"src"))
import pyfii as pf

N=7;OUT=REPO_ROOT/"output"/"deepseek_cannon";MUSIC=str(REPO_ROOT/"cannon_in_D.mp3")
ds=[pf.Drone(0,0,pf.drone_config_6m,f"192.168.51.{51+i}") for i in range(N)]

def st(t):return t*t*(3-2*t)
def i3(x):return int(round(x))

# 散布起始 (全场分散, >130cm间距)
starts=[(60,100),(180,50),(350,50),(500,150),(500,350),(350,500),(160,500)]
for i,d in enumerate(ds):
    d.X=d.x=starts[i][0];d.Y=d.y=starts[i][1]
    d.takeoff(1,100)

# ---- 段1: 0-16s 散布呼吸,全机微动 ----
for i,d in enumerate(ds):
    d.intime(4);d.VelXY(50,100);d.VelZ(40,80)
for step in range(4):
    t=(step+1)/4;s=st(t)
    for i,d in enumerate(ds):
        r=40*math.sin(s*math.pi+i)
        x=starts[i][0]+r*math.cos(i*1.7)
        y=starts[i][1]+r*math.sin(i*1.3)
        z=110+30*math.sin(s*math.pi+i)
        d.move2(i3(x),i3(y),i3(z))
        d.TurnOnAll("#4dd7ff");d.delay(1500)
    for i,d in enumerate(ds):
        d.TurnOffAll();d.delay(1500)


# ---- 段2: 16-32s 独立微动(各机在各自区域移动) ----
for i,d in enumerate(ds):
    d.intime(16);d.VelXY(80,160);d.VelZ(60,120)
for step in range(4):
    t=(step+1)/4;s=st(t)
    for i,d in enumerate(ds):
        # 各机在各自起始位附近做中幅度运动
        r=60*math.sin(s*math.pi+i)
        x=starts[i][0]+r*math.cos(i+0.3*s)
        y=starts[i][1]+r*math.sin(i*1.7+0.3*s)
        z=130+40*math.sin(s*math.pi+i)
        d.move2(i3(x),i3(y),i3(z))
        d.TurnOnAll("#ffdd59");d.delay(2000)
    for i,d in enumerate(ds):
        d.TurnOffAll();d.delay(1000)

# ---- 段3: 32-48s 左右分区扫场 ----
for i,d in enumerate(ds):
    d.intime(32);d.VelXY(120,240);d.VelZ(100,200)
for step in range(4):
    t=(step+1)/4;s=st(t)
    for i,d in enumerate(ds):
        if i<3:  # 左区: X[60,160], Y扫
            x=80
            y=80+i*200+40*math.sin(s*2*math.pi)
        elif i<6:  # 右区: X[400,500]
            x=480
            y=80+(i-3)*200+40*math.sin(s*2*math.pi)
        else:  # 中
            x=280+80*math.sin(s*3*math.pi)
            y=280+80*math.cos(s*2*math.pi)
        z=150+40*math.sin(s*math.pi+i)
        d.move2(i3(x),i3(y),i3(z))
        d.TurnOnAll("#ff6b9a");d.delay(2000)
    for i,d in enumerate(ds):
        d.TurnOffAll();d.delay(2000)

# ---- 段4: 48-64s 汇聚+展开 ----
for i,d in enumerate(ds):
    d.intime(48);d.VelXY(160,320);d.VelZ(140,280)
for step in range(4):
    t=(step+1)/4;s=st(t)
    for i,d in enumerate(ds):
        ang=2*math.pi*i/N+0.3*math.pi*s
        r=120+100*math.sin(s*math.pi)
        x=280+r*math.cos(ang)
        y=280+r*math.sin(ang)
        z=160+70*abs(math.sin(s*2*math.pi))
        d.move2(i3(x),i3(y),i3(z))
        d.TurnOnAll("#ffffff");d.delay(2000)
    for i,d in enumerate(ds):
        d.TurnOffAll();d.delay(2000)

# ---- 段5: 64-68s 原地降落 ----
for i,d in enumerate(ds):
    d.intime(64);d.VelXY(50,100);d.VelZ(40,80)
    d.land()


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
from collections import Counter
times=Counter()
for w in dw:
    p=str(w.message).split('s,');t=int(p[0].split()[-1])if p else 0;times[t]+=1
if times:print(f"time:{times.most_common(3)}")
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'2d'),FPS=25)
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'3d'),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))
print("done")
