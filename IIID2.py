import cv2
import numpy as np
from .transfer import *
def iiid2iid(aixs,center=(0,0,0)):
    r,a,b=xyz2rab(aixs[0]-center[0],aixs[1]-center[1],aixs[2]-center[2])
    return np.degrees(a),np.degrees(b),r
def polylines(img,plts,center,color,isclosed=True,n=1):
    plt=[]
    for p in plts:
        plt.append((iiid2iid(p,center)))
    plts=plt
    dots=[]
    for a in plts:
        dots.append([(-a[0]+180)%360/360*img.shape[1],(-a[1]+90)/180*img.shape[0]])
    if isclosed:
        for d in range(len(dots)):
            if abs(dots[d-1][0]-dots[d][0])>img.shape[1]/2:
                if dots[d-1][0]-dots[d][0]>0:
                    cv2.line(img,(int(dots[d-1][0]-img.shape[1]),int(dots[d-1][1])),(int(dots[d][0]),int(dots[d][1])),color,n)
                    cv2.line(img,(int(dots[d-1][0]),int(dots[d-1][1])),(int(dots[d][0]+img.shape[1]),int(dots[d][1])),color,n)
                else:
                    cv2.line(img,(int(dots[d-1][0]+img.shape[1]),int(dots[d-1][1])),(int(dots[d][0]),int(dots[d][1])),color,n)
                    cv2.line(img,(int(dots[d-1][0]),int(dots[d-1][1])),(int(dots[d][0]-img.shape[1]),int(dots[d][1])),color,n)
            else:
                cv2.line(img,(int(dots[d-1][0]),int(dots[d-1][1])),(int(dots[d][0]),int(dots[d][1])),color,n)
    else:
        for d in range(1,len(dots)):
            if abs(dots[d-1][0]-dots[d][0])>img.shape[1]/2:
                if dots[d-1][0]-dots[d][0]>0:
                    cv2.line(img,(int(dots[d-1][0]-img.shape[1]),int(dots[d-1][1])),(int(dots[d][0]),int(dots[d][1])),color,n)
                    cv2.line(img,(int(dots[d-1][0]),int(dots[d-1][1])),(int(dots[d][0]+img.shape[1]),int(dots[d][1])),color,n)
                else:
                    cv2.line(img,(int(dots[d-1][0]+img.shape[1]),int(dots[d-1][1])),(int(dots[d][0]),int(dots[d][1])),color,n)
                    cv2.line(img,(int(dots[d-1][0]),int(dots[d-1][1])),(int(dots[d][0]-img.shape[1]),int(dots[d][1])),color,n)
            else:
                cv2.line(img,(int(dots[d-1][0]),int(dots[d-1][1])),(int(dots[d][0]),int(dots[d][1])),color,n)
def line(img,aixs1,aixs2,color,r=1,center=(0,0,0),t=8):#在img上显示线段(img,端点1坐标,端点2坐标,颜色,粗细,观察者位置,直线类型)
    a1,b1,r1=iiid2iid(aixs1,center)
    a2,b2,r2=iiid2iid(aixs2,center)
    plts=[]
    m=int(((a1-a2)**2+(b1-b2)**2)**0.5/8+1)
    for n in range(m+1):
        plts.append((aixs1[0]+n*(aixs2[0]-aixs1[0])/m,aixs1[1]+n*(aixs2[1]-aixs1[1])/m,aixs1[2]+n*(aixs2[2]-aixs1[2])/m))
    polylines(img,plts,center,color,False,r)
def ring(img,aixs,color,r,center=(0,0,0),n=1):
    a1,b1,r1=iiid2iid(aixs,center)
    plts=[]
    if r1==0:
        cv2.line(img,(0,int(img.shape[0]/2)),(img.shape[1],int(img.shape[0]/2)),color,n)
    else:
        m=int(r/r1*180+1)
        if m<12:
            m=12
        elif m>360:
            m=360
        for l in range(m):
            l=l/m*2*np.pi
            plts.append((aixs[0]+r*np.cos(l),aixs[1]+r*np.sin(l),aixs[2]))
        polylines(img,plts,center,color,True,n)
def distance(aixs,center=(0,0,0)):#计算距离
    if aixs[-1]=='text':
        return -10000
    elif aixs[-1]=='line':
        return iiid2iid(((aixs[0][0]+aixs[1][0])/2,(aixs[0][1]+aixs[1][1])/2,(aixs[0][2]+aixs[1][2])/2),center)[2]
    elif aixs[-1]=='sphere':
        return iiid2iid(aixs[0],center)[2]
    elif aixs[-1]=='ring':
        return iiid2iid(aixs[0],center)[2]
def show(aixs,center=(0,0,0),x=3840,y=1920):#显示(aixs：记录所有需要显示的点线面的列表,观察者位置,显示的视图大小)
    aixs=sorted(aixs,key = lambda u:distance(u,center),reverse=True)#计算渲染顺序
    img=np.zeros((y,x,3),np.uint8)
    for aix in aixs:
        if aix[-1]=='line':
            line(img,aix[0],aix[1],aix[2],aix[3],center,aix[4])
        elif aix[-1]=='ring':
            ring(img,aix[0],aix[1],aix[2],center,aix[3])
    return img