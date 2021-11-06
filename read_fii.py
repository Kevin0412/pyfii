import read_xml

def read_fii(name):
    with open(name+'\\'+name+'.fii', "r",encoding='utf-8') as F:
        data = F.read()
    data=data.split('\n')
    xml=[]
    n=0
    for d in data:
        n+=1
        #print(d.split('  ')[-1],str(len(d.split('  '))))
        xml.append(d.split('  ')[-1])
    drones=[]
    for k in range(len(xml)):
        #print(xml[k].split('"'))
        if xml[k][1:8]=='Actions':
            #print(xml[k].split('"')[1][0])
            drones.append(xml[k].split('"')[1])
    dots=[]
    t0=0
    for drone in drones:
        for k in range(len(xml)):
            if xml[k][1:16]=='ActionFlightPos' and xml[k].split('"')[1][0:4]==drone:
                if xml[k][16]=='X':
                    x=int(xml[k].split('"')[1].split('pos')[1])
                elif xml[k][16]=='Y':
                    y=int(xml[k].split('"')[1].split('pos')[1])
                #print(xml[k].split('"')[1])
        with open(name+'\\动作组\\'+drone+'\\webCodeAll.xml', "r",encoding='utf-8') as F:
            file = F.read()
        dots.append(read_xml.dots2line(file,fii=[x,y]))
        t0=max(t0,len(read_xml.dots2line(file,fii=[x,y])))
    return dots,t0
    
if __name__=='__main__':
    print(read_fii('比赛现场程序'))