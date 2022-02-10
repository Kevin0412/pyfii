import os
import time
import uuid
import warnings

import cv2
import numpy as np
import pygame

from ffmpy import FFmpeg


# 视频添加音频
def video_add_audio(video_path: str, audio_path: str, output_dir: str):
    _ext_video = os.path.basename(video_path).strip().split('.')[-1]
    _ext_audio = os.path.basename(audio_path).strip().split('.')[-1]
    if _ext_audio not in ['mp3', 'wav']:
        raise Exception('audio format not support')
    _codec = 'copy'
    if _ext_audio == 'wav':
        _codec = 'aac'
    result = os.path.join(
        output_dir, '{}.{}'.format(
            uuid.uuid4(), _ext_video))
    ff = FFmpeg(
        inputs={video_path: None, audio_path: None},
        outputs={result: '-map 0:v -map 1:a -c:v copy -c:a {} -shortest'.format(_codec)})
    print(ff.cmd)
    ff.run()
    return result

def nothing(x):
    pass

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

'''def color(n):
    n=n*180/7
    x=255
    if int((n%765)/255)==0:
        return(255-n%255,n%255,x)
    if int((n%765)/255)==1:
        return(n%255,x,255-n%255)
    if int((n%765)/255)==2:
        return(x,255-n%255,n%255)'''

def show(data,t0,music,show=True,save="",FPS=100):
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
        for a in range(7):
            if a<4:
                for x in range(140):
                    cv2.rectangle(img,(560+a*140+x,500),(560+a*140+x,530),color(a,(x-70)/70*125),-1)
            else:
                for x in range(140):
                    cv2.rectangle(img,(560+(a-4)*140+x,530),(560+(a-4)*140+x,560),color(a,(x-70)/70*125),-1)
        for x in range(4):
            cv2.rectangle(img,(560+x*140,500),(700+x*140,530),(255,255,255),1)
            cv2.rectangle(img,(560+x*140,530),(700+x*140,560),(255,255,255),1)
        cv2.rectangle(img,(1030,530),(1120,560),(255,255,255),1)
        font=cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img,'front',(560,240), font, 1,(255,255,255),1)
        cv2.putText(img,'right',(560,490), font, 1,(255,255,255),1)
        cv2.imwrite('gui.png',img)
        #生成可视化界面↑
    if show:
        if len(music)>1:
            for root, dirs, files in os.walk(music[0]):
                for file in files:
                    if os.path.splitext(file)[0]==music[1]:
                        music_name=(os.path.join(root , file))
            pygame.mixer.init()
            pygame.mixer.music.load(music_name)
            pygame.mixer.music.play(start=0.0)
    time_read=time.time()
    k=0
    K=0
    #print('时间\t距离\t距离程度\t错误无人机')
    time_FPS=time.time()
    f=0#记录帧数
    while k < t0:
        if show or len(save)>0:
            img2=cv2.imread('gui.png')
        aixs=[]
        for a in range(len(data)):
            if len(data[a])>k:
                t=data[a][k][0]/1000
                x=int(data[a][k][1]+0.5)
                y=int(data[a][k][2]+0.5)
                z=int(data[a][k][3]+0.5)
            else:
                t=data[a][-1][0]/1000
                x=int(data[a][-1][1]+0.5)
                y=int(data[a][-1][2]+0.5)
                z=int(data[a][-1][3]+0.5)
            '''cv2.circle(img2,(x,560-y),15,color(a),-1)
            cv2.rectangle(img2,(560+x-15,250-z+5),(560+x+15,250-z-5),color(a),-1)
            cv2.rectangle(img2,(560+y-15,500-z+5),(560+y+15,500-z-5),color(a),-1)'''
            if show or len(save)>0:
                if a<4:
                    cv2.putText(img2,str(a+1)+' ('+str(x)+','+str(y)+','+str(z)+')',(560+a*140,520), font, 0.5,(255,255,255),1)
                else:
                    cv2.putText(img2,str(a+1)+' ('+str(x)+','+str(y)+','+str(z)+')',(a*140,550), font, 0.5,(255,255,255),1)#在img2上画出无人机的位置并显示坐标
            aixs.append((x,y,z,a))
        if show or len(save)>0:
            Xs=sorted(aixs,key=lambda x:x[0])
            Ys=sorted(aixs,key=lambda x:x[1],reverse=True)
            Zs=sorted(aixs,key=lambda x:x[2])
            #根据距离远近渲染
            for X in Xs:
                cv2.rectangle(img2,(560+X[1]-15,500-X[2]+5),(560+X[1]+15,500-X[2]-5),color(X[3],(X[0]-280)/280*125),-1)
            for Y in Ys:
                cv2.rectangle(img2,(560+Y[0]-15,250-Y[2]+5),(560+Y[0]+15,250-Y[2]-5),color(Y[3],(280-Y[1])/280*125),-1)
            for Z in Zs:
                cv2.circle(img2,(Z[0],560-Z[1]),15,color(Z[3],(Z[2]-125)/125*125),-1)
        #print(Xs)
        #print(aixs)
        for m in range(len(aixs)):
            for n in range(m+1,len(aixs)):#计算距离
                distance=((aixs[m][0]-aixs[n][0])**2+(aixs[m][1]-aixs[n][1])**2)**0.5
                if distance<50:
                    #print(t,distance,int(distance/20),m+1,n+1)#距离太近就输出错误
                    warnings.warn('In '+str(int(t))+'s,distance between d'+str(m+1)+' and d'+str(n+1)+' is less than '+str(int(distance/10)+1)+'0cm.在'+str(int(t))+'秒，无人机'+str(m+1)+'和无人机'+str(n+1)+'之间的距离小于'+str(int(distance/10)+1)+'0厘米。',Warning,2)
                    if show or len(save)>0:
                        cv2.circle(img2,(aixs[m][0],560-aixs[m][1]),20,(0,0,255),3)
                        cv2.circle(img2,(560+aixs[m][0],250-aixs[m][2]),20,(0,0,255),3)
                        cv2.circle(img2,(560+aixs[m][1],500-aixs[m][2]),20,(0,0,255),3)
                        cv2.circle(img2,(aixs[n][0],560-aixs[n][1]),20,(0,0,255),3)
                        cv2.circle(img2,(560+aixs[n][0],250-aixs[n][2]),20,(0,0,255),3)
                        cv2.circle(img2,(560+aixs[n][1],500-aixs[n][2]),20,(0,0,255),3)#错误红点标记
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
            #cv2.destroyAllWindows()
            #cv2.namedWindow('img')
            #cv2.createTrackbar('time','img',int(t),int(t0),nothing)
            cv2.imshow('img',img2)
            key = cv2.waitKey(1) & 0xff
            #Esc键退出
            if key == 27:
                break
            elif key==32:#空格暂停
                pygame.mixer.music.stop()
                cv2.waitKey(0)
                time_read=time.time()-k/100
                pygame.mixer.music.play(start=k/100)
            elif key==ord('q'):#后退
                k-=50
                #time_read+=0.5
                if time_read>time_fps:
                    time_read=time_fps
                if k<0:
                    k=0
                pygame.mixer.music.stop()
                cv2.waitKey(0)
                time_read=time.time()-k/100
                pygame.mixer.music.play(start=k/100)
            elif key==ord('e'):#快进
                #time_read-=0.5
                k+=50
                pygame.mixer.music.stop()
                cv2.waitKey(0)
                time_read=time.time()-k/100
                pygame.mixer.music.play(start=k/100)
            #time_read-=t-cv2.getTrackbarPos('time','img')
        #print('\r'+str(t)+'/'+str((t0-300)/100)+'  ',end='')
        if not show and len(save)==0:
            k+=1
        if len(save)>0:
            video.write(img2)
            K+=100/FPS
            k=int(K+0.5)
    if show:
        cv2.destroyAllWindows()
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
            video_add_audio(save+".mp4",music_name,'')
        print(save+".mp4保存成功")