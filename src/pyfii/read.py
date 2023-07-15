import os
import time
import warnings

def str2bgr(color):
    return (int(color[5:7],16),int(color[3:5],16),int(color[1:3],16))

def read_xml_points(data):
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

def read_xml(data,fii=[],time=0,x=0,y=0,z=0,vel=0,acc=0,w=0,points={}):#格式转换,xml指令转换为python指令
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
                    raise Warning("Block intime error.时间开始模块摆放错误")
                time=int(xml[k+1][19:21])*60000+int(xml[k+1][22:24])*1000
                #print(time)
            elif xml[k].split('"')[1][0:11]=='block_delay':
                time+=int(xml[k+2][19:-8])
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
                    repeat=read_xml(newxml*(int(xml[k+1][20:-8])-1),[],time,x,y,z,vel,acc,w,points)
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


def dots2line(file,fii=[],fps=200,points={}):#将指令转换为飞行轨迹
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
    '''for t in range(10,120000,10):
        lines.append((time+t,x,y,z))'''
    return(lines,time*fps/1000,warns)

def read_fii(path,getfeild=False,fps=200):
    '''
    读入.fii文件
    path 所在文件夹的路径
    '''
    time_start=time.time()
    for root, dirs, files in os.walk(path):
        for file in files:
            if os.path.splitext(file)[1] == '.fii':
                fii_path=(os.path.join(root , file))
    with open(fii_path, "r",encoding='utf-8') as F:
        data = F.read()
    data=data.split('\n')
    xml=[]
    n=0
    for d in data:
        n+=1
        #print(d.split('  ')[-1],str(len(d.split('  '))))
        xml.append(d.split('  ')[-1])
    drones=[]
    music=[path+"/动作组/"]
    for k in range(len(xml)):
        #print(xml[k].split('"'))
        if xml[k][1:10]=='MusicName':
            music.append(xml[k].split('"')[1])
        if xml[k][1:8]=='Actions':
            #print(xml[k].split('"')[1][0])
            drones.append(xml[k].split('"')[1])
        if xml[k][1:6]=='AreaL':
            feild=int(xml[k].split('"')[1][0])
    if len(music)==1:
        music=[]
    dots=[]
    t0=0
    n=0
    points={}
    for drone in drones:
        with open(path+'/动作组/'+drone+'/webCodeAll.xml', "r",encoding='utf-8') as F:
            file = F.read()
        for dic in read_xml_points(file).items():
            points[dic[0]]=dic[1]
    for drone in drones:
        for k in range(len(xml)):
            if xml[k][1:16]=='ActionFlightPos' and xml[k].split('"')[1][0:4]==drone:
                if xml[k][16]=='X':
                    x=int(xml[k].split('"')[1].split('pos')[1])
                elif xml[k][16]=='Y':
                    y=int(xml[k].split('"')[1].split('pos')[1])
                #print(xml[k].split('"')[1])
        with open(path+'/动作组/'+drone+'/webCodeAll.xml', "r",encoding='utf-8') as F:
            file = F.read()
        #try:
            line=dots2line(file,fii=[x,y],fps=fps,points=points)
            '''with open(name+'/动作组/'+drone+'line.csv','w',encoding='utf-8') as F:
                F.write('time,x,y,z,angle\n')
                for l in line[0]:
                    for li in l:
                        F.write(str(li))
                        F.write(',')
                    F.write('\n')'''
        '''except:
            raise Exception('No take off place.起飞位置未定义。')'''
        dots.append(line[0])
        t0=max(t0,line[1])
        n+=1
        if len(line[2])>0:
            for warn in line[2]:
                warnings.warn('d'+str(n)+' 无人机'+str(n)+':'+warn,Warning,2)
        print('\r'+str(n)+'/'+str(len(drones)),end='')
    print('\n读取文件与轨迹计算耗时：'+str(int((time.time()-time_start)*1000+0.5)/1000)+'秒')
    if getfeild:
        return dots,t0,music,feild
    else:
        return dots,t0,music

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
    