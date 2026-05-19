#!/usr/bin/env python3
"""DeepSeek Cannon 设计草稿
音乐: 卡农 68s 156BPM, 渐进叠加结构
草稿:
  0-16s 低能(0.25): 单机独舞S形, 其他悬停 → 安全(只有1机动)
  16-32s 中能(0.37): 三机三角对话, 其他微动 → 安全(3机三角间距>150)
  32-48s 中高(0.52): 七机六边形呼吸+中心起伏 → 安全(六边形半径140-190,邻距>120)
  48-64s 高能(0.58): 七机左右分区交叉 → 安全(左右各3机,中心1机,区间隔>200)
  64-72s 收束: 原地降落 → 安全(不交叉,各降各的)
速度规划: 段1=60/120, 段2=100/200, 段3=140/280, 段4=180/360, 段5=60/120
起始: 六边形140cm+中心, 保证初始间距>140
"""
import sys,math,os
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT/"src"))
import pyfii as pf

N=7;OUT=REPO_ROOT/"output"/"deepseek_cannon";MUSIC=str(REPO_ROOT/"cannon_in_D.mp3")
ds=[pf.Drone(0,0,pf.drone_config_6m,f"192.168.51.{51+i}") for i in range(N)]

# 六边形起始 R=140
for i,d in enumerate(ds):
    if i==6: x,y=280,280
    else:
        a=2*math.pi*i/6+math.pi/6
        x=280+140*math.cos(a);y=280+140*math.sin(a)
    d.X=d.x=int(round(x));d.Y=d.y=int(round(y))
    d.takeoff(1,110 if i!=6 else 150)

def st(t):return t*t*(3-2*t)
def i3(x):return int(round(x))

# ---- 段1: 0-16s 单机独舞 ----
for i,d in enumerate(ds):
    d.intime(4)  # d6从0s开始, 其他4s开始悬停
    d.VelXY(60,120);d.VelZ(50,100)
for stp in range(3):
    t=(stp+1)/4;s=st(t)
    for i,d in enumerate(ds):
        if i==6:  # 独舞S形
            x=280+70*math.sin(s*3*math.pi)
            y=280+70*math.cos(s*2*math.pi)
            z=140+60*math.sin(s*math.pi)
        else:
            x,y,z = d.x, d.y, 110
        if i==6:
            d.move2(i3(x),i3(y),i3(z))
            d.TurnOnAll("#4dd7ff")
            d.delay(1500)  # 独舞机有灯光delay, 其他瞬间完成
    for i,d in enumerate(ds):
        if i==6: d.TurnOffAll();d.delay(1500)



# ---- 段2: 16-32s 三角对话 ----
for i,d in enumerate(ds):
    d.intime(16);d.VelXY(100,200);d.VelZ(80,160)
for stp in range(4):
    t=(stp+1)/4;s=st(t)
    for i,d in enumerate(ds):
        if i in [1,3,5]:  # 对话组: 独立三角(中心200,380), 远离悬停机
            ang=2*math.pi*(i+1)/3+0.3*math.pi*s
            r=100+30*math.sin(s*math.pi)
            x=200+r*math.cos(ang);y=380+r*math.sin(ang)
            z=160+40*math.sin(s*math.pi+i)
            d.move2(i3(x),i3(y),i3(z))
            d.TurnOnAll("#ffdd59");d.delay(2000)
        elif i==6:  # 中心微动
            x=280+30*math.sin(s*2*math.pi);y=280+30*math.cos(s*3*math.pi)
            z=170
            d.move2(i3(x),i3(y),i3(z))
            d.TurnOnAll("#ffdd59");d.delay(2000)
        # 其他机不活动
    for i,d in enumerate(ds):
        if i in [1,3,5,6]: d.TurnOffAll();d.delay(1000)


# ---- 段3: 32-48s 六边形呼吸 ----
for i,d in enumerate(ds):
    d.intime(32);d.VelXY(140,280);d.VelZ(120,240)
for stp in range(4):
    t=(stp+1)/4;s=st(t)
    r=140+50*math.sin(s*2*math.pi)
    for i,d in enumerate(ds):
        if i<6:
            ang=2*math.pi*i/6+0.1*math.pi*s
            x=280+r*math.cos(ang);y=280+r*math.sin(ang)
        else:
            x=280;y=280
        z=150+50*math.sin(s*math.pi+i)
        d.move2(i3(x),i3(y),i3(z))
        if i<6: d.TurnOnAll("#ff6b9a");d.delay(2000)
        else: d.TurnOnAll("#ff4488");d.delay(2000)
    for i,d in enumerate(ds):
        d.TurnOffAll();d.delay(1000)
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
    msg=str(w.message);p=msg.split('s,');t=int(p[0].split()[-1])if p else 0;times[t]+=1
if times: print(f"时间:{min(times)}-{max(times)}s top3:{times.most_common(3)}")
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'2d'),FPS=25)
pf.show(data,t0,[str(MUSIC)],field=field,device=dev,max_fps=60,save=str(OUT/'3d'),FPS=25,ThreeD=True,imshow=[90,0],d=(600,450))
print("done")
