import cv2
import numpy as np
import math
import geometry as g
import IIID
import read_xml
import os
import time
import read_fii
time_start=time.time()
fii=True#是否读取.fii
save=True#保存为视频
show=False#展示
if save:
    video = cv2.VideoWriter("drones-3D.mp4", cv2.VideoWriter_fourcc('I', '4', '2', '0'), 100,(1280,720))
def color(n):
    n=int(n*765/7)
    x=255
    if int((n%765)/255)==0:
        return(255-n%255,n%255,x)
    if int((n%765)/255)==1:
        return(n%255,x,255-n%255)
    if int((n%765)/255)==2:
        return(x,255-n%255,n%255)
center=(280,280,165)#三维渲染旋转中心
lines=[]#三维渲染的线
lines.append([(0,0,0),(600,0,0),(0,0,255),1,8,'line'])
lines.append([(0,0,0),(0,600,0),(0,255,0),1,8,'line'])
lines.append([(0,0,0),(0,0,300),(255,0,0),1,8,'line'])
for x in range(1,57):
    if x%10==5:
        lines.append([(x*10,0,0),(x*10,40,40),(255,255,0),1,8,'line'])
        lines.append([(0,x*10,0),(40,x*10,40),(255,0,255),1,8,'line'])
    elif x%10==0:
        lines.append([(x*10,0,0),(x*10,50,50),(255,255,0),1,8,'line'])
        lines.append([(0,x*10,0),(50,x*10,50),(255,0,255),1,8,'line'])
    else:
        lines.append([(x*10,0,0),(x*10,30,30),(255,255,0),1,8,'line'])
        lines.append([(0,x*10,0),(30,x*10,30),(255,0,255),1,8,'line'])
for x in range(8,26):
    if x%10==5:
        lines.append([(0,0,x*10),(40,40,x*10),(0,255,255),1,8,'line'])
    elif x%10==0:
        lines.append([(0,0,x*10),(50,50,x*10),(0,255,255),1,8,'line'])
    else:
        lines.append([(0,0,x*10),(30,30,x*10),(0,255,255),1,8,'line'])
#绘制坐标轴↑
if fii:
    data,t0=read_fii.read_fii('比赛现场程序')
else:
    files=[]
    path = '2021-6/'
    filelist = os.listdir(path)
    for item in filelist:
        if item.endswith('.xml'): 
            item = path + item
            print(item)
            with open(item, "r",encoding='utf-8') as F:
                files.append(F.read())#读入path文件夹中的.xml文件
    data=[]
    t0=0
    for file in files:
        data.append(read_xml.dots2line(file,fps=100))
    t0=max(t0,len(read_xml.dots2line(file,fps=100)))#取最长的时间
#读取文件↑
time_read=time.time()
print('读取文件耗时：'+str(int((time_read-time_start)*1000+0.5)/1000)+'秒')
imshow=[90,-15,1,0,0]#第1、2个值为观察角度
i=imshow[0]
k=0
print('时间\t距离\t距离程度\t错误无人机')
time_FPS=time.time()
f=0#记录帧数
while k < t0:
    aixs=[]#飞机坐标
    texts=[]#显示的文字
    for a in range(len(data)):
        t=data[a][k][0]/1000
        x=data[a][k][1]
        y=data[a][k][2]
        z=data[a][k][3]
        c=color(a)
        aixs.append([(x,y,z),c,5,-1,'sphere'])
        texts.append([str(a+1)+'('+str(int(x+0.5))+','+str(int(y+0.5))+','+str(int(z+0.5))+')',(0,140+30*a),0.5,c,1,'text'])
    texts.append(['T+'+str(t),(0,80),0.5,(255,255,255),1,'text'])
    errors=[]#圈出错误的飞机
    for m in range(len(aixs)):
        for n in range(m+1,len(aixs)):#计算距离
            distance=((aixs[m][0][0]-aixs[n][0][0])**2+(aixs[m][0][1]-aixs[n][0][1])**2)**0.5
            if distance<60:
                print(t,distance,int(distance/20),m+1,n+1)#距离太近就输出错误
                errors.append([(aixs[m][0][0],aixs[m][0][1],aixs[m][0][2]),(0,0,255),10,1,'sphere'])#错误红圈标记
                errors.append([(aixs[n][0][0],aixs[n][0][1],aixs[n][0][2]),(0,0,255),10,1,'sphere'])
    '''x=1#跟踪飞机
    r,imshow[0],imshow[1]=g.xyz2rab(aixs[x-1][0][0]-center[0],aixs[x-1][0][1]-center[1],aixs[x-1][0][2]-center[2])
    imshow[0]=int(math.degrees(imshow[0])+0.5)+180
    imshow[1]=-int(math.degrees(imshow[1])+0.5)'''
    f+=1
    time_fps=time.time()
    if not save:#不保存为视频就跳帧，视频为100帧
        k=int((time_fps-time_read)*100)
    if f==1:
        img=IIID.show(aixs+lines+errors+texts,center,1280,720,imshow)
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
    if save:
        fps='100.0'
    #fps为帧率，fs为计算帧率的帧数间隔
    texts.append(['FPS:'+fps,(0,110),0.5,(255,255,255),1,'text'])#显示帧率
    if show or save:
        img=IIID.show(aixs+lines+errors+texts,center,1280,720,imshow)
    if show:
        cv2.imshow('img',img)
        key = cv2.waitKey(1) & 0xff
        #Esc键退出
        if key == 27:
            break
        elif key==32:#长按空格键暂停，暂停后可以按wasd旋转，按esc退出暂停
            imshow[0],imshow[1]=IIID.show(aixs+lines+errors+texts,center,1280,720,[imshow[0],imshow[1],1])
            i=imshow[0]-int(k/100*36+0.5)
            time_read=time_fps-k/100
        elif key==ord('q'):#后退
            time_read+=0.5
            if time_read>time_fps:
                time_read=time_fps
        elif key==ord('e'):#快进
            time_read-=0.5
    if save:
        video.write(img)
        print(t)
        k+=1
    imshow[0]=int(i+k/100*36+0.5)#边演示示边旋转
cv2.destroyAllWindows()
timer=time.time()-time_read
print('平均帧率：'+str(int(10*f/timer+0.5)/10))
print('飞行总时间：'+str(int(timer*1000+0.5)/1000)+'秒')
if save:
    video.release()