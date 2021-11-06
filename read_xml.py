def read_xml(data,fii=[]):#格式转换,xml指令转换为python指令
    data=data.split('\n')
    xml=[]
    n=0
    for d in data:
        n+=1
        #print(d.split('  ')[-1],str(len(d.split('  '))))
        xml.append(d.split('  ')[-1])
    dots=[]
    time=0
    for k in range(len(xml)):
        if xml[k][1:6]=='block':
            #print(xml[k].split('"')[1])
            if xml[k].split('"')[1]=='block_inittime':
                time=int(xml[k+1][19:21])*60+int(xml[k+1][22:24])*1000
                #print(time)
            elif xml[k].split('"')[1]=='block_delay':
                time+=int(xml[k+2][19:-8])
                #print(time)
            elif xml[k].split('"')[1]=='Goertek_MoveToCoord':
                x=int(xml[k+1][16:-8])
                y=int(xml[k+2][16:-8])
                #print(time,x,y,int(xml[k+3][16:-8]))
                dots.append((time,x,y,int(xml[k+3][16:-8])))
            elif xml[k].split('"')[1]=='Goertek_Start':
                if len(fii)==0:
                    x=int(xml[k].split('"')[3])
                    y=int(xml[k].split('"')[5])
                else:
                    x=fii[0]
                    y=fii[1]
                #print(time,x,y,0)
                dots.append((time,x,y,0))
            elif xml[k].split('"')[1]=='Goertek_TakeOff':
                #print(time,x,y,int(xml[k+1][18:-8]))
                dots.append((time,x,y,int(xml[k+1][18:-8])))
            elif xml[k].split('"')[1]=='Goertek_Land':
                #print(time,x,y,0)
                dots.append((time,x,y,0))
    return(dots)
def dots2line(file,fii=[],vilocity=125,fps=100):#将指令转换为飞行轨迹,速度单位:cm/s
    dots=read_xml(file,fii)
    x=dots[0][1]
    y=dots[0][2]
    z=dots[0][3]
    time=0
    v=vilocity/fps
    lines=[]
    while(True):
        k=-1
        for n in range(len(dots)):
            if time-dots[n][0]>0:
                k=n
        X=dots[k][1]-x
        Y=dots[k][2]-y
        Z=dots[k][3]-z
        R=(X**2+Y**2+Z**2)**0.5
        if R<=v:
            x=dots[k][1]
            y=dots[k][2]
            z=dots[k][3]
        else:
            x+=X/R*v
            y+=Y/R*v
            z+=Z/R*v
        #print(time/1000,x,y,z)
        lines.append((time,x,y,z))
        if k==len(dots)-1 and z==dots[-1][3]:
            break
        time+=1000/fps
    return(lines)
if __name__=='__main__':
    with open("test_circle.xml", "r") as F:
        data = F.read()
    #dots=read_xml(data)
    dots=dots2line(data)
    #print(dots)

