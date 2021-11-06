import math
import numpy as np
def xy2ra(x,y):#二维坐标转化为距离方位
    r=(x**2+y**2)**0.5
    if y<0:
        a=-math.acos(x/r)
    elif y>0:
        a=math.acos(x/r)
    else:
        if x>=0:
            a=0
        else:
            a=np.pi
    return r,a
def ra2xy(r,a):#距离方位转化为二维坐标
    x=r*math.cos(a)
    y=r*math.sin(a)
    return x,y
def xyz2rab(x,y,z):#三维坐标转化为距离方位
    r,a=xy2ra(x,y)
    r,b=xy2ra(r,z)
    return r,a,b
def rab2xyz(r,a,b):#距离方位转化为三维坐标
    r,z=ra2xy(r,b)
    x,y=ra2xy(r,a)
    return x,y,z
def rotate(aixs,a):#二维旋转(坐标点,旋转角度)
    x=aixs[0]
    y=aixs[1]
    R,A=xy2ra(x,y)
    x,y=ra2xy(R,A+a)
    return (x,y)
def resize(aixs,n):#二维缩放(坐标点,缩放大小)
    x=aixs[0]*n
    y=aixs[1]*n
    return (x,y)
def move(aixs,x,y):#二维移动(坐标点,xy方向移动距离)
    x+=aixs[0]
    y+=aixs[1]
    return (x,y)
def rotate3d(aixs,a,b):#三维旋转(坐标点,旋转角度)
    x=aixs[0]
    y=aixs[1]
    z=aixs[2]
    #R,A,B=xyz2rab(x,y,z)
    #x,y,z=rab2xyz(R,A+a,B+b)
    x,y=rotate((x,y),a)
    x,z=rotate((x,z),b)
    return (x,y,z)
def resize3d(aixs,n):#三维缩放(坐标点,缩放大小)
    x=aixs[0]*n
    y=aixs[1]*n
    z=aixs[2]*n
    return (x,y,z)
def move3d(aixs,x,y,z):#三维移动(坐标点,xyz方向移动距离)
    x+=aixs[0]
    y+=aixs[1]
    z+=aixs[2]
    return (x,y,z)
