import cv2
import numpy as np

def main(img,z=(80,250)):#img为图片，z为高度，一个为前高度，一个为后高度
    img=cv2.resize(img,(560,560))
    def get_point(event,x,y,flags,param):
        if event==cv2.EVENT_LBUTTONDOWN:
            print('d.move2('+str(560-y)+','+str(x)+','+str(int(z[0]*x/560+z[1]*(560-x)/560+0.5))+')')
    cv2.namedWindow('image')
    cv2.setMouseCallback('image',get_point)
    while(True):
        cv2.imshow('image',img)
        if cv2.waitKey(20)&0xFF==27:#esc退出
            break
    cv2.destroyAllWindows()

if __name__=='__main__':
    main(cv2.imread('test2.jpg'))
