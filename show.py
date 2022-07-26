import os
import time
import uuid
import warnings

import cv2
import numpy as np
import pygame
from ffmpy import FFmpeg

from .cv3d import IIID,IIID2

# 视频添加音频
def video_add_audio(video_path: str, audio_path: str,output_path:str):
    _ext_video = os.path.basename(video_path).strip().split('.')[-1]
    _ext_audio = os.path.basename(audio_path).strip().split('.')[-1]
    if _ext_audio not in ['mp3', 'wav']:
        raise Exception('audio format not support')
    _codec = 'copy'
    if _ext_audio == 'wav':
        _codec = 'aac'
    result =output_path.format(uuid.uuid4(), _ext_video)
    ff = FFmpeg(
        inputs={video_path: None, audio_path: None},
        outputs={result: '-map 0:v -map 1:a -c:v copy -c:a {} -shortest'.format(_codec)})
    print(ff.cmd)
    ff.run()
    return result

'''def nothing(x):
    pass'''

def color(n,m=0):
    n=180-n*180/7
    if m>0:
        n=(-abs(n))%180
        h,s,v=int(n),int(255-m),255
    else:
        n=(-abs(n))%180
        h,s,v=int(n),255,int(255+m)
    img=np.zeros((1,1,3),np.uint8)
    img[0][0]=(h,s,v)
    img=cv2.cvtColor(img,cv2.COLOR_HSV2BGR)
    return(int(img[0][0][0]),int(img[0][0][1]),int(img[0][0][2]))

def draw_drone(img,x,y,color,a=0,up=False):
    if up:
        cv2.circle(img,(int(x-21/2*np.cos(np.pi/4+a)),int(y+21/2*np.sin(np.pi/4+a))),8,color,1)
        cv2.circle(img,(int(x-21/2*np.cos(3*np.pi/4+a)),int(y+21/2*np.sin(3*np.pi/4+a))),8,color,1)
        cv2.circle(img,(int(x-21/2*np.cos(-3*np.pi/4+a)),int(y+21/2*np.sin(-3*np.pi/4+a))),8,color,1)
        cv2.circle(img,(int(x-21/2*np.cos(-np.pi/4+a)),int(y+21/2*np.sin(-np.pi/4+a))),8,color,1)
        cv2.line(img,(int(x-21/2*np.cos(np.pi/4+a)),int(y+21/2*np.sin(np.pi/4+a))),(int(x-21/2*np.cos(-3*np.pi/4+a)),int(y+21/2*np.sin(-3*np.pi/4+a))),color,1)
        cv2.line(img,(int(x-21/2*np.cos(-np.pi/4+a)),int(y+21/2*np.sin(-np.pi/4+a))),(int(x-21/2*np.cos(3*np.pi/4+a)),int(y+21/2*np.sin(3*np.pi/4+a))),color,1)
    else:
        cv2.ellipse(img,(int(x+21/(2**0.5)/2),int(y-1/4*7.6)),(8,2),0,0,360,color,1)
        cv2.ellipse(img,(int(x-21/(2**0.5)/2),int(y-1/4*7.6)),(8,2),0,0,360,color,1)
        cv2.ellipse(img,(int(x-21/(2**0.5)/2),int(y-3/4*7.6)),(8,2),0,0,360,color,1)
        cv2.ellipse(img,(int(x+21/(2**0.5)/2),int(y-3/4*7.6)),(8,2),0,0,360,color,1)
        cv2.line(img,(int(x+21/(2**0.5)/2),int(y-1/4*7.6)),(int(x-21/(2**0.5)/2),int(y-3/4*7.6)),color,1)
        cv2.line(img,(int(x-21/(2**0.5)/2),int(y-1/4*7.6)),(int(x+21/(2**0.5)/2),int(y-3/4*7.6)),color,1)

def drone3d(aixs,x,y,z,c,a):
    aixs.append([(x+21/2*np.cos(np.pi/4+a),y+21/2*np.sin(np.pi/4+a),z),c,(14.9-21/4*2**0.5),1,'ring'])
    aixs.append([(x+21/2*np.cos(3*np.pi/4+a),y+21/2*np.sin(3*np.pi/4+a),z),c,(14.9-21/4*2**0.5),1,'ring'])
    aixs.append([(x+21/2*np.cos(-3*np.pi/4+a),y+21/2*np.sin(-3*np.pi/4+a),z),c,(14.9-21/4*2**0.5),1,'ring'])
    aixs.append([(x+21/2*np.cos(-np.pi/4+a),y+21/2*np.sin(-np.pi/4+a),z),c,(14.9-21/4*2**0.5),1,'ring'])
    aixs.append([(x+21/2*np.cos(np.pi/4+a),y+21/2*np.sin(np.pi/4+a),z),(x+21/2*np.cos(-3*np.pi/4+a),y+21/2*np.sin(-3*np.pi/4+a),z),c,1,8,'line'])
    aixs.append([(x+21/2*np.cos(-np.pi/4+a),y+21/2*np.sin(-np.pi/4+a),z),(x+21/2*np.cos(3*np.pi/4+a),y+21/2*np.sin(3*np.pi/4+a),z),c,1,8,'line'])

'''def color(n):
    n=n*180/7
    x=255
    if int((n%765)/255)==0:
        return(255-n%255,n%255,x)
    if int((n%765)/255)==1:
        return(n%255,x,255-n%255)
    if int((n%765)/255)==2:
        return(x,255-n%255,n%255)'''

def show(data,t0,music,show=True,save="",FPS=200,ThreeD=False,imshow=[120,-15],d=(600,450),track=[]):
    t0=int(t0+0.5)+300
    if len(save)>0 and not ThreeD:
        show=False
        video = cv2.VideoWriter(save+"_process.mp4", cv2.VideoWriter_fourcc('A', 'V', 'C', '1'), FPS,(1200,600))
    if len(save)>0 and ThreeD:
        if len(track)==0:
            video = cv2.VideoWriter(save+"_process.mp4", cv2.VideoWriter_fourcc('A', 'V', 'C', '1'), FPS,(1280,720))
        else:
            video = cv2.VideoWriter(save+"_process.mp4", cv2.VideoWriter_fourcc('A', 'V', 'C', '1'), FPS,(3840,1920))
    if (show and not ThreeD) or len(save)>0:
        img=np.zeros((600,1200,3),np.uint8)
        cv2.rectangle(img,(0,0),(600,600),(255,255,255),1)
        for x in range(12):
            for y in range(12):
                if x==11 and y!=11:
                    cv2.rectangle(img,(570,580-y*50),(580,580-(y*50+50)),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
                elif x!=11 and y==11:
                    cv2.rectangle(img,(x*50+20,30),(x*50+70,20),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
                elif x==11 and y==11:
                    cv2.rectangle(img,(570,30),(580,20),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
                else:
                    cv2.rectangle(img,(x*50+20,580-y*50),(x*50+70,580-(y*50+50)),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
        cv2.rectangle(img,(600,0),(1200,270),(255,255,255),1)
        cv2.rectangle(img,(600,270),(1200,540),(255,255,255),1)
        for x in range(0,18):
            cv2.rectangle(img,(600,x*10+20),(620,x*10+20),(255,255,255),-1)
            cv2.rectangle(img,(600,x*10+290),(620,x*10+290),(255,255,255),-1)
            if x%5==0:
                cv2.rectangle(img,(600,x*10+20),(640,x*10+20),(255,255,255),-1)
                cv2.rectangle(img,(600,x*10+290),(640,x*10+290),(255,255,255),-1)
        for a in range(7):
            if a<4:
                for x in range(150):
                    cv2.rectangle(img,(600+a*150+x,540),(600+a*150+x,570),color(a,(x-75)/75*125),-1)
            else:
                for x in range(150):
                    cv2.rectangle(img,(600+(a-4)*150+x,570),(600+(a-4)*150+x,600),color(a,(x-75)/75*125),-1)
        for x in range(4):
            cv2.rectangle(img,(600+x*150,540),(750+x*150,570),(255,255,255),1)
            cv2.rectangle(img,(600+x*150,570),(750+x*150,600),(255,255,255),1)
        cv2.rectangle(img,(1120,570),(1200,600),(255,255,255),1)
        font=cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img,'front',(600,260), font, 1,(255,255,255),1)
        cv2.putText(img,'right',(600,530), font, 1,(255,255,255),1)
        cv2.imwrite('gui.png',img)
        #生成可视化界面↑
    if ThreeD:
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
        i=imshow[0]
    if (show and len(save)==0) or (ThreeD and len(save)==0):
        if len(music)>1:
            for root, dirs, files in os.walk(music[0]):
                for file in files:
                    if os.path.splitext(file)[0]==music[1]:
                        music_name=(os.path.join(root , file))
            pygame.mixer.init()
            pygame.mixer.music.load(music_name)
            pygame.mixer.music.play(start=0.0)
        elif len(music)==1:
            pygame.mixer.init()
            pygame.mixer.music.load(music[0])
            pygame.mixer.music.play(start=0.0)
    time_read=time.time()
    k=0
    K=0
    #print('时间\t距离\t距离程度\t错误无人机')
    time_FPS=time.time()
    f=0#记录帧数
    while k < t0:
        if (show or len(save)>0) and not ThreeD:
            img2=cv2.imread('gui.png')
        aixs=[]
        if not ThreeD:
            t=0
            for a in range(len(data)):
                if len(data[a])>k:
                    t=max(t,data[a][k][0]/1000)
                    x=data[a][k][1]
                    y=data[a][k][2]
                    z=data[a][k][3]
                    angle=data[a][k][4]
                else:
                    t=max(t,data[a][-1][0]/1000)
                    x=data[a][-1][1]
                    y=data[a][-1][2]
                    z=data[a][-1][3]
                    angle=data[a][-1][4]
                '''cv2.circle(img2,(x,560-y),15,color(a),-1)
                cv2.rectangle(img2,(560+x-15,250-z+5),(560+x+15,250-z-5),color(a),-1)
                cv2.rectangle(img2,(560+y-15,500-z+5),(560+y+15,500-z-5),color(a),-1)'''
                if (show or len(save)>0) and not ThreeD:
                    if a<4:
                        cv2.putText(img2,str(a+1)+' ('+str(int(x*1+0.5))+','+str(int(y*1+0.5))+','+str(int(z*1+0.5))+')',(600+a*150,560), font, 0.5,(255,255,255),1)
                    else:
                        cv2.putText(img2,str(a+1)+' ('+str(int(x*1+0.5))+','+str(int(y*1+0.5))+','+str(int(z*1+0.5))+')',(a*150,590), font, 0.5,(255,255,255),1)#在img2上画出无人机的位置并显示坐标
                aixs.append((x,y,z,angle,a))
        if (show or len(save)>0) and not ThreeD:
            Xs=sorted(aixs,key=lambda x:x[0])
            Ys=sorted(aixs,key=lambda x:x[1],reverse=True)
            Zs=sorted(aixs,key=lambda x:x[2])
            #根据距离远近渲染
            for X in Xs:
                draw_drone(img2,620+X[1],540-X[2],color(X[4],(X[0]-280)/280*125))
                #cv2.rectangle(img2,(int(560+X[1]-15),int(500-X[2]+5)),(int(560+X[1]+15),int(500-X[2]-5)),color(X[3],(X[0]-280)/280*125),-1)
            for Y in Ys:
                draw_drone(img2,620+Y[0],270-Y[2],color(Y[4],(Y[1]-280)/280*125))
                #cv2.rectangle(img2,(int(560+Y[0]-15),int(250-Y[2]+5)),(int(560+Y[0]+15),int(250-Y[2]-5)),color(Y[3],(280-Y[1])/280*125),-1)
            for Z in Zs:
                draw_drone(img2,20+Z[0],580-Z[1],color(Z[4],(Z[2]-125)/125*125),a=Z[3]/180*np.pi,up=True)
                #cv2.circle(img2,(Z[0],560-Z[1]),15,color(Z[3],(Z[2]-125)/125*125),-1)
        #print(Xs)
        #print(aixs)
        if not ThreeD:
            for m in range(len(aixs)):
                for n in range(m+1,len(aixs)):#计算距离
                    distance=((aixs[m][0]-aixs[n][0])**2+(aixs[m][1]-aixs[n][1])**2)**0.5
                    if distance<50:
                        #print(t,distance,int(distance/20),m+1,n+1)#距离太近就输出错误
                        warnings.warn('In '+str(int(t))+'s,distance between d'+str(m+1)+' and d'+str(n+1)+' is less than '+str(int(distance/10)+1)+'0cm.在'+str(int(t))+'秒，无人机'+str(m+1)+'和无人机'+str(n+1)+'之间的距离小于'+str(int(distance/10)+1)+'0厘米。',Warning,2)
                        if show or len(save)>0:
                            cv2.circle(img2,(int(20+aixs[m][0]),int(580-aixs[m][1])),20,(0,0,255),3)
                            cv2.circle(img2,(int(620+aixs[m][0]),int(270-aixs[m][2])),20,(0,0,255),3)
                            cv2.circle(img2,(int(620+aixs[m][1]),int(540-aixs[m][2])),20,(0,0,255),3)
                            cv2.circle(img2,(int(20+aixs[n][0]),int(580-aixs[n][1])),20,(0,0,255),3)
                            cv2.circle(img2,(int(620+aixs[n][0]),int(270-aixs[n][2])),20,(0,0,255),3)
                            cv2.circle(img2,(int(620+aixs[n][1]),int(540-aixs[n][2])),20,(0,0,255),3)#错误红点标记
        if (show or len(save)>0) and not ThreeD:
            cv2.putText(img2,str(t),(1050,590),font,0.5,(255,255,255),1)#在img2上显示时间
        time_fps=time.time()
        if len(save)==0 and show or (ThreeD and len(save)==0):
            k=int((time_fps-time_read)*200)
        if show and not ThreeD:
            f+=1
            if f==1:
                time_fps=time.time()
                try:
                    fps=str(int(10/(time_fps-time_FPS)+0.5)/10)
                    fs=int(float(fps)/10+0.5)*10
                except:
                    fps='200.0'
                    fs=200
                if fs==0:
                    fs=10
            elif f%fs==0:
                fps=str(int(fs*10/(time_fps-time_FPS)+0.5)/10)
                time_FPS=time_fps
        if len(save)>0:
            fps=str(int(FPS*10+0.5)/10)
        if (show or len(save)>0) and not ThreeD:
            cv2.putText(img2,'fps:'+fps,(1120,590),font,0.5,(255,255,255),1)
        if show and not ThreeD:
            #cv2.destroyAllWindows()
            #cv2.namedWindow('img')
            #cv2.createTrackbar('time','img',int(t),int(t0),nothing)
            cv2.imshow('img',img2)
            key = cv2.waitKey(1) & 0xff
            #Esc键退出
            if key == 27:
                break
            elif key==32:#空格暂停
                if len(music)>0:
                    pygame.mixer.music.stop()
                cv2.waitKey(0)
                time_read=time.time()-k/200
                if len(music)>0:
                    pygame.mixer.music.play(start=k/200)
            elif key==ord('q'):#后退
                k-=100
                #time_read+=0.5
                if time_read>time_fps:
                    time_read=time_fps
                if k<0:
                    k=0
                if len(music)>0:
                    pygame.mixer.music.stop()
                cv2.waitKey(0)
                time_read=time.time()-k/200
                if len(music)>0:
                    pygame.mixer.music.play(start=k/200)
            elif key==ord('e'):#快进
                #time_read-=0.5
                k+=100
                if len(music)>0:
                    pygame.mixer.music.stop()
                cv2.waitKey(0)
                time_read=time.time()-k/200
                if len(music)>0:
                    pygame.mixer.music.play(start=k/200)
            #time_read-=t-cv2.getTrackbarPos('time','img')
        #print('\r'+str(t)+'/'+str((t0-300)/100)+'  ',end='')
        
        if ThreeD:
            texts=[]#显示的文字
            t=0
            for a in range(len(data)):
                if len(data[a])>k:
                    t=max(t,data[a][k][0]/1000)
                    x=data[a][k][1]
                    y=data[a][k][2]
                    z=data[a][k][3]
                    angle=data[a][k][4]
                else:
                    t=max(t,data[a][-1][0]/1000)
                    x=data[a][-1][1]
                    y=data[a][-1][2]
                    z=data[a][-1][3]
                    angle=data[a][-1][4]
                c=color(a)
                #aixs.append([(x,y,z),c,5,1,'ring'])
                #drone.append([x,y,z,c])
                drone3d(aixs,x,y,z,color(a,127),angle/180*np.pi)
                drone3d(aixs,x,y,0,color(a,-127),angle/180*np.pi)
                texts.append([str(a+1)+'('+str(int(x+0.5))+','+str(int(y+0.5))+','+str(int(z+0.5))+')',(0,140+30*a),0.5,c,1,'text'])
            texts.append(['T+'+str(t),(0,80),0.5,(255,255,255),1,'text'])
            errors=[]#圈出错误的飞机
            for m in range(0,len(aixs),12):
                for n in range(m+12,len(aixs),12):#计算距离
                    distance=((aixs[m][0][0]-aixs[n][0][0]+aixs[m+2][0][0]-aixs[n+2][0][0])**2+(aixs[m][0][1]-aixs[n][0][1]+aixs[m+2][0][1]-aixs[n+2][0][1])**2)**0.5/2
                    if distance<50:
                        warnings.warn('In '+str(int(t))+'s,distance between d'+str(int(m/12+1))+' and d'+str(int(n/12+1))+' is less than '+str(int(distance/10)+1)+'0cm.在'+str(int(t))+'秒，无人机'+str(int(m/12+1))+'和无人机'+str(int(n/12+1))+'之间的距离小于'+str(int(distance/10)+1)+'0厘米。',Warning,2)
                        #print(t,distance,int(distance/20),m+1,n+1)#距离太近就输出错误
                        if len(track)==0:
                            errors.append([((aixs[m][0][0]+aixs[m+2][0][0])/2,(aixs[m][0][1]+aixs[m+2][0][1])/2,aixs[m][0][2]),(0,0,255),10,1,'sphere'])#错误红圈标记
                            errors.append([((aixs[n][0][0]+aixs[n+2][0][0])/2,(aixs[n][0][1]+aixs[n+2][0][1])/2,aixs[n][0][2]),(0,0,255),10,1,'sphere'])
                        else:
                            errors.append([((aixs[m][0][0]+aixs[m+2][0][0])/2,(aixs[m][0][1]+aixs[m+2][0][1])/2,aixs[m][0][2]),(0,0,255),10,1,'ring'])#错误红圈标记
                            errors.append([((aixs[n][0][0]+aixs[n+2][0][0])/2,(aixs[n][0][1]+aixs[n+2][0][1])/2,aixs[n][0][2]),(0,0,255),10,1,'ring'])
            img=IIID.show(aixs+lines+errors+texts,center,1280,720,[imshow[0],imshow[1],1,0,0],d)
            f+=1
            if f==1:
                time_fps=time.time()
                try:
                    fps=str(int(10/(time_fps-time_FPS)+0.5)/10)
                    fs=int(float(fps)/10+0.5)*10
                except:
                    fps='200.0'
                    fs=200
                if fs==0:
                    fs=10
            elif f%fs==0:
                fps=str(int(fs*10/(time_fps-time_FPS)+0.5)/10)
                time_FPS=time_fps
            if len(save)>0:
                fps=str(int(FPS*10+0.5)/10)
            texts.append(['FPS:'+fps,(0,110),0.5,(255,255,255),1,'text'])
            if len(track)==1:
                if len(data[track[0]])>k:
                    x=data[track[0]][k][1]
                    y=data[track[0]][k][2]
                    z=data[track[0]][k][3]
                else:
                    x=data[track[0]][-1][1]
                    y=data[track[0]][-1][2]
                    z=data[track[0]][-1][3]
                center=(x,y,z+5)
            if len(track)==3:
                center=track
            if len(track)==0:
                img=IIID.show(aixs+lines+errors+texts,center,1280,720,[imshow[0],imshow[1],1,0,0],d)
            else:
                img=IIID2.show(aixs+lines+errors,center,3840,1920)
            if len(save)==0:
                cv2.imshow('img',img)
                key = cv2.waitKey(1) & 0xff
                #Esc键退出
                if key == 27:
                    break
                elif key==32:#长按空格键暂停，暂停后可以按wasd旋转，按esc退出暂停
                    if len(music)>0:
                        pygame.mixer.music.stop()
                    imshow[0],imshow[1]=IIID.show(aixs+lines+errors+texts,center,1280,720,[imshow[0],imshow[1],1],d)
                    i=imshow[0]-int(k/200*36+0.5)
                    time_read=time.time()-k/200
                    if len(music)>0:
                        pygame.mixer.music.play(start=k/200)
                elif key==ord('q'):#后退
                    k-=200
                    #time_read+=0.5
                    if time_read>time_fps:
                        time_read=time_fps
                    if k<0:
                        k=0
                    if len(music)>0:
                        pygame.mixer.music.stop()
                    cv2.waitKey(0)
                    time_read=time.time()-k/200
                    if len(music)>0:
                        pygame.mixer.music.play(start=k/200)
                elif key==ord('e'):#快进
                    k+=200
                    if len(music)>0:
                        pygame.mixer.music.stop()
                    cv2.waitKey(0)
                    time_read=time.time()-k/200
                    if len(music)>0:
                        pygame.mixer.music.play(start=k/200)
            
        if not show and len(save)==0 and not ThreeD:
            k+=1
        if len(save)>0:
            if ThreeD:
                video.write(img)
            else:
                video.write(img2)
            K+=200/FPS
            k=int(K+0.5)
    if (show and len(save)==0) or (ThreeD and len(save)==0):
        cv2.destroyAllWindows()
        if len(music)>0:
            pygame.mixer.music.stop()
    timer=time.time()-time_read
    print('平均帧率：'+str(int(10*f/timer+0.5)/10))
    print('飞行总时间：'+str(int((time.time()-time_read)*1000+0.5)/1000)+'秒')
    if len(save)>0:
        print('视频保存中')
        video.release()#储存视频
        if len(music)>1:
            print('音频添加中')
            for root, dirs, files in os.walk(music[0]):
                for file in files:
                    if os.path.splitext(file)[0]==music[1]:
                        music_name=(os.path.join(root , file))
            if os.path.exists(save+'.mp4'):
                os.remove(save+'.mp4')
            video_add_audio(save+"_process.mp4",music_name,save+'.mp4')
            os.remove(save+'_process.mp4')
        elif len(music)==1:
            print('音频添加中')
            if os.path.exists(save+'.mp4'):
                os.remove(save+'.mp4')
            video_add_audio(save+"_process.mp4",music[0],save+'.mp4')
            os.remove(save+'_process.mp4')
        print(save+".mp4保存成功")
