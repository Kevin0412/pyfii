import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf
import numpy as np
import cmath
from function import *
   
'''创建无人机'''
d1=pf.Drone()
d2=pf.Drone()
d3=pf.Drone()
d4=pf.Drone()
d5=pf.Drone()
d6=pf.Drone()
d7=pf.Drone()
ds=[d1,d2,d3,d4,d5,d6,d7]#无人机列表

'''起飞
startTime = 0s
endTime = 7s
'''
leds=[[1,0,0],[1,1,0],[0,1,0],[0,1,1],[0,0,1],[1,0,1]]
n=0
for d in ds:
    n+=1
    if n==7:
        d.X = d.x = 280
        d.Y = d.y = 280
        d.takeoff(1,120)
        d.intime(4)
        deng=0
        for x in range(163,292,43):
            move2(d,(280,280,x),1000)
            for a in range(10):
                d.TurnOnAll(rgb2str(23+(deng*10+a)*8,23+(deng*10+a)*8,23+(deng*10+a)*8))
                d.delay(100)
            deng+=1
    else:
        d.X = d.x = int(280+(E**(n/3*PI*1j)).real*70+0.5)
        d.Y = d.y = int(280+(E**(n/3*PI*1j)).imag*70+0.5)
        d.takeoff(1,90)
        d.intime(4)
        move2(d,(280+(E**(n/3*PI*1j)).real*100,280+(E**(n/3*PI*1j)).imag*100,165),1000)
        for a in range(10):
            d.TurnOnAll(rgb2str((23+a*8)*leds[n-1][0],(23+a*8)*leds[n-1][1],(23+a*8)*leds[n-1][2]))
            d.delay(100)
        move2(d,(280+(E**(n/3*PI*1j)).real*130,280+(E**(n/3*PI*1j)).imag*130,190),1000)
        for a in range(10,20):
            d.TurnOnAll(rgb2str((23+a*8)*leds[n-1][0],(23+a*8)*leds[n-1][1],(23+a*8)*leds[n-1][2]))
            d.delay(100)
        move2(d,(280+(E**(n/3*PI*1j)).real*160,280+(E**(n/3*PI*1j)).imag*160,165),1000)
        for a in range(20,30):
            d.TurnOnAll(rgb2str((23+a*8)*leds[n-1][0],(23+a*8)*leds[n-1][1],(23+a*8)*leds[n-1][2]))
            d.delay(100)
        
'''起飞->利萨如
startTime = 7s
endTime = 10s
'''
leds=[]
for a in range(60):
    leds.append([int(160+95.5*np.sin(2*a/60*2*np.pi)),int(160+95.5*np.sin(3*a/60*2*np.pi)),int(160+95.5*np.sin(4*a/60*2*np.pi+np.pi/2))])
dleds=[[0,1,2],[0,2,1],[1,0,2],[],[1,2,0],[2,0,1],[2,1,0]]  
li=[]
for a in range(24):
    li.append((280+320/3**0.5*np.sin(2*a/24*2*np.pi),280+320/3**0.5*np.sin(3*a/24*2*np.pi),165+128/3**0.5*np.sin(4*a/24*2*np.pi+np.pi/2)))
li1=[8,20,0,12,0,4,16]
li2=[1,-1,-1,0,1,1,-1]
li3=[-80,0,-80,0,80,0,80]
n=0
for d in [d4,d3,d2,d7,d1,d6,d5]:
    if n==0:
        d.intime(7)
        move2(d,(d.x-160,d.y,d.z),1500)
        d.delay(1500)
        move2(d,(li[li1[n]][0]+li3[n],li[li1[n]][1],li[li1[n]][2]),1500)
    elif n==6:
        d.intime(7)
        move2(d,(d.x+160,d.y,d.z),1500)
        d.delay(1500)
        move2(d,(li[li1[n]][0]+li3[n],li[li1[n]][1],li[li1[n]][2]),1500)
    elif n==3:
        d.intime(7)
        move2(d,(d.x,d.y-80*3**0.5,d.z),1500)
        d.delay(1500) 
        b=0
        for a in [0,1,2,4,5,6]:
            b+=li[li1[a]][2]/6
        move2(d,(280,280,b),1500)
    else:
        d.intime(7)
        d.delay(1500)
        move2(d,(li[li1[n]][0]+li3[n],li[li1[n]][1],li[li1[n]][2]),1500)
    n+=1

'''利萨如
startTime = 10s
endTime = 16s
'''
n=0
for d in [d4,d3,d2,d7,d1,d6,d5]:
    d.intime(10)
    for m in range(1,5):
        if n!=3:
            move2(d,(li[li1[n]+li2[n]*m][0]+li3[n],li[li1[n]+li2[n]*m][1],li[li1[n]+li2[n]*m][2]),1500)
            for l in range(15):
                d.TurnOnAll(rgb2str(leds[(m-1)*15+l][dleds[n][0]], leds[(m-1)*15+l][dleds[n][1]],leds[(m-1)*15+l][dleds[n][2]]))
                d.delay(100)
        else:
            d.TurnOnAll(['#ff0000','#00ff00','#0000ff','#ffffff'][m-1])
            d.delay(1500)
    n+=1

'''斜对称1
startTime = 16s
endTime = 21s
'''
n=0
for d in [d2,d6,d4,d7,d5,d3,d1]:
    d.intime(16)
    move2(d,(40+80*n,40+80*n,248-abs(3-n)*40),2000)
    for a in range(20):
        d.TurnOnAll(rgb2str(int(160+95.5*np.sin(3*2*np.pi/45*a)),int(160+95.5*np.sin(4*2*np.pi/45*a)),int(160+95.5*np.sin(2*2*np.pi/45*a))))
        d.delay(100)
    if n in [0,2]:
        move2(d,(d.x+160*(1-n),d.y,d.z),1500)
    elif n in [4,6]:
        move2(d,(d.x,d.y+160*(5-n),d.z),1500)
    elif n==3:
        move2(d,(d.x,d.y,168),1500)
    for a in range(20,35):
        d.TurnOnAll(rgb2str(int(160+95.5*np.sin(3*2*np.pi/45*a)),int(160+95.5*np.sin(4*2*np.pi/45*a)),int(160+95.5*np.sin(2*2*np.pi/45*a))))
        d.delay(100)
    if n!=3:
        move2(d,(d.x+80*abs(3-n)/(3-n),d.y+80*abs(3-n)/(3-n),88+abs(3-n)*40),1500)
    for a in range(35,45):
        d.TurnOnAll(rgb2str(int(160+95.5*np.sin(3*2*np.pi/45*a)),int(160+95.5*np.sin(4*2*np.pi/45*a)),int(160+95.5*np.sin(2*2*np.pi/45*a))))
        d.delay(100)
    n+=1

'''斜对称2
startTime = 21s
endTime = 29s
dt = 8s
'''
n=0
for d in [d2,d1,d6,d3,d4,d5,d7]:
    n+=1
    d.intime(21)
    if n in [3,4]:
        move2(d,(d.x,d.y+160*2*(3.5-n),168+40*(3.5-n)),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15+16*a,15,15))
            d.delay(100)
    elif n in [1,2]:
        move2(d,(480+80*(n-1.5),80+80*(n-1.5),168+20*(n-1.5)),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15+16*a,255,15))
            d.delay(100)
    elif n in [5,6]:
        move2(d,(80+80*(n-5.5),480+80*(n-5.5),168+20*(n-5.5)),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15+16*a,15,255))
            d.delay(100)

    if n in [1,5]:
        move2(d,(d.x+80,d.y,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(255,15+16*a,15))
            d.delay(100)
    elif n in [2,6]:
        move2(d,(d.x-80,d.y,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(255,255-16*a,15))
            d.delay(100)
    elif n in [3,4]:
        move2(d,(d.x+160*2*(3.5-n),d.y,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(255,15+16*a,255))
            d.delay(100)

    if n in [1,5]:
        move2(d,(d.x,d.y+80,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(255-16*a,255,15))
            d.delay(100)
    elif n in [2,6]:
        move2(d,(d.x,d.y-80,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(255-16*a,15,15))
            d.delay(100)
    elif n in [3,4]:
        move2(d,(d.x,d.y+160*2*(n-3.5),d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(255-16*a,255,255))
            d.delay(100)

    if n in [1,5]:
        move2(d,(d.x-80,d.y,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15,255,15+16*a))
            d.delay(100)
    elif n in [2,6]:
        move2(d,(d.x+80,d.y,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15,15,15+16*a))
            d.delay(100)
    elif n in [3,4]:
        move2(d,(d.x+160*2*(n-3.5),d.y,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15,255,255-16*a))
            d.delay(100)

    if n in [1,5]:
        move2(d,(d.x,d.y-80,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15,255-16*a,255))
            d.delay(100)
    elif n in [2,6]:
        move2(d,(d.x,d.y+80,d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15,15+16*a,255))
            d.delay(100)
    elif n in [3,4]:
        move2(d,(d.x,d.y+160*2*(3.5-n),d.z),1600)
        for a in range(16):
            d.TurnOnAll(rgb2str(15,255-16*a,15))
            d.delay(100)
    
    if n==7:
        for a in range(80):
            d.TurnOnAll(rgb2str(int(128+127.5*np.sin(a*np.pi*2/16)),int(128+127.5*np.sin(a*np.pi*2/16+2*np.pi/3)),int(128+127.5*np.sin(a*np.pi*2/16+2*np.pi*2/3))))
            d.delay(100)

'''平移旋转
startTime = 29s
endTime = 37s
dt = 8s

group1 = {7, 6, 3, 1}
group2 = {2, 4, 5}
'''
# 飞机编号对应组编号, -1代表飞机在中心
# n2g1 = {7:-1, 3:0, 6:1, 1:2}    # n to group 2
# n2g2 = {2:0, 4:1, 5:2}
n2g1 = {6:-1, 7:0, 5:1, 3:2}    # n to group 2 # changed without chash
n2g2 = {4:0, 2:1, 1:2}
g1, g2 = [6, 7, 5, 3], [4, 2, 1]     # group 1
R = 100 # 旋转半径
for d in ds:
    d.intime(29)
for step in range(4):   # 动作的步骤
    delayTime = 3000 if step==0 else(1000 if step==3 else 1500)
    # delayTime = 800 if step==0 and n==1 else delayTime
    if step == 0:
        g1c = [0.7*N, 0.7*N]    # center of group 1
        g2l = [0.2*N, 0.2*N]    # left of group 2
    elif step == 1:
        g1c = [0.3*N, 0.7*N]    # center of group 1
        g2l = [0.2*N, 0.2*N]    # left of group 2
    elif step == 2:
        g1c = [0.5*N, 0.7*N]    # center of group 1
        g2l = [0.2*N, 0.2*N]    # left of group 2
    for d, n in zip(ds, range(7)):
        if n+1 in g1:
            gn = n2g1[n+1]
            if gn == -1:
                move2autoz(d,(g1c[0], g1c[1]), delayTime)
                d.TurnOnAll('#ffff00')
            else:
                theta = 2/3*PI*gn+PI/3*step if step!=3 else 2/3*PI*gn+2.5/3*PI
                rotateV = E**(theta*1j)     # 旋转的向量
                move2autoz(d,(g1c[0]+R*rotateV.real, g1c[1]+R*rotateV.imag), delayTime)
                d.TurnOnAll('#0000ff')
        if n+1 in g2:
            gn = n2g2[n+1]
            offsetV = [70*gn, 0]
            move2autoz(d,(g2l[0]+offsetV[0], g2l[1]+offsetV[1]), delayTime)
            d.TurnOffAll()
        d.delay(delayTime)
        if step==3:
            d.TurnOffAll()

'''新闻联播
startTime = 37s
endTime = 45s
dt = 8s
'''
for d in ds:
    d.intime(37)
g1c = [0.5*N, 0.6*N]    # center of group 1
R = 70
for d, n in zip(ds, range(7)):
    if n+1 in g1:
        gn = n2g1[n+1]
        if gn == -1:
            move2(d,(g1c[0], g1c[1], 200), 6000)
            d.TurnOnAll('#ffff00')
            d.delay(6000)
        else:
            for step in range(12):
                # start angle = 2/3*PI*gn+2.5/3*PI
                theta = 2/3*PI*gn+PI/6*step+2.5/3*PI
                rotateV = E**(theta*1j)     # 旋转的向量
                move2autoz(d,(g1c[0]+R*rotateV.real, g1c[1]+R*rotateV.imag), 6000/10)
                t = step/11
                d.TurnOnAll('#ffffff')
                d.delay(6000/10)
        d.TurnOffAll()
    if n+1 in g2:
        gn = n2g2[n+1]
        L = 50
        if gn==0:
            d.TurnOffAll()
            move2(d,(L, N-L, 250), 3000)
            d.delay(3000)
            d.TurnOnAll(RED)
            move2(d,(N-L, N-L, 80), 3000)
            d.delay(3000)
        elif gn==1:
            d.TurnOffAll()
            move2(d,(L, L, 80), 1000)
            d.delay(1000)
            d.TurnOnAll(BLUE)
            move2(d,(N-L, L, 250), 3000)
            d.delay(3000)
        elif gn==2:
            d.TurnOffAll()
            move2(d,(N-L, 2*L, 80), 2000)
            d.delay(2000)
            d.TurnOnAll(GREEN)
            move2(d,(L, 2*L, 250), 3000)
            d.delay(3000)
        d.TurnOffAll()
'''三维旋转
startTime = 45s
endTime = 54s
dt = 9s
'''
dH = 20
baseH = 160
center = N/2+N/2*1j
R = 100
dHs = [dH, 2*dH, dH, -dH, -2*dH, -dH]
# n2gn = [None, 0, 1, 2, 5, 3, 4, -1]   #n to group number
# gn2n = {0:4, 1:7, 2:5, 3:1, 4:2, 5:3, -1:6}
n2gn = {1:3, 2:4, 3:5, 4:0, 5:2, 6:-1, 7:1}
rotateVs = [R*E**(ang2rad(30+60*n)*1j) for n in range(6)]      # rotating vectors
for d in ds:
    d.intime(45)
for step in range(4):
    for d, n in zip(ds, range(7)):
        gn = n2gn[n+1]
        if gn==-1:
            d.TurnOnAll(RED)
            move2(d, (center.real, center.imag, baseH), 2000)
        else:
            clrs = ['#00aaff', '#88ff77', '#d077ff', '#ff9c52']
            iv, ih = (gn+step)%6, (gn+2*step)%6   # index of vector, index of height
            pos = center+rotateVs[iv]           # position
            move2(d, (pos.real, pos.imag, baseH+dHs[ih]), 2000)
            d.TurnOnAll(clrs[step])
        for a in range(20):
            d.TurnOnAll(rgb2str(int(160+95.5*np.sin(3*2*np.pi/20*a)),int(160+95.5*np.sin(4*2*np.pi/20*a)),int(160+95.5*np.sin(2*2*np.pi/20*a))))
            d.delay(100)
'''镰刀
startTime = 54s
endTime = 59s
dt = 7s
'''
# n2sg = [None, 7, 5, 4, 6, 2, 1, 3]  # n to symbol group 符号组 指镰锤
n2sg = [None, 2, 1, 0, 6, 3, 5, 4]  # n to symbol group 符号组 指镰锤 # changed without chash
pointsLian = [[0, 3], [2, 2], [3, 0], [2, -2], [0, -3], [-2, -2], [-3, -4]]
Scale = N/2/5
for d in ds:
    d.intime(54)
for d, n in zip(ds, range(7)):
    gn = n2sg[n+1]
    d.TurnOnAll(RED)
    move2autoz(d,(Scale*pointsLian[gn][0]+N/2, Scale*pointsLian[gn][1]+N/2), 1000)
    d.delay(5000)
    d.TurnOffAll()

'''锤子
startTime = 59s
endTime = 64s
dt = 7s
'''
pointsChui = [[-1.5, 2.5], [0, 2], [-1, 1], [1, -1], [3, -3], [-2, 0], [-3, 1]]
Scale = N/2/3.5
for d in ds:
    d.intime(59)
for d, n in zip(ds, range(7)):
    gn = n2sg[n+1]
    d.TurnOnAll(YELLOW)
    move2autoz(d,(Scale*pointsChui[gn][0]+N/2, Scale*pointsChui[gn][1]+N/2), 1000)
    d.delay(4000)

for d in ds:
    d.intime(64)
    d.land()
    d.end()

    
        
name = 'output/大闹天宫'
F=pf.Fii(name,ds,music='云宫迅音_缩混3.mp3')
F.save()
data, t0, music = pf.read_fii(name,fps=60)
pf.show(data, t0, music, save='dntg20220730', FPS=60,max_fps=60,skin=1)
pf.show(data,t0,music,save='dntg20220730_3D',ThreeD=True,imshow=[90,3],d=(600,500),FPS=60,max_fps=60)


