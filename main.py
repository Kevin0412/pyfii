import drone
import os
import read_xml
import cv2show

class Fii:
    def __init__(self,name,drones):
        self.name=name
        self.ds=drones

    def show(self):
        dots=[]
        t0=0
        for d in self.ds:
            dots.append(read_xml.dots2line(d.outputString,fii=[d.X,d.Y]))
            t0=max(t0,len(read_xml.dots2line(d.outputString,fii=[d.X,d.Y])))
        cv2show.show(dots,t0)

    def save(self):
        if not os.path.exists(self.name):
            os.makedirs(self.name)

        file=open(self.name+'\\'+self.name+'.fii',"w",encoding='utf-8')
        file.write('''<?xml version="1.0" encoding="utf-8"?>
<GoertekGraphicXml>
  <DeviceType DeviceType="F400" />
  <AreaL AreaL="600" />
  <AreaW AreaW="600" />
  <AreaH AreaH="300" />
''')
        k=1
        for d in self.ds:
            file.write('  <Actions actionname="动作组'+str(k)+'" />')
            file.write('\n')
            file.write('''  <ActionFlight actionfname="动作组'''+str(k)+'''无人机'''+str(k)+'''" />
  <ActionFlightID actionfid="动作组'''+str(k)+'''无人机'''+str(k)+'''UAVID'''+str(k)+'''00'''+str(k)+'''" />
  <ActionFlightPosX actionfX="动作组'''+str(k)+'''无人机'''+str(k)+'''pos'''+str(d.X)+'''" />
  <ActionFlightPosY actionfY="动作组'''+str(k)+'''无人机'''+str(k)+'''pos'''+str(d.Y)+'''" />
  <ActionFlightPosZ actionfZ="动作组'''+str(k)+'''无人机'''+str(k)+'''pos0" />
''')
            for t in d.times:
                file.write('  <动作组'+str(k)+'Controls time="'+str(t)+'" />')
                file.write('\n')
            k+=1
        file.write('</GoertekGraphicXml>')
        file.close()
        
        if not os.path.exists(self.name+'\\动作组'):
            os.makedirs(self.name+'\\动作组') 
        file=open(self.name+'\\动作组\\checksums.xml',"w",encoding='utf-8')
        file.write('<?xml version="1.0" encoding="utf-8"?>')
        file.write('\n')
        file.write('<CheckSumXml>')
        file.write('\n')
        k=1
        for d in self.ds:
            file.write('  <CheckSums flightchecksum="动作组'+str(k)+'无人机'+str(k)+'UAVID'+str(k)+'00'+str(k)+'CheckSum0" />')
            file.write('\n')
            k+=1
        file.write('</CheckSumXml>')
        file.close()

        k=1
        for d in self.ds:
            if not os.path.exists(self.name+'\\动作组\\动作组'+str(k)):
                os.makedirs(self.name+'\\动作组\\动作组'+str(k)) 
            file=open(self.name+'\\动作组\\动作组'+str(k)+'\\webCodeAll.xml',"w",encoding='utf-8')
            file.write(d.outputString)
            file.close()
            k+=1
        print('已保存'+self.name)

if __name__=='__main__':
    d1=drone.Drone(100,100)
    d1.takeoff(0,100)

    d1.intime(3)
    d1.move2(500,100,150)

    d1.intime(10)
    d1.land()
    d1.end()

    d2=drone.Drone(200,200)
    d2.takeoff(0,200)
    
    d2.intime(3)
    d2.move2(400,200,150)

    d2.intime(10)
    d2.land()
    d2.end()

    F=Fii('测试',[d1,d2])
    F.save()
    F.show()