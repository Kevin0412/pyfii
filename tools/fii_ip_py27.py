import os
def ip(fii,csv,flights=7):
    with open(csv+'.csv','r') as I:
        Ip=I.read()
        Ip2=Ip.split('\n')
        ips=[]
        for i in Ip2:
            ips.append(i.split(','))
    ipsfii=['']
    for x in range(1,len(ips[2])):
        if ips[2][x]=='1':
            ipfii=''
            if ips[0][1]!='0':
                ipfii+=ips[0][1]
            ipfii+='0'*(3-len(ips[1][x]))
            ipfii+=ips[1][x]
            ipsfii.append([ipfii,ips[0][1]+'.'+ips[1][x]])
    if len(ipsfii)<=flights:
        raise Exception('No enough drones.')
    
    for root, dirs, files in os.walk(fii):
        for file in files:
            if os.path.splitext(file)[1] == '.fii':
                fii_name=(os.path.join(root , file))
    with open(fii_name,"r") as F:
        data = F.read()
    data=data.split('\n')
    xml=[]
    n=0
    for d in data:
        n+=1
        xml.append([d.split('  ')[-1],len(d.split('  '))])
    for x in range(flights):
        x+=1
        for xm in xml:
            if xm[0][0:52]=='<ActionFlightID actionfid="\xe5\x8a\xa8\xe4\xbd\x9c\xe7\xbb\x84'+str(x)+'\xe6\x97\xa0\xe4\xba\xba\xe6\x9c\xba'+str(x)+'UAVID':
                xm[0]='<ActionFlightID actionfid="\xe5\x8a\xa8\xe4\xbd\x9c\xe7\xbb\x84'+str(x)+'\xe6\x97\xa0\xe4\xba\xba\xe6\x9c\xba'+str(x)+'UAVID'+ipsfii[x][0]+'" />'
                print('192.168.'+ipsfii[x][1]+' to flight'+str(x))
    newfii=''
    for xm in xml:
        newfii+='  '*(xm[1]-1)+xm[0]+'\n'
    with open(fii_name,"w+") as F:
        F.write(newfii)
    print('Saved successfully. All ip(s) of all drone(s) succeeded!')

if __name__=='__main__':
    ip('dntg','ip')
