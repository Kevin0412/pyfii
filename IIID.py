import cv2
import numpy as np
import math
import geometry as g
def iiid2iid(aixs,x,y,a,b,center=(0,0,0)):#三维坐标点投影在二维平面的位置(三维坐标点,二维平面原点xy,观察者面朝角度ab,观察者观察的中心位置)
    a=math.radians(a)
    b=math.radians(b)
    aixs=g.rotate3d((aixs[0]-center[0],aixs[1]-center[1],aixs[2]-center[2]),-a,-b)
    return x-aixs[1],y-aixs[2],aixs[0]#第一二个输出为显示的xy坐标,第三个输出为点与观察者的相对距离(用于确定渲染的先后顺序,远先近后)
def sphere(img,aixs,x,y,a,b,color,r=1,center=(0,0,0),n=-1):#在img上显示球体（点）(img,球心坐标,二维平面原点xy,观察者面朝角度ab,颜色,半径,观察者观察的中心位置)
    x,y,z=iiid2iid(aixs,x,y,a,b,center)
    cv2.circle(img,(int(x+0.5),int(y+0.5)),r,color,n)
def line(img,aixs1,aixs2,x,y,a,b,color,r=1,center=(0,0,0),t=8):#在img上显示线段(img,端点1坐标,端点2坐标,二维平面原点xy,观察者面朝角度ab,颜色,粗细,观察者观察的中心位置,直线类型)
    x1,y1,z1=iiid2iid(aixs1,x,y,a,b,center)
    x2,y2,z2=iiid2iid(aixs2,x,y,a,b,center)
    cv2.line(img,(int(x1+0.5),int(y1+0.5)),(int(x2+0.5),int(y2+0.5)),color,r,t)
def distance(aixs,x,y,A,B,center=(0,0,0)):#计算距离
    if aixs[-1]=='text':
        return -10000
    elif aixs[-1]=='line':
        return iiid2iid(((aixs[0][0]+aixs[1][0])/2,(aixs[0][1]+aixs[1][1])/2,(aixs[0][2]+aixs[1][2])/2),x,y,A,B,center)[2]
    elif aixs[-1]=='sphere':
         return iiid2iid(aixs[0],x,y,A,B,center)[2]
def show(aixs,center=(0,0,0),x=720,y=720,imshow=[-1]):#显示(aixs：记录所有需要显示的点线面的列表,观察者观察的中心位置,显示的视图大小,imshow：为显示无人机而设的变量，请自行理解)
    if imshow[-1]==0:
        A=imshow[0]
        B=imshow[1]
        k=imshow[2]
        l=imshow[3]
    elif imshow[-1]==1:
        A=imshow[0]
        B=imshow[1]
        k=1
        l=0
    else:
        A=90
        B=0
        k=1
        l=0
    aixs=sorted(aixs,key = lambda u:distance(u,x,y,A,B,center),reverse=True)#计算渲染顺序
    while(True):
        #font=cv2.FONT_HERSHEY_SIMPLEX
        img=np.zeros((y,x,3),np.uint8)
        for aix in aixs:
            if aix[-1]=='sphere':
                sphere(img,aix[0],int(x/2+0.5),int(y/2+0.5),A,B,aix[1],aix[2],center,aix[3])
            elif aix[-1]=='line':
                line(img,aix[0],aix[1],int(x/2+0.5),int(y/2+0.5),A,B,aix[2],aix[3],center,aix[4])
            elif aix[-1]=='text':
                cv2.putText(img,aix[0],aix[1],cv2.FONT_HERSHEY_SIMPLEX,aix[2],aix[3],aix[4])
        A=(A+180)%360-180
        cv2.putText(img,str(A),(0,20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,255,255),1)
        cv2.putText(img,str(B),(0,50), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,255,255),1)
        if not imshow[-1]==0:
            cv2.imshow('img',img)
        key=cv2.waitKey(1)&0xFF
        if key==27:#esc键退出
            break
        elif key==ord('d'):#w,a,s,d,左右上下旋转
            A+=k
            A=(A+180)%360-180
            k+=1
            l=0
        elif key==ord('a'):
            A-=k
            A=(A+180)%360-180
            k+=1
            l=0
        elif key==ord('w'):
            B-=k
            if B<-90:
                B=-90
            k+=1
            l=0
        elif key==ord('s'):
            B+=k
            if B>90:
                B=90
            k+=1
            l=0
        else:
            l+=1
            #print(l)
            if l>49:
                k=1
                l=0
        if imshow[-1]==0:
            break
    if imshow[-1]==0:
        return img
    elif imshow[-1]==1:
        return A,B
    else:
        cv2.destroyAllWindows()
