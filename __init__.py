# -*- coding: utf-8 -*-
__version__ = '1.0.2'

import cv2
import numpy as np
import os
import time

def read_xml(data,fii=[]):#格式转换,xml指令转换为python指令
    data=data.split('\n')
    xml=[]
    n=0
    for d in data:
        n+=1
        #print(d.split('  ')[-1],str(len(d.split('  '))))
        xml.append(d.split('  ')[-1])
    dots=[]
    time=0
    for k in range(len(xml)):
        if xml[k][1:6]=='block':
            #print(xml[k].split('"')[1])
            if xml[k].split('"')[1]=='block_inittime':
                time=int(xml[k+1][19:21])*60+int(xml[k+1][22:24])*1000
                #print(time)
            elif xml[k].split('"')[1]=='block_delay':
                time+=int(xml[k+2][19:-8])
                #print(time)
            elif xml[k].split('"')[1]=='Goertek_MoveToCoord':
                x=int(xml[k+1][16:-8])
                y=int(xml[k+2][16:-8])
                #print(time,x,y,int(xml[k+3][16:-8]))
                dots.append((time,x,y,int(xml[k+3][16:-8])))
            elif xml[k].split('"')[1]=='Goertek_Start':
                if len(fii)==0:
                    x=int(xml[k].split('"')[3])
                    y=int(xml[k].split('"')[5])
                else:
                    x=fii[0]
                    y=fii[1]
                #print(time,x,y,0)
                dots.append((time,x,y,0))
            elif xml[k].split('"')[1]=='Goertek_TakeOff':
                #print(time,x,y,int(xml[k+1][18:-8]))
                dots.append((time,x,y,int(xml[k+1][18:-8])))
            elif xml[k].split('"')[1]=='Goertek_Land':
                #print(time,x,y,0)
                dots.append((time,x,y,0))
    return(dots)

def dots2line(file,fii=[],vilocity=125,fps=100):#将指令转换为飞行轨迹,速度单位:cm/s
    dots=read_xml(file,fii)
    x=dots[0][1]
    y=dots[0][2]
    z=dots[0][3]
    time=0
    v=vilocity/fps
    lines=[]
    while(True):
        k=-1
        for n in range(len(dots)):
            if time-dots[n][0]>0:
                k=n
        X=dots[k][1]-x
        Y=dots[k][2]-y
        Z=dots[k][3]-z
        R=(X**2+Y**2+Z**2)**0.5
        if R<=v:
            x=dots[k][1]
            y=dots[k][2]
            z=dots[k][3]
        else:
            x+=X/R*v
            y+=Y/R*v
            z+=Z/R*v
        #print(time/1000,x,y,z)
        lines.append((time,x,y,z))
        if k==len(dots)-1 and z==dots[-1][3]:
            break
        time+=1000/fps
    for t in range(10,60000,10):
        lines.append((time+t,x,y,z))
    return(lines,time*fps/1000)

def read_fii(name):
    time_start=time.time()
    for root, dirs, files in os.walk(name):
        for file in files:
            if os.path.splitext(file)[1] == '.fii':
                fii_name=(os.path.join(root , file))
    with open(fii_name, "r",encoding='utf-8') as F:
        data = F.read()
    data=data.split('\n')
    xml=[]
    n=0
    for d in data:
        n+=1
        #print(d.split('  ')[-1],str(len(d.split('  '))))
        xml.append(d.split('  ')[-1])
    drones=[]
    for k in range(len(xml)):
        #print(xml[k].split('"'))
        if xml[k][1:8]=='Actions':
            #print(xml[k].split('"')[1][0])
            drones.append(xml[k].split('"')[1])
    dots=[]
    t0=0
    for drone in drones:
        for k in range(len(xml)):
            if xml[k][1:16]=='ActionFlightPos' and xml[k].split('"')[1][0:4]==drone:
                if xml[k][16]=='X':
                    x=int(xml[k].split('"')[1].split('pos')[1])
                elif xml[k][16]=='Y':
                    y=int(xml[k].split('"')[1].split('pos')[1])
                #print(xml[k].split('"')[1])
        with open(name+'\\动作组\\'+drone+'\\webCodeAll.xml', "r",encoding='utf-8') as F:
            file = F.read()
        dots.append(dots2line(file,fii=[x,y])[0])
        t0=max(t0,dots2line(file,fii=[x,y])[1])
    print('读取文件耗时：'+str(int((time.time()-time_start)*1000+0.5)/1000)+'秒')
    return dots,t0

def color(n):
    n=int(n*765/7)
    x=255
    if int((n%765)/255)==0:
        return(255-n%255,n%255,x)
    if int((n%765)/255)==1:
        return(n%255,x,255-n%255)
    if int((n%765)/255)==2:
        return(x,255-n%255,n%255)

def show(data,t0,show=True,save="",FPS=100):
    t0=int(t0+0.5)+300
    if len(save)>0:
        show=False
        video = cv2.VideoWriter(save+".mp4", cv2.VideoWriter_fourcc('I', '4', '2', '0'), FPS,(1120,560))
    if show or len(save)>0:
        img=np.zeros((560,1120,3),np.uint8)
        cv2.rectangle(img,(0,0),(560,560),(255,255,255),1)
        for x in range(12):
            for y in range(12):
                if x==11 and y!=11:
                    cv2.rectangle(img,(550,560-y*50),(560,560-(y*50+50)),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
                elif x!=11 and y==11:
                    cv2.rectangle(img,(x*50,10),(x*50+50,0),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
                elif x==11 and y==11:
                    cv2.rectangle(img,(550,10),(560,0),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
                else:
                    cv2.rectangle(img,(x*50,560-y*50),(x*50+50,560-(y*50+50)),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
        cv2.rectangle(img,(560,0),(1120,250),(255,255,255),1)
        cv2.rectangle(img,(560,250),(1120,500),(255,255,255),1)
        for x in range(1,18):
            cv2.rectangle(img,(560,x*10),(580,x*10),(255,255,255),-1)
            cv2.rectangle(img,(560,x*10+250),(580,x*10+250),(255,255,255),-1)
            if x%5==0:
                cv2.rectangle(img,(560,x*10),(600,x*10),(255,255,255),-1)
                cv2.rectangle(img,(560,x*10+250),(600,x*10+250),(255,255,255),-1)
        for x in range(4):
            cv2.rectangle(img,(560+x*140,500),(700+x*140,530),(255,255,255),1)
            cv2.rectangle(img,(560+x*140,530),(700+x*140,560),(255,255,255),1)
        cv2.rectangle(img,(1030,530),(1120,560),(255,255,255),1)
        font=cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img,'front',(560,240), font, 1,(255,255,255),1)
        cv2.putText(img,'right',(560,490), font, 1,(255,255,255),1)
        cv2.imwrite('gui.png',img)
        #生成可视化界面↑
    time_read=time.time()
    k=0
    K=0
    print('时间\t距离\t距离程度\t错误无人机')
    time_FPS=time.time()
    f=0#记录帧数
    while k < t0:
        if show or len(save)>0:
            img2=cv2.imread('gui.png')
        aixs=[]
        for a in range(len(data)):
            t=data[a][k][0]/1000
            x=int(data[a][k][1]+0.5)
            y=int(data[a][k][2]+0.5)
            z=int(data[a][k][3]+0.5)
            '''cv2.circle(img2,(x,560-y),15,color(a),-1)
            cv2.rectangle(img2,(560+x-15,250-z+5),(560+x+15,250-z-5),color(a),-1)
            cv2.rectangle(img2,(560+y-15,500-z+5),(560+y+15,500-z-5),color(a),-1)'''
            if show or len(save)>0:
                if a<4:
                    cv2.putText(img2,str(a+1)+' ('+str(x)+','+str(y)+','+str(z)+')',(560+a*140,520), font, 0.5,color(a),1)
                else:
                    cv2.putText(img2,str(a+1)+' ('+str(x)+','+str(y)+','+str(z)+')',(a*140,550), font, 0.5,color(a),1)#在img2上画出无人机的位置并显示坐标
            aixs.append((x,y,z,a))
        if show or len(save)>0:
            Xs=sorted(aixs,key=lambda x:x[0])
            Ys=sorted(aixs,key=lambda x:x[1],reverse=True)
            Zs=sorted(aixs,key=lambda x:x[2],reverse=True)
            #根据距离远近渲染
            for X in Xs:
                cv2.rectangle(img2,(560+X[1]-15,500-X[2]+5),(560+X[1]+15,500-X[2]-5),color(X[3]),-1)
            for Y in Ys:
                cv2.rectangle(img2,(560+Y[0]-15,250-Y[2]+5),(560+Y[0]+15,250-Y[2]-5),color(Y[3]),-1)
            for Z in Zs:
                cv2.circle(img2,(Z[0],560-Z[1]),15,color(Z[3]),-1)
        #print(Xs)
        #print(aixs)
        for m in range(len(aixs)):
            for n in range(m+1,len(aixs)):#计算距离
                distance=((aixs[m][0]-aixs[n][0])**2+(aixs[m][1]-aixs[n][1])**2)**0.5
                if distance<60:
                    print(t,distance,int(distance/20),m+1,n+1)#距离太近就输出错误
                    if show or len(save)>0:
                        cv2.circle(img2,(aixs[m][0],560-aixs[m][1]),5,(0,0,255),-1)
                        cv2.circle(img2,(560+aixs[m][0],250-aixs[m][2]),5,(0,0,255),-1)
                        cv2.circle(img2,(560+aixs[m][1],500-aixs[m][2]),5,(0,0,255),-1)
                        cv2.circle(img2,(aixs[n][0],560-aixs[n][1]),5,(0,0,255),-1)
                        cv2.circle(img2,(560+aixs[n][0],250-aixs[n][2]),5,(0,0,255),-1)
                        cv2.circle(img2,(560+aixs[n][1],500-aixs[n][2]),5,(0,0,255),-1)#错误红点标记
        if show or len(save)>0:
            cv2.putText(img2,str(t),(980,550),font,0.5,(255,255,255),1)#在img2上显示时间
        f+=1
        time_fps=time.time()
        if len(save)==0 and show:
            k=int((time_fps-time_read)*100)
        if f==1:
            time_fps=time.time()
            try:
                fps=str(int(10/(time_fps-time_FPS)+0.5)/10)
                fs=int(float(fps)/10+0.5)*10
            except:
                fps='100.0'
                fs=100
            if fs==0:
                fs=10
        elif f%fs==0:
            fps=str(int(fs*10/(time_fps-time_FPS)+0.5)/10)
            time_FPS=time_fps
        if len(save)>0:
            fps=str(int(FPS*10+0.5)/10)
        if show or len(save)>0:
            cv2.putText(img2,'fps:'+fps,(1040,550),font,0.5,(255,255,255),1)
        if show:
            cv2.imshow('img',img2)
            key = cv2.waitKey(1) & 0xff
            #Esc键退出
            if key == 27:
                break
            elif key==32:#空格暂停
                cv2.waitKey(0)
                time_read=time.time()-k/100
            elif key==ord('q'):#后退
                k-=50
                #time_read+=0.5
                '''if time_read>time_fps:
                    time_read=time_fps'''
                if k<0:
                    k=0
                cv2.waitKey(0)
                time_read=time.time()-k/100
            elif key==ord('e'):#快进
                #time_read-=0.5
                k+=50
                cv2.waitKey(0)
                time_read=time.time()-k/100
        if not show and len(save)==0:
            k+=1
        if len(save)>0:
            video.write(img2)
            print(t)
            K+=100/FPS
            k=int(K+0.5)
    if show or len(save)>0:
        cv2.destroyAllWindows()
    timer=time.time()-time_read
    print('平均帧率：'+str(int(10*f/timer+0.5)/10))
    print('飞行总时间：'+str(int((time.time()-time_read)*1000+0.5)/1000)+'秒')
    if len(save)>0:
        video.release()#储存视频

class Drone:
    def __init__(self,x,y):
        self.space = 0
        self.block = 0
        self.inT = False
        self.outputString = '''<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables></variables>
'''
        self.X=int(x+0.5)
        self.Y=int(y+0.5)
        self.times=[]
    
    def takeoff(self,time,z):
        """
        起飞(x坐标,y坐标,起飞高度)
        单位:cm
        """
        time=int(time+0.5)
        self.times.append(time)
        m=int(time/60) #分
        s = time%60 #秒
        if s<10:
            time='0'+str(m)+':0'+str(s)
        else:
            time='0'+str(m)+':'+str(s)
        self.z =z
        self.outputString += '''  <block type="Goertek_Start" x="'''+str(self.X)+'''" y="'''+str(self.Y)+'''">
    <next>
      <block type="block_inittime">
        <field name="time">'''+time+'''</field>
        <field name="color">#cccccc</field>
        <statement name="functionIntit">
          <block type="Goertek_UnLock">
            <next>
              <block type="block_delay">
                <field name="delay">0</field>
                <field name="time">1000</field>
                <next>
                  <block type="Goertek_TakeOff">
                    <field name="alt">'''+str(int(z+0.5))+'''</field>
'''
        self.block+=6
        self.inT=True
        self.space=4

    def intime(self,time):
        """
        某一时刻开始执行(时刻)
        单位:s(直接写秒数)
        """
        for n in range(self.block-1,0,-1):
            spaces='  '*(self.space+n)
            if n%2==1:
                self.outputString += spaces+'''</block>
'''
            else:
                self.outputString += spaces+'''</next>
'''
        self.block=0
        spaces='  '*(self.space+self.block)
        self.outputString += spaces+'''</statement>
'''
        time=int(time+0.5)
        self.times.append(time)
        spaces = '  '*self.space
        m=int(time/60) #分
        s = time%60 #秒
        if s<10:
            time='0'+str(m)+':0'+str(s)
        else:
            time='0'+str(m)+':'+str(s)
        self.outputString += spaces+'''<next>
'''+spaces+'''  <block type="block_inittime">
'''+spaces+'''    <field name="time">'''+time+'''</field>
'''+spaces+'''    <field name="color">#cccccc</field>
'''+spaces+'''    <statement name="functionIntit">
'''
        self.space+=2
        self.block+=1
        self.inT=False

    def move2(self, x, y, z):
        """
        直线移动至(x坐标,y坐标,z坐标)
        单位:cm
        必须在intime(time)中
        """
        x,y,z=int(x+0.5),int(y+0.5),int(z+0.5)
        self.x, self.y, self.z = x, y, z
        spaces='  '*(self.space+self.block)
        if self.inT:
            self.outputString += spaces+'''<next>
    '''
            self.block+=1
            spaces+='  '
        self.outputString += spaces+'''<block type="Goertek_MoveToCoord">
'''+spaces+'''  <field name="X">'''+str(x)+'''</field>
'''+spaces+'''  <field name="Y">'''+str(y)+'''</field>
'''+spaces+'''  <field name="Z">'''+str(z)+'''</field>
'''
        self.block+=1
        self.inT=True

    def delay(self, time):
        """
        等待(时间)
        单位:ms
        必须在intime(time)中
        """
        time=int(time+0.5)
        spaces='  '*(self.space+self.block)
        if self.inT:
            self.outputString += spaces+'''<next>
'''
            self.block+=1
            spaces+='  '
        self.outputString += spaces+'''<block type="block_delay">
'''+spaces+'''  <field name="delay">0</field>
'''+spaces+'''  <field name="time">'''+str(time)+'''</field>
'''
        self.block+=1
        self.inT=True
    def land(self):
        """
        降落
        """
        spaces='  '*(self.space+self.block)
        self.outputString += spaces+'''<block type="Goertek_Land"></block>
'''

    def end(self):
        """
        结束
        """
        for n in range(self.space-1,-1,-1):
            spaces='  '*n
            if n==0:
                self.outputString += '</xml>'
            elif n%2==1:
                self.outputString += spaces+'''</block>
'''
            else:
                self.outputString += spaces+'''</next>
'''

class Fii:
    def __init__(self,name,drones):
        self.name=name
        self.ds=drones
        self.dots=[]
        self.t0=0
        for d in self.ds:
            self.dots.append(dots2line(d.outputString,fii=[d.X,d.Y])[0])
            self.t0=max(self.t0,dots2line(d.outputString,fii=[d.X,d.Y])[1])

    def save(self):
        if not os.path.exists(self.name):
            os.makedirs(self.name)

        file=open(self.name+'\\'+self.name+'.fii',"w",encoding='utf-8')
        file.write('''<?xml version="1.0" encoding="utf-8"?>
<GoertekGraphicXml>
  <DeviceType DeviceType="F400" />
  <AreaL AreaL="600" />
  <AreaW AreaW="600" />
  <AreaH AreaH="300" />
''')
        k=1
        for d in self.ds:
            file.write('  <Actions actionname="动作组'+str(k)+'" />')
            file.write('\n')
            file.write('''  <ActionFlight actionfname="动作组'''+str(k)+'''无人机'''+str(k)+'''" />
  <ActionFlightID actionfid="动作组'''+str(k)+'''无人机'''+str(k)+'''UAVID'''+str(k)+'''00'''+str(k)+'''" />
  <ActionFlightPosX actionfX="动作组'''+str(k)+'''无人机'''+str(k)+'''pos'''+str(d.X)+'''" />
  <ActionFlightPosY actionfY="动作组'''+str(k)+'''无人机'''+str(k)+'''pos'''+str(d.Y)+'''" />
  <ActionFlightPosZ actionfZ="动作组'''+str(k)+'''无人机'''+str(k)+'''pos0" />
''')
            for t in d.times:
                file.write('  <动作组'+str(k)+'Controls time="'+str(t)+'" />')
                file.write('\n')
            k+=1
        file.write('</GoertekGraphicXml>')
        file.close()
        
        if not os.path.exists(self.name+'\\动作组'):
            os.makedirs(self.name+'\\动作组') 
        file=open(self.name+'\\动作组\\checksums.xml',"w",encoding='utf-8')
        file.write('<?xml version="1.0" encoding="utf-8"?>')
        file.write('\n')
        file.write('<CheckSumXml>')
        file.write('\n')
        k=1
        for d in self.ds:
            file.write('  <CheckSums flightchecksum="动作组'+str(k)+'无人机'+str(k)+'UAVID'+str(k)+'00'+str(k)+'CheckSum0" />')
            file.write('\n')
            k+=1
        file.write('</CheckSumXml>')
        file.close()

        k=1
        for d in self.ds:
            if not os.path.exists(self.name+'\\动作组\\动作组'+str(k)):
                os.makedirs(self.name+'\\动作组\\动作组'+str(k)) 
            file=open(self.name+'\\动作组\\动作组'+str(k)+'\\webCodeAll.xml',"w",encoding='utf-8')
            file.write(d.outputString)
            file.close()
            k+=1
        print('已保存'+self.name)
