import main
import numpy as np
import math
import cv2
import geometry as g
import IIID
center=(280,280,165)
lines=[]
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
def color(n):
    x=255
    if int((n%765)/255)==0:
        return(255-n%255,n%255,x)
    if int((n%765)/255)==1:
        return(n%255,x,255-n%255)
    if int((n%765)/255)==2:
        return(x,255-n%255,n%255)
def circle(x,y,z,R,r,time,start,end,delay,a=0,b=0,show=False):#(x,y,z)为圆心,,R为长轴半径(厘米),r为半径(厘米),time为过程持续时间(秒),start为起始角度,end为结束角度,delay为取点时间间隔(毫秒),a,b为圆的角度
    t=int((time*1000)/delay)
    s=math.radians(start)
    e=math.radians(end)
    a=math.radians(a)
    b=math.radians(b)
    k=(e-s)/t
    dots=[]
    for m in range(t+1):
        d=s+k*m-b
        if math.cos(d)>0:
            d=math.atan(math.tan(d)*R/r)
        elif math.cos(d)<0:
            d=math.atan(math.tan(d)*R/r)+np.pi
        dots.append((math.cos(d)*R,r*math.sin(d)))
    n=0
    aixs=[]
    for dot in dots:
        x1=dot[0]*math.cos(a)
        y1=dot[1]
        z1=dot[0]*math.sin(a)
        r,c=g.xy2ra(x1,y1)
        x1,y1=g.ra2xy(r,c+math.atan(math.tan(b)/math.cos(a)))
        colour=color(int(n/100*765))
        x1,y1,z1=g.move3d((x1,y1,z1),x,y,z)
        aixs.append([(x1,y1,z1),colour,1,'circle'])
        n+=1
        f.move2(int(x1+0.5),int(y1+0.5),int(z1+0.5))
        f.delay(delay)
    if show:
        IIID.show(aixs+lines,center,1280,720)
if __name__=='__main__':
    file=open('test_circle.xml',"w+")
    f = main.Drone(file)
    f.takeoff(380,280,100)
    f.intime(3)
    circle(280,280,165,200,100,10,360,0,100,45,45,True)
    f.endtime()
    #f.intime(15)
    #f.land()
    #f.endtime()
    f.end()
    #print(f.outputString)
