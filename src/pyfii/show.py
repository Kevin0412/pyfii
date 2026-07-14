import cmath
import os
import shutil
import uuid

import cv2
import numpy as np
from ffmpy import FFmpeg


# 视频添加音频
def video_add_audio(video_path: str, audio_path: str,output_path:str):
    _ext_video = os.path.basename(video_path).strip().split('.')[-1]
    _ext_audio = os.path.basename(audio_path).strip().split('.')[-1]
    if _ext_audio not in ['mp3', 'wav','flac','ogg']:
        print('No music!')
        shutil.copy(video_path,video_path[0:-12]+'.mp4')
    else:
        _codec = 'copy'
        if _ext_audio == 'wav':
            _codec = 'aac'
        cap = cv2.VideoCapture(video_path)
        video_duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        result =output_path.format(uuid.uuid4(), _ext_video)
        ff = FFmpeg(
            inputs={video_path: None, audio_path: None},
            outputs={result: '-map 0:v -map 1:a -c:v copy -c:a {} -t {}'.format(_codec, video_duration)})
        print(ff.cmd)
        ff.run()
        return result

'''def nothing(x):
    pass'''

def color(n,m=0):
    n=180-n*180/9
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

def iiid_rotate(a,g=np.array([0,0,-980])):# 无人机旋转
    wing_force=a-g
    unit_wing_force=wing_force/np.sqrt(wing_force[0]**2+wing_force[1]**2+wing_force[2]**2)
    
    x,y,z=unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]
    if x==0 and y==0:
        rotate_matrix=np.array([
        [1,0,0],
        [0,1,0],
        [0,0,1]
    ])
    else:
        rotate_matrix=np.array([
            [(x**2*z+y**2)/(x**2+y**2),-x*y/(z+1),x],
            [-x*y/(z+1),(x**2+y**2*z)/(x**2+y**2),y],
            [-x,-y,z]
        ])

    return rotate_matrix

def draw_drone(img,x,y,color,a=0,led=(-1,-1,-1),up=False,skin=1,device="F400",size=1):
    if device=="F400":
        if skin==0:
            if up:
                cv2.circle(img,(int(x*size),int(y*size)),15*size,color,-1)
            else:
                cv2.rectangle(img,(int((x-15)*size),int((y+5)*size)),(int((x+15)*size),int((y-5)*size)),color,-1)
        elif skin==1:
            if up:
                cv2.circle(img,(int((x-21/2*np.cos(np.pi/4+a))*size),int((y+21/2*np.sin(np.pi/4+a))*size)),8*size,color,size)
                cv2.circle(img,(int((x-21/2*np.cos(3*np.pi/4+a))*size),int((y+21/2*np.sin(3*np.pi/4+a))*size)),8*size,color,size)
                cv2.circle(img,(int((x-21/2*np.cos(-3*np.pi/4+a))*size),int((y+21/2*np.sin(-3*np.pi/4+a))*size)),8*size,color,size)
                cv2.circle(img,(int((x-21/2*np.cos(-np.pi/4+a))*size),int((y+21/2*np.sin(-np.pi/4+a))*size)),8*size,color,size)
                cv2.line(img,(int((x-21/2*np.cos(np.pi/4+a))*size),int((y+21/2*np.sin(np.pi/4+a))*size)),(int((x-21/2*np.cos(-3*np.pi/4+a))*size),int((y+21/2*np.sin(-3*np.pi/4+a))*size)),color,size)
                cv2.line(img,(int((x-21/2*np.cos(-np.pi/4+a))*size),int((y+21/2*np.sin(-np.pi/4+a))*size)),(int((x-21/2*np.cos(3*np.pi/4+a))*size),int((y+21/2*np.sin(3*np.pi/4+a))*size)),color,size)
                if led[0]>-1:
                    cv2.circle(img,(int(x*size),int(y*size)),5*size,led,-1)
            else:
                cv2.ellipse(img,(int((x+21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.ellipse(img,(int((x-21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.ellipse(img,(int((x-21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.ellipse(img,(int((x+21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.line(img,(int((x+21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(int((x-21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),color,size)
                cv2.line(img,(int((x-21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(int((x+21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),color,size)
                if led[0]>-1:
                    cv2.circle(img,(int(x*size),int((y-1/2*7.6)*size)),5*size,led,-1)
        elif skin==2:
            if up:
                red_square=(np.array([[x+16*np.cos(a),y+16*np.sin(a)],[x+16*np.cos(a+np.pi/2),y+16*np.sin(a+np.pi/2)],[x+16*np.cos(a+np.pi),y+16*np.sin(a+np.pi)],[x+16*np.cos(a-np.pi/2),y+16*np.sin(a-np.pi/2)]],np.float32)*size).astype(np.int32)
                fu=[(np.array([[x+((-7-6j)*cmath.e**(a*1j)).real,y+((-7-6j)*cmath.e**(a*1j)).imag],[x+((-6-5j)*cmath.e**(a*1j)).real,y+((-6-5j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-8-2j)*cmath.e**(a*1j)).real,y+((-8-2j)*cmath.e**(a*1j)).imag],[x+((-5-3j)*cmath.e**(a*1j)).real,y+((-5-3j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-5-3j)*cmath.e**(a*1j)).real,y+((-5-3j)*cmath.e**(a*1j)).imag],[x+((-8+3j)*cmath.e**(a*1j)).real,y+((-8+3j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-6-0j)*cmath.e**(a*1j)).real,y+((-6-0j)*cmath.e**(a*1j)).imag],[x+((-6+6j)*cmath.e**(a*1j)).real,y+((-6+6j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-6+1j)*cmath.e**(a*1j)).real,y+((-6+1j)*cmath.e**(a*1j)).imag],[x+((-5+2j)*cmath.e**(a*1j)).real,y+((-5+2j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-3-5j)*cmath.e**(a*1j)).real,y+((-3-5j)*cmath.e**(a*1j)).imag],[x+((5-5j)*cmath.e**(a*1j)).real,y+((5-5j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-2-3j)*cmath.e**(a*1j)).real,y+((-2-3j)*cmath.e**(a*1j)).imag],[x+((4-3j)*cmath.e**(a*1j)).real,y+((4-3j)*cmath.e**(a*1j)).imag],
                [x+((4-1j)*cmath.e**(a*1j)).real,y+((4-1j)*cmath.e**(a*1j)).imag],[x+((-2-1j)*cmath.e**(a*1j)).real,y+((-2-1j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-3+1j)*cmath.e**(a*1j)).real,y+((-3+1j)*cmath.e**(a*1j)).imag],[x+((5+1j)*cmath.e**(a*1j)).real,y+((5+1j)*cmath.e**(a*1j)).imag],
                [x+((5+5j)*cmath.e**(a*1j)).real,y+((5+5j)*cmath.e**(a*1j)).imag],[x+((-3+5j)*cmath.e**(a*1j)).real,y+((-3+5j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((-3+3j)*cmath.e**(a*1j)).real,y+((-3+3j)*cmath.e**(a*1j)).imag],[x+((5+3j)*cmath.e**(a*1j)).real,y+((5+3j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32),
                (np.array([[x+((1+1j)*cmath.e**(a*1j)).real,y+((1+1j)*cmath.e**(a*1j)).imag],[(x+(1+5j)*cmath.e**(a*1j)).real,y+((1+5j)*cmath.e**(a*1j)).imag]],np.float32)*size).astype(np.int32)]
                img=cv2.fillPoly(img,[red_square],color=[0,0,255])
                img=cv2.polylines(img,fu,isClosed=True,color=[0,0,0],thickness=size)
            else:
                cv2.ellipse(img,(int((x+21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.ellipse(img,(int((x-21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.ellipse(img,(int((x-21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.ellipse(img,(int((x+21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),(8*size,2*size),0,0,360,color,size)
                cv2.line(img,(int((x+21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(int((x-21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),color,size)
                cv2.line(img,(int((x-21/(2**0.5)/2)*size),int((y-1/4*7.6)*size)),(int((x+21/(2**0.5)/2)*size),int((y-3/4*7.6)*size)),color,size)
                if led[0]>-1:
                    cv2.circle(img,(int(x*size),int((y-1/2*7.6)*size)),5*size,led,-1)
    elif device=="F600":
        if up:
            cv2.circle(img,(int((x-12.6/2*np.cos(np.pi/4+a))*size),int((y+12.6/2*np.sin(np.pi/4+a))*size)),5*size,color,size)
            cv2.circle(img,(int((x-12.6/2*np.cos(3*np.pi/4+a))*size),int((y+12.6/2*np.sin(3*np.pi/4+a))*size)),5*size,color,size)
            cv2.circle(img,(int((x-12.6/2*np.cos(-3*np.pi/4+a))*size),int((y+12.6/2*np.sin(-3*np.pi/4+a))*size)),5*size,color,size)
            cv2.circle(img,(int((x-12.6/2*np.cos(-np.pi/4+a))*size),int((y+12.6/2*np.sin(-np.pi/4+a))*size)),5*size,color,size)
            cv2.line(img,(int((x-12.6/2*np.cos(np.pi/4+a))*size),int((y+12.6/2*np.sin(np.pi/4+a))*size)),(int((x-12.6/2*np.cos(-3*np.pi/4+a))*size),int((y+12.6/2*np.sin(-3*np.pi/4+a))*size)),color,size)
            cv2.line(img,(int((x-12.6/2*np.cos(-np.pi/4+a))*size),int((y+12.6/2*np.sin(-np.pi/4+a))*size)),(int((x-12.6/2*np.cos(3*np.pi/4+a))*size),int((y+12.6/2*np.sin(3*np.pi/4+a))*size)),color,size)
            if led[0]>-1:
                cv2.circle(img,(int(x*size),int(y*size)),3*size,led,-1)
        else:
            cv2.ellipse(img,(int((x+12.6/(2**0.5)/2)*size),int((y-1/4*4.0)*size)),(5*size,2*size),0,0,360,color,size)
            cv2.ellipse(img,(int((x-12.6/(2**0.5)/2)*size),int((y-1/4*4.0)*size)),(5*size,2*size),0,0,360,color,size)
            cv2.ellipse(img,(int((x-12.6/(2**0.5)/2)*size),int((y-3/4*4.0)*size)),(5*size,2*size),0,0,360,color,size)
            cv2.ellipse(img,(int((x+12.6/(2**0.5)/2)*size),int((y-3/4*4.0)*size)),(5*size,2*size),0,0,360,color,size)
            cv2.line(img,(int((x+12.6/(2**0.5)/2)*size),int((y-1/4*4.0)*size)),(int((x-21/(2**0.5)/2)*size),int((y-3/4*4.0)*size)),color,size)
            cv2.line(img,(int((x-12.6/(2**0.5)/2)*size),int((y-1/4*4.0)*size)),(int((x+21/(2**0.5)/2)*size),int((y-3/4*4.0)*size)),color,size)
            if led[0]>-1:
                cv2.circle(img,(int(x*size),int((y-1/2*4.0)*size)),3*size,led,-1)
    else:
        raise(Exception("Error Drone Type!无人机型号不支持"))

def drone3d(aixs,x,y,z,c,a,led=(-1,-1,-1),acceleration=(0,0,0),g=np.array([0,0,-980]),device="F400"):
    if device=="F400":
        rotate_matrix=iiid_rotate(np.array([acceleration[0],acceleration[1],acceleration[2]]),g)
        wing_force=np.asarray(acceleration, dtype=float)-g
        unit_wing_force=wing_force/np.sqrt(wing_force[0]**2+wing_force[1]**2+wing_force[2]**2)
        ring1=np.dot(rotate_matrix,np.array([21/2*np.cos(np.pi/4+a),21/2*np.sin(np.pi/4+a),0]))[None, :]
        ring2=np.dot(rotate_matrix,np.array([21/2*np.cos(3*np.pi/4+a),21/2*np.sin(3*np.pi/4+a),0]))[None, :]
        ring3=np.dot(rotate_matrix,np.array([21/2*np.cos(-3*np.pi/4+a),21/2*np.sin(-3*np.pi/4+a),0]))[None, :]
        ring4=np.dot(rotate_matrix,np.array([21/2*np.cos(-np.pi/4+a),21/2*np.sin(-np.pi/4+a),0]))[None, :]
        aixs.append([(x+ring1[0][0],y+ring1[0][1],z+ring1[0][2]),c,(14.9-21/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring2[0][0],y+ring2[0][1],z+ring2[0][2]),c,(14.9-21/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring3[0][0],y+ring3[0][1],z+ring3[0][2]),c,(14.9-21/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring4[0][0],y+ring4[0][1],z+ring4[0][2]),c,(14.9-21/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring1[0][0],y+ring1[0][1],z+ring1[0][2]),(x+ring3[0][0],y+ring3[0][1],z+ring3[0][2]),c,1,8,'line'])
        aixs.append([(x+ring2[0][0],y+ring2[0][1],z+ring2[0][2]),(x+ring4[0][0],y+ring4[0][1],z+ring4[0][2]),c,1,8,'line'])
        if led[0]>-1:
            aixs.append([(x,y,z),led,5,-1,'sphere'])
        else:
            aixs.append([(x,y,z),c,1,-1,'sphere'])
    elif device=="F600":
        rotate_matrix=iiid_rotate(np.array([acceleration[0],acceleration[1],acceleration[2]]),g)
        wing_force=np.asarray(acceleration, dtype=float)-g
        unit_wing_force=wing_force/np.sqrt(wing_force[0]**2+wing_force[1]**2+wing_force[2]**2)
        ring1=np.dot(rotate_matrix,np.array([12.6/2*np.cos(np.pi/4+a),12.6/2*np.sin(np.pi/4+a),0]))[None, :]
        ring2=np.dot(rotate_matrix,np.array([12.6/2*np.cos(3*np.pi/4+a),12.6/2*np.sin(3*np.pi/4+a),0]))[None, :]
        ring3=np.dot(rotate_matrix,np.array([12.6/2*np.cos(-3*np.pi/4+a),12.6/2*np.sin(-3*np.pi/4+a),0]))[None, :]
        ring4=np.dot(rotate_matrix,np.array([12.6/2*np.cos(-np.pi/4+a),12.6/2*np.sin(-np.pi/4+a),0]))[None, :]
        aixs.append([(x+ring1[0][0],y+ring1[0][1],z+ring1[0][2]),c,(17.5/2-12.6/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring2[0][0],y+ring2[0][1],z+ring2[0][2]),c,(17.5/2-12.6/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring3[0][0],y+ring3[0][1],z+ring3[0][2]),c,(17.5/2-12.6/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring4[0][0],y+ring4[0][1],z+ring4[0][2]),c,(17.5/2-12.6/4*2**0.5),1,(unit_wing_force[0],unit_wing_force[1],unit_wing_force[2]),'ring'])
        aixs.append([(x+ring1[0][0],y+ring1[0][1],z+ring1[0][2]),(x+ring3[0][0],y+ring3[0][1],z+ring3[0][2]),c,1,8,'line'])
        aixs.append([(x+ring2[0][0],y+ring2[0][1],z+ring2[0][2]),(x+ring4[0][0],y+ring4[0][1],z+ring4[0][2]),c,1,8,'line'])
        if led[0]>-1:
            aixs.append([(x,y,z),led,6.7/2,-1,'sphere'])
        else:
            aixs.append([(x,y,z),c,1,-1,'sphere'])
    else:
        raise(Exception("Error Drone Type!无人机型号不支持"))


'''def color(n):
    n=n*180/9
    x=255
    if int((n%765)/255)==0:
        return(255-n%255,n%255,x)
    if int((n%765)/255)==1:
        return(n%255,x,255-n%255)
    if int((n%765)/255)==2:
        return(x,255-n%255,n%255)'''

def getGui(field,size):
    size=int(size)
    img=np.zeros((600*size,1200*size,3),np.uint8)
    cv2.rectangle(img,(0,0),(600*size,600*size),(255,255,255),size)
    for x in range(12):
        for y in range(12):
            if x==11 and y!=11:
                cv2.rectangle(img,(570*size,(580-y*50)*size),(580*size,(580-(y*50+50))*size),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
            elif x!=11 and y==11:
                cv2.rectangle(img,((x*50+20)*size,30*size),((x*50+70)*size,20*size),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
            elif x==11 and y==11:
                cv2.rectangle(img,(570*size,30*size),(580*size,20*size),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
            else:
                cv2.rectangle(img,((x*50+20)*size,(580-y*50)*size),((x*50+70)*size,(580-(y*50+50))*size),(63+128*((x+y)%2),63+128*((x+y)%2),63+128*((x+y)%2)),-1)
    cv2.rectangle(img,(600*size,0),(1200*size,270*size),(255,255,255),size)
    cv2.rectangle(img,(600*size,270*size),(1200*size,540*size),(255,255,255),size)
    for x in range(0,18):
        cv2.line(img,(600*size,(x*10+20)*size),(620*size,(x*10+20)*size),(255,255,255),size)
        cv2.line(img,(600*size,(x*10+290)*size),(620*size,(x*10+290)*size),(255,255,255),size)
        if x%5==0:
            cv2.line(img,(600*size,(x*10+20)*size),(640*size,(x*10+20)*size),(255,255,255),size)
            cv2.line(img,(600*size,(x*10+290)*size),(640*size,(x*10+290)*size),(255,255,255),size)
    legend_cols = 5
    legend_cell_w = 120
    for a in range(9):
        if a<legend_cols:
            for x in range(legend_cell_w):
                cv2.line(img,((600+a*legend_cell_w+x)*size,540*size),((600+a*legend_cell_w+x)*size,570*size),color(a,(x-legend_cell_w/2)/(legend_cell_w/2)*125),size)
        else:
            for x in range(legend_cell_w):
                cv2.line(img,((600+(a-legend_cols)*legend_cell_w+x)*size,570*size),((600+(a-legend_cols)*legend_cell_w+x)*size,600*size),color(a,(x-legend_cell_w/2)/(legend_cell_w/2)*125),size)
    for x in range(legend_cols):
        cv2.rectangle(img,((600+x*legend_cell_w)*size,540*size),((600+(x+1)*legend_cell_w)*size,570*size),(255,255,255),size)
        cv2.rectangle(img,((600+x*legend_cell_w)*size,570*size),((600+(x+1)*legend_cell_w)*size,600*size),(255,255,255),size)
    cv2.rectangle(img,((600+4*legend_cell_w+56)*size,570*size),((600+5*legend_cell_w)*size,600*size),(255,255,255),size)
    if field==4:
        cv2.rectangle(img,(20*size,580*size),(380*size,220*size),(255,255,255),size)
        cv2.rectangle(img,(1000*size,0),(1000*size,540*size),(255,255,255),size)
    font=cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img,'front',(600*size,260*size), font, size,(255,255,255),size)
    cv2.putText(img,'right',(600*size,530*size), font, size,(255,255,255),size)
    return img

def show(data,t0=None,music=None,field=6,device="F400",show=True,save="",FPS=200,max_fps=200,ThreeD=False,imshow=[120,-15],d=(600,450),track=[],skin=1,size=1,ssaa=1,workers=None):
    from .fiiRead import DroneTrack, FiiRender2D, FiiRender3D, FiiRenderPanorama
    if isinstance(data, DroneTrack):
        dt = data
    else:
        if t0 is None or music is None:
            raise TypeError("legacy show() requires data, t0 and music")
        dt = DroneTrack(data, t0, music, field, device)
    cfg = dict(skin=skin, size=size, ssaa=ssaa, imshow=imshow, d=d,
               follow=track, FPS=FPS, max_fps=max_fps, progress=show,
               workers=workers)
    if not ThreeD:
        renderer = FiiRender2D(dt, cfg)
    elif len(track) == 0:
        renderer = FiiRender3D(dt, cfg)
    else:
        renderer = FiiRenderPanorama(dt, cfg)
    if len(save) > 0:
        renderer.save(save)
    else:
        renderer.show(display=show)
