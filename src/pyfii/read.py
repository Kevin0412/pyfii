import os
import sys
import time
import warnings
from joblib.externals.loky import ProcessPoolExecutor
from .fii_parser import FiiParseError, parse_fii
from .xml_parser import XmlParseError, collect_points, parse_web_code

def str2bgr(color):
    return (int(color[5:7],16),int(color[3:5],16),int(color[1:3],16))

def _read_xml_points_legacy(data):
    data=data.split('\n')
    xml=[]
    n=0
    for d in data:
        n+=1
        #print(d.split('  ')[-1],str(len(d.split('  '))))
        xml.append(d.split('  ')[-1])
    points={}
    for k in range(len(xml)):
        if xml[k][1:6]=='block':
            if xml[k].split('"')[1][0:13]=='Goertek_Point':
                points[xml[k+1][19:-8]]=[int(xml[k+2][16:-8]),int(xml[k+3][16:-8]),int(xml[k+4][16:-8])]
    return points

def _read_xml_legacy(data,fii=[],time=0,x=0,y=0,z=0,vel=0,acc=0,w=0,points={}):#格式转换,xml指令转换为python指令
    data=data.split('\n')
    xml=[]
    lenxml=[]
    n=0
    for d in data:
        n+=1
        #print(d.split('  ')[-1],str(len(d.split('  '))))
        xml.append(d.split('  ')[-1])
        lenxml.append(len(d.split('  ')))
    dots=[]
    warns=[]
    end=time
    for k in range(len(xml)):
        if xml[k][1:6]=='block':
            #print(xml[k].split('"')[1])
            if xml[k].split('"')[1][0:14]=='block_inittime':
                if time>int(xml[k+1][19:21])*60000+int(xml[k+1][22:24])*1000:
                    raise Warning("Block inittime error.时间开始模块摆放错误")
                time=int(xml[k+1][19:21])*60000+int(xml[k+1][22:24])*1000
                #print(time)
            elif xml[k].split('"')[1][0:11]=='block_delay':
                time+=float(xml[k+2][19:-8])
                #print(time)
            elif xml[k].split('"')[1][0:19]=='Goertek_MoveToCoord':
                if vel==0:
                    vel=60
                    warns.append("Velcity is not defined.Default 60cm/s.速度未定义。默认60cm/s。")
                if acc==0:
                    acc=100
                    warns.append("Acceleration is not defined.Default 100cm/s^2.加速度未定义。默认100cm/s^2。")
                x=float(xml[k+1][16:-8])
                y=float(xml[k+2][16:-8])
                #print(time,x,y,int(xml[k+3][16:-8]))
                dots.append([time,x,y,float(xml[k+3][16:-8]),vel,acc,"move2"])
                end=max(time,end)
            elif xml[k].split('"')[1][0:13]=='Goertek_Start':
                if len(fii)==0:
                    x=float(xml[k].split('"')[3])
                    y=float(xml[k].split('"')[5])
                else:
                    x=fii[0]
                    y=fii[1]
                #print(time,x,y,0)
                dots.append([time,x,y,0,200,400,"move2"])
                end=max(time,end)
            elif xml[k].split('"')[1][0:15]=='Goertek_TakeOff':
                #print(time,x,y,int(xml[k+1][18:-8]))
                dots.append([time,x,y,float(xml[k+1][18:-8]),200,400,"move2"])
                end=max(time,end)
            elif xml[k].split('"')[1][0:12]=='Goertek_Land':
                #print(time,x,y,0)
                dots.append([time,"land"])
                end=max(time,end)
            elif xml[k].split('"')[1][0:23]=='Goertek_HorizontalSpeed':
                vel=float(xml[k+1][17:-8])
                acc=float(xml[k+2][17:-8])
            elif xml[k].split('"')[1][0:13]=='Goertek_Point':
                points[xml[k+1][19:-8]]=[float(xml[k+2][16:-8]),float(xml[k+3][16:-8]),float(xml[k+4][16:-8])]
            elif xml[k].split('"')[1][0:19]=='Goertek_MoveToPoint':
                if vel==0:
                    vel=60
                    warns.append("Velcity is not defined.Default 60cm/s.速度未定义。默认60cm/s。")
                if acc==0:
                    acc=100
                    warns.append("Acceleration is not defined.Default 100cm/s^2.加速度未定义。默认100cm/s^2。")
                x=points[xml[k+1][20:-8]][0]
                y=points[xml[k+1][20:-8]][1]
                dots.append([time,x,y,points[xml[k+1][20:-8]][2],vel,acc,"move2"])
                end=max(time,end)
            elif xml[k].split('"')[1][0:15]=='controls_repeat':
                newxml=''
                for g in range(k+3,len(lenxml)):
                    if lenxml[g]==lenxml[k+1]:
                        break
                    newxml+='  '*lenxml[g]+xml[g]
                    newxml+='\n'
                #print(newxml)
                if int(xml[k+1][20:-8])!=1:
                    repeat=_read_xml_legacy(newxml*(int(xml[k+1][20:-8])-1),[],time,x,y,z,vel,acc,w,points)
                    #print(repeat[0])
                    for dot in repeat[0]:
                        dots.append(dot)
                    for warn in repeat[1]:
                        warns.append(warn)
                    time=repeat[2]
                    end=repeat[3]
            elif xml[k].split('"')[1][0:12]=='Goertek_Move':
                if vel==0:
                    vel=60
                    warns.append("Velcity is not defined.Default 60cm/s.速度未定义。默认60cm/s。")
                if acc==0:
                    acc=100
                    warns.append("Acceleration is not defined.Default 100cm/s^2.加速度未定义。默认100cm/s^2。")
                x=float(xml[k+1][16:-8])
                y=float(xml[k+2][16:-8])
                dots.append([time,x,y,float(xml[k+3][16:-8]),vel,acc,"move"])
                end=max(time,end)
                #raise Warning("Goertek_Move is not recommended.方向移动不建议使用。")
            elif xml[k].split('"')[1][0:14]=='Goertek_TurnTo':
                if w==0:
                    w=60
                    warns.append("Arate is not defined.Default 60°/s.角速度未定义。默认60°/s。")
                if xml[k+1][28]=='l':
                    angle=float(xml[k+2][20:-8])
                    dots.append([time,angle,w,"turn2"])
                    end=max(time,end)
                elif xml[k+1][28]=='r':
                    angle=-float(xml[k+2][20:-8])
                    dots.append([time,angle,w,"turn2"])
                    end=max(time,end)
                #print(angle)
            elif xml[k].split('"')[1][0:12]=='Goertek_Turn':
                if w==0:
                    w=60
                    warns.append("Arate is not defined.Default 60°/s.角速度未定义。默认60°/s。")
                if xml[k+1][28]=='l':
                    angle=float(xml[k+2][20:-8])
                elif xml[k+1][28]=='r':
                    angle=-float(xml[k+2][20:-8])
                dots.append([time,angle,w,"turn"])
                end=max(time,end)
                #print(angle)
            elif xml[k].split('"')[1][0:23]=='Goertek_AngularVelocity':
                w=float(xml[k+1][16:-8])
                #print(w)
            elif "Goertek_LEDTurnOnAllSingleColor" in xml[k]:
                color = str2bgr(xml[k+1].split('>')[1].split('<')[0])
                dots.append([time, color, 'TurnOnAllSingleColor'])
                end=max(time,end)
            elif "Goertek_LEDTurnOffAll" in xml[k]:
                dots.append([time,'TurnOffAll'])
                end=max(time,end)
    return(dots,warns,time,end)


def read_xml_points(data):
    """Read named points with the tree parser, falling back for broken XML."""
    try:
        return collect_points(data)
    except XmlParseError as error:
        warnings.warn(
            f"Tree XML point parser failed ({error}); using the legacy parser.",
            RuntimeWarning,
            stacklevel=2,
        )
        return _read_xml_points_legacy(data)


def read_xml(data,fii=[],time=0,x=0,y=0,z=0,vel=0,acc=0,w=0,points={}):
    """Compile action XML with the tree parser and retain legacy fallback."""
    # Non-zero interpreter state belongs to the legacy recursive API.  Normal
    # project reads always start from zero and use the tree parser below.
    if any((time, x, y, z, vel, acc, w)):
        return _read_xml_legacy(data, fii, time, x, y, z, vel, acc, w, points)

    start_position = fii if len(fii) >= 2 else None
    try:
        return parse_web_code(
            data,
            start_position=start_position,
            points=points,
        ).as_legacy_tuple()
    except XmlParseError as error:
        warnings.warn(
            f"Tree XML parser failed ({error}); using the legacy parser.",
            RuntimeWarning,
            stacklevel=2,
        )
        return _read_xml_legacy(data, fii, time, x, y, z, vel, acc, w, points)

def dots2angle(dots,warns,end,fps=200):#将指令转化为转圈动作
    time=0
    a=0
    w=60
    angle=0
    angles=[]
    k=0
    k1=0
    while(True):
        for n in range(len(dots)):
            if time-dots[n][0]>0 and dots[n][-1] in ['turn2','turn','turned']:
                k1=n
        k=k1
        if dots[k][-1]=='turn':
            angle=a+dots[k][1]
            w=dots[k][2]
            dots[k][-1]='turned'
        elif dots[k][-1]=='turn2':
            angle=dots[k][1]%360
            a=a%360
            w=dots[k][2]
            if a-angle>180:
                a-=360
            elif angle-a>180:
                angle-=360
        w1=w/fps
        if abs(a-angle)>w1:
            a+=(angle-a)/abs(angle-a)*w1
        else:
            a=angle
        angles.append((time,float(a)))
        if time>end:
            break
        time+=1000/fps
    return(angles)

def dots2led(dots,warns,end,fps=200):#将指令转化为灯光
    time=0
    led=(-1,-1,-1)
    leds=[]
    k=0
    k1=0
    while(True):
        for n in range(len(dots)):
            if time-dots[n][0]>0 and dots[n][-1] in ['TurnOnAllSingleColor','TurnOffAll']:
                k1=n
        k=k1
        if dots[k][-1]=='TurnOnAllSingleColor':
            led=dots[k][1]
        elif dots[k][-1]=='TurnOffAll':
            led=(-1,-1,-1)
        leds.append((time,led))
        if time>end:
            break
        time+=1000/fps
    return(leds)


def dots2line(file,fii=[],fps=200,points={},ignore_acc=False):#将指令转换为飞行轨迹
    dots,warns,time,end=read_xml(file,fii,points=points)
    '''for dot in dots:
        print(dot)
    #print(dots,len(dots))
    #time.sleep(1000)'''
    angles=dots2angle(dots,warns,end,fps)
    leds=dots2led(dots,warns,end,fps)
    '''for a in angles:
        print(a)'''
    x=float(dots[0][1])
    y=float(dots[0][2])
    z=float(dots[0][3])
    time=0
    #v=0
    lines=[]
    a=0#0不加速,1加速,-1减速
    acceleration=(0,0,0)
    moving=False#是否有速度
    k=0
    k1=0
    if not ignore_acc:
        while(True):
            for n in range(len(dots)):
                if time-dots[n][0]>0 and dots[n][-1] in ['move2','move','land','moved']:
                    '''if n-k>1:
                        #warnings.warn(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。",Warning,3)
                        #raise Warning(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。")
                        warns.append("In "+str(int(time/1000))+"s,action isn't completed.在"+str(int(time/1000))+"秒动作未完成。")'''
                    k1=n
            k=k1
            #print(k)
            if dots[k][-1]=='move2':
                X=float(dots[k][1])-x
                Y=float(dots[k][2])-y
                Z=float(dots[k][3])-z
                vel=dots[k][4]
                acc=dots[k][5]
            elif dots[k][-1]=='move':
                X=float(dots[k][1])
                Y=float(dots[k][2])
                Z=float(dots[k][3])
                vel=dots[k][4]
                acc=dots[k][5]
            elif dots[k][-1]=='moved':
                X=0
                Y=0
                Z=0
                vel=dots[k][4]
                acc=dots[k][5]
            elif dots[k][-1]=='land':
                X=0
                Y=0
                Z=-z
                vel=200
                acc=400
            alenth=vel**2/(2*acc)#加速距离s=v^2/2a
            R=(X**2+Y**2+Z**2)**0.5#(X,Y,Z)位移矢量
            if R==0:
                moving=False
                if len(lines)>=len(angles):
                    angle=angles[-1][1]
                else:
                    angle=angles[len(lines)][1]
                if len(lines)>=len(leds):
                    led=leds[-1][1]
                else:
                    led=leds[len(lines)][1]
                lines.append((time,x,y,z,angle,led,acceleration))
                #print('\r'+str((time,x,y,z)),end='')
                a=0
            if a==0 and R!=0:#静止初始状态
                #Rs=[]
                ast=time/1000#动作开始时间点
                if R>=2*alenth:#距离是否大于全速加速减速的前进距离
                    slenth=alenth#实际加速距离
                    actiontime=ast+2*vel/acc+(R-2*alenth)/vel#动作结束时间点
                    acctime=vel/acc#加速时长
                else:
                    slenth=R/2
                    actiontime=ast+2*(2*slenth/acc)**0.5
                    acctime=(2*slenth/acc)**0.5
                moving=True
                v=0
                slow=False
                while(moving):
                    if slow:#出现下一指令
                        if v==0:
                            x=x1
                            y=y1
                            z=z1
                            acceleration=(0,0,0)
                            #dots[k][-1]='moved'
                            if len(lines)>=len(angles):
                                angle=angles[-1][1]
                            else:
                                angle=angles[len(lines)][1]
                            if len(lines)>=len(leds):
                                led=leds[-1][1]
                            else:
                                led=leds[len(lines)][1]
                            lines.append((time,x,y,z,angle,led,acceleration))
                            #print(time)
                            break
                        if v-400/fps>0:
                            r+=v/fps-200/(fps**2)
                            v-=400/fps
                            acceleration=(-400*X/R,-400*Y/R,-400*Z/R)
                        else:
                            r+=v**2/800
                            v=0
                            acceleration=(-400*X/R,-400*Y/R,-400*Z/R)
                    elif time/1000-ast<=acctime:#加速
                        r=1/2*acc*(time/1000-ast)**2
                        v=acc*(time/1000-ast)
                        acceleration=(acc*X/R,acc*Y/R,acc*Z/R)
                    elif time/1000<actiontime-acctime:#匀速
                        r=(slenth+vel*(time/1000-ast-acctime))
                        v=vel
                        acceleration=(0,0,0)
                    elif time/1000<actiontime:#减速
                        r=R-1/2*acc*(actiontime-time/1000)**2
                        v=acc*(actiontime-time/1000)
                        acceleration=(-acc*X/R,-acc*Y/R,-acc*Z/R)
                    else:#停
                        r=R
                        if dots[k][-1]=='move2':
                            x=float(dots[k][1])
                            y=float(dots[k][2])
                            z=float(dots[k][3])
                            #dots[k][-1]='moved'
                        elif dots[k][-1]=='move':
                            x+=float(dots[k][1])
                            y+=float(dots[k][2])
                            z+=float(dots[k][3])
                            dots[k][-1]='moved'
                        elif dots[k][-1]=='land':
                            z=0
                        if len(lines)>=len(angles):
                            angle=angles[-1][1]
                        else:
                            angle=angles[len(lines)][1]
                        if len(lines)>=len(leds):
                            led=leds[-1][1]
                        else:
                            led=leds[len(lines)][1]
                        acceleration=(-acc*X/R,-acc*Y/R,-acc*Z/R)
                        lines.append((time,x,y,z,angle,led,acceleration))
                        acceleration=(0,0,0)
                        #print('\r'+str((time,x,y,z)),end='')
                        #print(time)
                        break
                    x1=x+r*X/R
                    y1=y+r*Y/R
                    z1=z+r*Z/R
                    if len(lines)>=len(angles):
                        angle=angles[-1][1]
                    else:
                        angle=angles[len(lines)][1]
                    if len(lines)>=len(leds):
                        led=leds[-1][1]
                    else:
                        led=leds[len(lines)][1]
                    lines.append((time,x1,y1,z1,angle,led,acceleration))
                    #print('\r'+str((time,x1,y1,z1)),end='')
                    time+=1000/fps
                    for n in range(len(dots)):
                        if time-dots[n][0]>0 and dots[n][-1] in ['move2','move','land','moved']:
                            if n-k>0:
                                #warnings.warn(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。",Warning,3)
                                #raise Warning(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。")
                                warns.append("In "+str(int(time/1000))+"s,action isn't completed.在"+str(int(time/1000))+"秒动作未完成。")
                                slow=True
                #print(time/1000,x1,y1,z1)
                #print(moving)
            '''if moving:
                if a==1:#加速状态
                    if R-(v+a/2)<slength:#加速是否结束
                        if
            if v==vel:
                a=0
            else:


            if R<=v:
                x=dots[k][1]
                y=dots[k][2]
                z=dots[k][3]
            else:
                x+=X/R*v
                y+=Y/R*v
                z+=Z/R*v
            #print(time/1000,x,y,z)'''
            if k==len(dots)-1 or time>end:
                m=-1
                breakable=False
                while True:
                    if dots[m][-1]=='land':
                        break
                    if len(dots[m])>3:
                        if z==dots[m][3]:
                            breakable=True
                        break
                    m-=1
                if breakable:
                    break
                if z==0:
                    break
            time+=1000/fps
    else:
        while(True):
            for n in range(len(dots)):
                if time-dots[n][0]>0 and dots[n][-1] in ['move2','move','land','moved']:
                    '''if n-k>1:
                        #warnings.warn(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。",Warning,3)
                        #raise Warning(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。")
                        warns.append("In "+str(int(time/1000))+"s,action isn't completed.在"+str(int(time/1000))+"秒动作未完成。")'''
                    k1=n
            k=k1
            #print(k)
            if dots[k][-1]=='move2':
                X=float(dots[k][1])-x
                Y=float(dots[k][2])-y
                Z=float(dots[k][3])-z
                vel=dots[k][4]
                acc=2.0**512
            elif dots[k][-1]=='move':
                X=float(dots[k][1])
                Y=float(dots[k][2])
                Z=float(dots[k][3])
                vel=dots[k][4]
                acc=2.0**512
            elif dots[k][-1]=='moved':
                X=0
                Y=0
                Z=0
                vel=dots[k][4]
                acc=2.0**512
            elif dots[k][-1]=='land':
                X=0
                Y=0
                Z=-z
                vel=200
                acc=2.0**512
            alenth=vel**2/(2*acc)#加速距离s=v^2/2a
            R=(X**2+Y**2+Z**2)**0.5#(X,Y,Z)位移矢量
            if R==0:
                moving=False
                if len(lines)>=len(angles):
                    angle=angles[-1][1]
                else:
                    angle=angles[len(lines)][1]
                if len(lines)>=len(leds):
                    led=leds[-1][1]
                else:
                    led=leds[len(lines)][1]
                lines.append((time,x,y,z,angle,led,(0,0,0)))
                #print('\r'+str((time,x,y,z)),end='')
                a=0
            if a==0 and R!=0:#静止初始状态
                #Rs=[]
                ast=time/1000#动作开始时间点
                if R>=2*alenth:#距离是否大于全速加速减速的前进距离
                    slenth=alenth#实际加速距离
                    actiontime=ast+2*vel/acc+(R-2*alenth)/vel#动作结束时间点
                    acctime=vel/acc#加速时长
                else:
                    slenth=R/2
                    actiontime=ast+2*(2*slenth/acc)**0.5
                    acctime=(2*slenth/acc)**0.5
                moving=True
                v=0
                slow=False
                while(moving):
                    if slow:#出现下一指令
                        if v==0:
                            x=x1
                            y=y1
                            z=z1
                            #dots[k][-1]='moved'
                            if len(lines)>=len(angles):
                                angle=angles[-1][1]
                            else:
                                angle=angles[len(lines)][1]
                            if len(lines)>=len(leds):
                                led=leds[-1][1]
                            else:
                                led=leds[len(lines)][1]
                            lines.append((time,x,y,z,angle,led,(0,0,0)))
                            #print(time)
                            break
                        if v-2.0**512/fps>0:
                            r+=v/fps-2.0**512/2/(fps**2)
                            v-=2.0**512/fps
                        else:
                            r+=v**2/2.0**512/2
                            v=0
                    elif time/1000-ast<=acctime:#加速
                        r=1/2*acc*(time/1000-ast)**2
                        v=acc*(time/1000-ast)
                    elif time/1000<actiontime-acctime:#匀速
                        r=(slenth+vel*(time/1000-ast-acctime))
                        v=vel
                    elif time/1000<actiontime:#减速
                        r=R-1/2*acc*(actiontime-time/1000)**2
                        v=acc*(actiontime-time/1000)
                    else:#停
                        r=R
                        if dots[k][-1]=='move2':
                            x=float(dots[k][1])
                            y=float(dots[k][2])
                            z=float(dots[k][3])
                            #dots[k][-1]='moved'
                        elif dots[k][-1]=='move':
                            x+=float(dots[k][1])
                            y+=float(dots[k][2])
                            z+=float(dots[k][3])
                            dots[k][-1]='moved'
                        elif dots[k][-1]=='land':
                            z=0
                        if len(lines)>=len(angles):
                            angle=angles[-1][1]
                        else:
                            angle=angles[len(lines)][1]
                        if len(lines)>=len(leds):
                            led=leds[-1][1]
                        else:
                            led=leds[len(lines)][1]
                        lines.append((time,x,y,z,angle,led,(0,0,0)))
                        #print('\r'+str((time,x,y,z)),end='')
                        #print(time)
                        break
                    x1=x+r*X/R
                    y1=y+r*Y/R
                    z1=z+r*Z/R
                    if len(lines)>=len(angles):
                        angle=angles[-1][1]
                    else:
                        angle=angles[len(lines)][1]
                    if len(lines)>=len(leds):
                        led=leds[-1][1]
                    else:
                        led=leds[len(lines)][1]
                    lines.append((time,x1,y1,z1,angle,led,(0,0,0)))
                    #print('\r'+str((time,x1,y1,z1)),end='')
                    time+=1000/fps
                    for n in range(len(dots)):
                        if time-dots[n][0]>0 and dots[n][-1] in ['move2','move','land','moved']:
                            if n-k>0:
                                #warnings.warn(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。",Warning,3)
                                #raise Warning(str(int(time/100)/10)+"s:Action isn't completed.动作未完成。")
                                warns.append("In "+str(int(time/1000))+"s,action isn't completed.在"+str(int(time/1000))+"秒动作未完成。")
                                slow=True
                #print(time/1000,x1,y1,z1)
                #print(moving)
            '''if moving:
                if a==1:#加速状态
                    if R-(v+a/2)<slength:#加速是否结束
                        if
            if v==vel:
                a=0
            else:


            if R<=v:
                x=dots[k][1]
                y=dots[k][2]
                z=dots[k][3]
            else:
                x+=X/R*v
                y+=Y/R*v
                z+=Z/R*v
            #print(time/1000,x,y,z)'''
            if k==len(dots)-1 or time>end:
                m=-1
                breakable=False
                while True:
                    if dots[m][-1]=='land':
                        break
                    if len(dots[m])>3:
                        if z==dots[m][3]:
                            breakable=True
                        break
                    m-=1
                if breakable:
                    break
                if z==0:
                    break
            time+=1000/fps
    '''for t in range(10,120000,10):
        lines.append((time+t,x,y,z))'''
    return(lines,time*fps/1000,warns)

def _dots2line_job(job):
    file, position, fps, points, ignore_acc = job
    return dots2line(
        file,
        fii=position,
        fps=fps,
        points=points,
        ignore_acc=ignore_acc,
    )


def _trajectory_worker_count(configured_workers, drone_count):
    if drone_count <= 0:
        return 1
    if configured_workers is None or int(configured_workers) <= 0:
        return max(1, min(os.cpu_count() or 1, drone_count))
    return max(1, min(int(configured_workers), drone_count))


def _debugger_active():
    return sys.gettrace() is not None or "debugpy" in sys.modules


def _debugger_multiprocessing_unsafe():
    return _debugger_active() and os.environ.get(
        "PYFII_MULTIPROCESS_UNDER_DEBUGGER"
    ) != "1"


def _read_fii_metadata_legacy(data):
    """Original line-based metadata reader, kept only as a fallback."""
    xml = [line.split('  ')[-1] for line in data.split('\n')]
    drones = []
    music_name = None
    field = None
    device_type = None

    for line in xml:
        if line[1:10] == 'MusicName':
            music_name = line.split('"')[1]
        if line[1:8] == 'Actions':
            drones.append(line.split('"')[1])
        if line[1:6] == 'AreaL':
            field = int(line.split('"')[1][0])
        if line[1:11] == 'DeviceType':
            device_type = line.split('"')[1]

    positions = {}
    for drone in drones:
        x = y = None
        for line in xml:
            if line[1:16] == 'ActionFlightPos' and line.split('"')[1][0:4] == drone:
                if line[16] == 'X':
                    x = int(line.split('"')[1].split('pos')[1])
                elif line[16] == 'Y':
                    y = int(line.split('"')[1].split('pos')[1])
        if x is not None and y is not None:
            positions[drone] = (x, y)

    return device_type, field, music_name, drones, positions


def _read_fii_metadata(data):
    """Use XML metadata parsing first and retain the old reader as fallback."""
    try:
        metadata = parse_fii(data)
        return (
            metadata.device_type,
            metadata.field,
            metadata.music_name,
            metadata.actions,
            metadata.takeoff_positions,
        )
    except FiiParseError as error:
        warnings.warn(
            f"XML .fii parser failed ({error}); using the legacy parser.",
            RuntimeWarning,
            stacklevel=2,
        )
        return _read_fii_metadata_legacy(data)


def read_fii(path,getfield=None,getdevice=None,fps=200,ignore_acc=False,workers=None):
    '''
    读入.fii文件
    path 所在文件夹的路径
    '''
    if getfield!=None:
        warnings.warn('getfield argument can be ingored since pyfii1.6.0. pyfii1.6.0及以后版本可忽略getfield参数。',Warning)
    if getdevice!=None:
        warnings.warn('getdevice argument can be ingored since pyfii1.6.0. pyfii1.6.0及以后版本可忽略getdevice参数。',Warning)
    
    fii_path = None
    time_start=time.time()
    for root, dirs, files in os.walk(path):
        for file in files:
            if os.path.splitext(file)[1] == '.fii':
                fii_path=(os.path.join(root , file))
                break
        if fii_path is not None:
            break
    if fii_path is None:
        raise FileNotFoundError(f"No .fii file found under path: {path}")
    with open(fii_path, "r",encoding='utf-8') as F:
        data = F.read()
    DeviceType, field, music_name, drones, positions = _read_fii_metadata(data)
    music = [path+"/动作组/", music_name] if music_name is not None else []
    dots=[]
    t0=0
    n=0
    points={}
    drone_files=[]
    for drone in drones:
        with open(path+'/动作组/'+drone+'/webCodeAll.xml', "r",encoding='utf-8') as F:
            file = F.read()
        drone_files.append(file)
        for dic in read_xml_points(file).items():
            points[dic[0]]=dic[1]
    jobs=[]
    for drone, file in zip(drones, drone_files):
        position = positions.get(drone)
        if position is None:
            raise ValueError('No take off place.起飞位置未定义。')
        jobs.append((file, list(position), fps, points, ignore_acc))

    worker_count = _trajectory_worker_count(workers, len(jobs))
    if worker_count > 1 and _debugger_multiprocessing_unsafe():
        warnings.warn(
            "Trajectory multiprocessing is disabled while a debugger is attached "
            "to avoid a debugpy/fork deadlock; run without debugging for full CPU use.",
            RuntimeWarning,
            stacklevel=2,
        )
        worker_count = 1
    if worker_count == 1:
        lines = map(_dots2line_job, jobs)
    else:
        executor = ProcessPoolExecutor(
            max_workers=worker_count,
            env={
                "PYGAME_HIDE_SUPPORT_PROMPT": "1",
                "PYTHONWARNINGS": "ignore::UserWarning",
            },
        )
        lines = executor.map(_dots2line_job, jobs)

    try:
        for line in lines:
            dots.append(line[0])
            t0=max(t0,line[1])
            n+=1
            if len(line[2])>0:
                for warn in line[2]:
                    warnings.warn('d'+str(n)+' 无人机'+str(n)+':'+warn,Warning,2)
            print('\r'+str(n)+'/'+str(len(drones)),end='')
    finally:
        if worker_count > 1:
            executor.shutdown()
    print('\n读取文件与轨迹计算耗时：'+str(int((time.time()-time_start)*1000+0.5)/1000)+'秒')
    return dots,t0,music,field,DeviceType

'''def read_py(fii):
    time_start=time.time()
    dots=[]
    t0=0
    n=0
    for d in fii.ds:
        line=dots2line(d.outputString)
        dots.append(line[0])
        t0=max(t0,line[1])
        n+=1
        if len(line[2])>0:
            for warn in line[2]:
                warnings.warn('d'+str(n)+':'+warn,Warning,2)
        print('\r'+str(n)+'/'+str(len(fii.ds)),end='')
    print('\n轨迹计算耗时：'+str(int((time.time()-time_start)*1000+0.5)/1000)+'秒')
    return dots,t0'''
