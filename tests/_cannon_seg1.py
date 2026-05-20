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
        score = md*500 - max(math.dist(starts[i],tt[i]) for i in range(N))*0.1
        if score > best_score:
            best_score = score
            best = tt
    return best

S=[(60,120),(180,60),(350,60),(500,160),(500,380),(350,480),(160,480)]
for i,d in enumerate(ds):
    d.X=d.x=S[i][0];d.Y=d.y=S[i][1];d.takeoff(1,110)
for i,d in enumerate(ds): d.intime(4); d.VelXY(150,300); d.VelZ(150,300)

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
    if gi == 0:
        targets = geo[gi]  # 散布呼吸直接匹配, 不搜索
    else:
        targets = best_assign(prev_pos, geo[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        dd = math.dist((prev_pos[i][0],prev_pos[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(120, int(dd/2.5)))
        d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        for tick in range(30 if gi<3 else 15):
            bright = int(100+155*math.sin(tick*math.pi/30))
            r = int(colors[gi][1:3],16)*bright//255
            g = int(colors[gi][3:5],16)*bright//255
            b = int(colors[gi][5:7],16)*bright//255
            d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}"); d.delay(100)
        if gi == 3: d.TurnOffAll()
    prev_pos = targets


# 段2: 4个安全几何
geo2 = [
    [(280+150*math.cos(2*math.pi*i/N), 280+150*math.sin(2*math.pi*i/N), 145+20*math.sin(2*math.pi*i/N)) for i in range(N)],  # 环
    [(70+115*i, 150, 155) if i<4 else (190+110*(i-3), 410, 160) for i in range(N)],  # 双排
    [(60,60,165),(500,60,165),(60,500,165),(500,500,165),(280,280,170),(200,200,165),(360,360,165)],  # 四角外
    [(280+150*math.cos(2*math.pi*i/N+math.pi/7), 280+150*math.sin(2*math.pi*i/N+math.pi/7), 150+20*math.sin(2*math.pi*i/N+math.pi/7)) for i in range(N)],  # 旋转环
]
colors2 = ["#ffbb33","#ffaa22","#ff9911","#ffdd59"]
for i,d in enumerate(ds): d.intime(16); d.VelXY(90,180); d.VelZ(90,180); d.delay(i*100)
for gi in range(4):
    targets = best_assign(prev_pos, geo2[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        dd = math.dist((prev_pos[i][0],prev_pos[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(120, int(dd/2.5)))
        d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        for tick in range(39):
            bright = int(100+155*math.sin(tick*math.pi/39))
            r = int(colors2[gi][1:3],16)*bright//255
            g = int(colors2[gi][3:5],16)*bright//255
            b = int(colors2[gi][5:7],16)*bright//255
            d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}"); d.delay(100)
    prev_pos = targets


# 段3: 4个安全几何
geo3 = [
    [(280+170*math.cos(2*math.pi*i/N), 280+170*math.sin(2*math.pi*i/N), 185) for i in range(N)],  # 大环
    [(80+115*i, 180, 190) if i<4 else (200+110*(i-3), 380, 190) for i in range(N)],  # 双排
    [(80,80,195),(480,80,195),(80,480,195),(480,480,195),(280,280,200),(180,180,195),(380,380,195)],  # 四角内
    [(280+170*math.cos(2*math.pi*i/N+math.pi/7), 280+170*math.sin(2*math.pi*i/N+math.pi/7), 200) for i in range(N)],  # 旋转环
]
colors3 = ["#ff5588","#ff4477","#ff3366","#ff2266"]
for i,d in enumerate(ds): d.intime(33); d.VelXY(150,300); d.VelZ(150,300); d.delay(i*80)
for gi in range(4):
    targets = best_assign(prev_pos, geo3[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        dd = math.dist((prev_pos[i][0],prev_pos[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(120, int(dd/2.5)))
        d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        for tick in range(39):
            bright = int(100+155*math.sin(tick*math.pi/39))
            r = int(colors3[gi][1:3],16)*bright//255
            g = int(colors3[gi][3:5],16)*bright//255
            b = int(colors3[gi][5:7],16)*bright//255
            d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}"); d.delay(100)
    prev_pos = targets


# 段4: 4个几何
geo4 = [
    [(280+190*math.cos(2*math.pi*i/N), 280+190*math.sin(2*math.pi*i/N), 205) for i in range(N)],  # 大环
    [(100+110*i, 200, 210) if i<4 else (210+105*(i-3), 360, 210) for i in range(N)],  # 双排
    [(60,60,215),(500,60,215),(60,500,215),(500,500,215),(280,280,220),(200,200,215),(360,360,215)],  # 四角全
    [(280+190*math.cos(2*math.pi*i/N+math.pi/7), 280+190*math.sin(2*math.pi*i/N+math.pi/7), 220) for i in range(N)],  # 旋转环
]
colors4 = ["#ffffff","#ffeeee","#ffdddd","#ffcccc"]
for i,d in enumerate(ds): d.intime(50); d.VelXY(160,320); d.VelZ(160,320); d.delay(i*80)
for gi in range(4):
    targets = best_assign(prev_pos, geo4[gi])
    for i,d in enumerate(ds):
        tx, ty, tz = targets[i]
        dd = math.dist((prev_pos[i][0],prev_pos[i][1]),(targets[i][0],targets[i][1]))
        spd = min(200, max(120, int(dd/2.5)))
        d.VelXY(spd, spd*2); d.VelZ(spd, spd*2)
        d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
        for tick in range(39):
            bright = int(100+155*math.sin(tick*math.pi/39))
            r = int(colors4[gi][1:3],16)*bright//255
            g = int(colors4[gi][3:5],16)*bright//255
            b = int(colors4[gi][5:7],16)*bright//255
            d.TurnOnAll(f"#{r:02x}{g:02x}{b:02x}"); d.delay(100)
    prev_pos = targets

# 段5: 收束降落
for i,d in enumerate(ds): d.intime(67); d.VelXY(60,120); d.VelZ(60,120)
geo5 = [(280+100*math.cos(2*math.pi*i/N), 280+100*math.sin(2*math.pi*i/N), 150) for i in range(N)]
targets = best_assign(prev_pos, geo5)
for i,d in enumerate(ds):
    tx, ty, tz = targets[i]
    d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
    d.TurnOnAll("#48dbfb"); d.delay(2000); d.TurnOffAll(); d.delay(2000)
for i,d in enumerate(ds):
    d.intime(73); d.land()

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

geo1 = [  # 段1: 呼吸 → 环 → 双排 → 四角
    [(S[i][0]+20*math.sin(i), S[i][1]+20*math.cos(i), 115) for i in range(N)],
    [(280+130*math.cos(2*math.pi*i/N), 280+130*math.sin(2*math.pi*i/N), 130) for i in range(N)],
    [(80+i*115, 170, 145) if i<4 else (90+(i-3)*120, 390, 155) for i in range(N)],
    [(80,80,145),(480,80,155),(80,480,160),(480,480,150),(280,280,170),(200,200,145),(360,360,155)],
]
geo2 = [  # 段2: 对角线 → 反对角 → 水平梳 → 外围框
    [(80+90*i, 80+90*i, 155) for i in range(N)],
    [(500-90*i, 80+90*i, 160) for i in range(N)],
    [(280,60,165),(120,280,165),(440,280,165),(280,500,165),(200,200,175),(360,200,170),(280,280,180)],
    [(60,60,170),(500,60,170),(60,500,170),(500,500,170),(280,280,180),(140,280,170),(420,280,170)],
    [(100,280,172),(280,100,172),(460,280,172),(280,460,172),(200,200,175),(360,360,175),(280,280,178)],
    [(80,80,175),(280,120,175),(480,80,175),(280,440,175),(80,480,175),(480,480,175),(280,280,180)],
]
geo3 = [  # 段3: 大环 → 反斜线 → 交错三角 → 内收框
    [(280+170*math.cos(2*math.pi*i/N), 280+170*math.sin(2*math.pi*i/N), 180) for i in range(N)],
    [(120,120,185),(380,100,185),(200,400,185),(460,350,185),(100,280,190),(400,200,190),(280,280,195)],
    [(80,80,190),(80,180,190),(80,280,190),(80,380,190),(80,480,190),(280,480,195),(280,280,200)],
    [(80,80,195),(480,80,195),(80,480,195),(480,480,195),(280,280,205),(180,180,200),(380,380,200)],
]
geo4 = [  # 段4: 偏转环 → 对角梳 → 放射线 → 爆发点
    [(280+180*math.cos(2*math.pi*i/N+0.5), 280+180*math.sin(2*math.pi*i/N+0.5), 200) for i in range(N)],
    [(80+70*i, 120+150*(i%2), 205) for i in range(N)],
    [(80,280,210),(160,160,210),(280,100,215),(400,160,210),(480,280,210),(280,280,220),(200,380,210)],
    [(100,100,215),(460,100,215),(100,460,215),(460,460,215),(280,280,225),(180,280,220),(380,280,220)],
    [(280,280,220),(200,150,220),(360,150,220),(200,410,220),(360,410,220),(120,280,225),(440,280,225)],
]
# 段5: 收束降落
for i,d in enumerate(ds): d.intime(67); d.VelXY(60,120); d.VelZ(60,120)
geo5 = [(280+100*math.cos(2*math.pi*i/N), 280+100*math.sin(2*math.pi*i/N), 150) for i in range(N)]
targets = best_assign(prev_pos, geo5)
for i,d in enumerate(ds):
    tx, ty, tz = targets[i]
    d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
    d.TurnOnAll("#48dbfb"); d.delay(2000); d.TurnOffAll(); d.delay(2000)
for i,d in enumerate(ds):
    d.intime(73); d.land()

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
geo1 = [
    [(S[i][0]+20*math.sin(i), S[i][1]+20*math.cos(i), 115+i*5) for i in range(N)],
    [(280+130*math.cos(2*math.pi*i/N), 280+130*math.sin(2*math.pi*i/N), 130+25*math.sin(2*math.pi*i/N)) for i in range(N)],
    [(80+i*115, 170, 140) if i<4 else (90+(i-3)*120, 390, 155) for i in range(N)],
    [(80,80,145),(480,80,155),(80,480,160),(480,480,150),(280,280,170),(200,200,145),(360,360,155)],
]
geo2 = [
    [(80+90*i, 80+90*i, 155) for i in range(N)],
    [(480-90*i, 80+90*i, 160) for i in range(N)],
    [(100+70*i, 240+80*math.sin(i), 165) for i in range(N)],
    [(80,80,170),(480,80,170),(80,480,170),(480,480,170),(280,160,180),(280,400,175),(160,280,185)],
]
geo3 = [
    [(280+160*math.cos(2*math.pi*i/N), 280+160*math.sin(2*math.pi*i/N), 180) for i in range(N)],
    [(100+80*i, 440-80*i, 185) for i in range(N)],
    [(180+i*65, 200+120*math.sin(i), 190) for i in range(N)],
    [(60,60,195),(500,60,195),(60,500,195),(500,500,195),(280,280,205),(180,180,200),(380,380,200)],
]
geo4 = [
    [(120+70*i, 120+70*i, 200) for i in range(N)],
    [(440-70*i, 120+70*i, 205) for i in range(N)],
    [(280+180*math.cos(2*math.pi*i/N+0.3), 280+180*math.sin(2*math.pi*i/N+0.3), 210) for i in range(N)],
    [(60,200,215),(500,200,215),(280,60,220),(280,500,215),(200,200,225),(360,360,220),(280,280,230)],
]
# 段5: 收束降落
for i,d in enumerate(ds): d.intime(67); d.VelXY(60,120); d.VelZ(60,120)
geo5 = [(280+100*math.cos(2*math.pi*i/N), 280+100*math.sin(2*math.pi*i/N), 150) for i in range(N)]
targets = best_assign(prev_pos, geo5)
for i,d in enumerate(ds):
    tx, ty, tz = targets[i]
    d.move2(cl(tx), cl(ty), cz(tz+20*math.sin(i)))
    d.TurnOnAll("#48dbfb"); d.delay(2000); d.TurnOffAll(); d.delay(2000)
for i,d in enumerate(ds):
    d.intime(73); d.land()

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
