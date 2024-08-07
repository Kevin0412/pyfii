import cv2
import numpy as np

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