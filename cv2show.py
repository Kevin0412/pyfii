import cv2
import numpy as np
import read_xml
import os
import time
import read_fii

def color(n):
    n=int(n*765/7)
    x=255
    if int((n%765)/255)==0:
        return(255-n%255,n%255,x)
    if int((n%765)/255)==1:
        return(n%255,x,255-n%255)
    if int((n%765)/255)==2:
        return(x,255-n%255,n%255)

def show(data,t0,show=True,save=""):
    time_start=time.time()
    if len(save)>0:
        video = cv2.VideoWriter(save+".mp4", cv2.VideoWriter_fourcc('I', '4', '2', '0'), 100,(1120,560))
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
    print('读取文件耗时：'+str(int((time_read-time_start)*1000+0.5)/1000)+'秒')
    k=0
    print('时间\t距离\t距离程度\t错误无人机')
    time_FPS=time.time()
    f=0#记录帧数
    while k < t0:
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
            if a<4:
                cv2.putText(img2,str(a+1)+' ('+str(x)+','+str(y)+','+str(z)+')',(560+a*140,520), font, 0.5,color(a),1)
            else:
                cv2.putText(img2,str(a+1)+' ('+str(x)+','+str(y)+','+str(z)+')',(a*140,550), font, 0.5,color(a),1)#在img2上画出无人机的位置并显示坐标
            aixs.append((x,y,z,a))
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
                    cv2.circle(img2,(aixs[m][0],560-aixs[m][1]),5,(0,0,255),-1)
                    cv2.circle(img2,(560+aixs[m][0],250-aixs[m][2]),5,(0,0,255),-1)
                    cv2.circle(img2,(560+aixs[m][1],500-aixs[m][2]),5,(0,0,255),-1)
                    cv2.circle(img2,(aixs[n][0],560-aixs[n][1]),5,(0,0,255),-1)
                    cv2.circle(img2,(560+aixs[n][0],250-aixs[n][2]),5,(0,0,255),-1)
                    cv2.circle(img2,(560+aixs[n][1],500-aixs[n][2]),5,(0,0,255),-1)#错误红点标记
        cv2.putText(img2,str(t),(980,550),font,0.5,(255,255,255),1)#在img2上显示时间
        f+=1
        time_fps=time.time()
        if len(save)==0:
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
            fps='100.0'
        cv2.putText(img2,'fps:'+fps,(1040,550),font,0.5,(255,255,255),1)
        if show:
            cv2.imshow('img',img2)
            key = cv2.waitKey(1) & 0xff
            #Esc键退出
            if key == 27:
                break
            elif key==32:#空格暂停
                cv2.waitKey(0)
                time_read=time_fps-k/100
            elif key==ord('q'):#后退
                time_read+=0.5
                if time_read>time_fps:
                    time_read=time_fps
                cv2.waitKey(0)
            elif key==ord('e'):#快进
                time_read-=0.5
                cv2.waitKey(0)
        if len(save)>0:
            video.write(img2)
            print(t)
            k+=1
    cv2.destroyAllWindows()
    timer=time.time()-time_read
    print('平均帧率：'+str(int(10*f/timer+0.5)/10))
    print('飞行总时间：'+str(time.time()-time_read)+'秒')
    if len(save)>0:
        video.release()#储存视频

if __name__=='__main__':
    fii=True#是否读取.fii
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
    show(data,t0,show=False,save='1')