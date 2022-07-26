import os
import shutil
from .read import dots2line
import warnings

class Fii:
    def __init__(self,name,drones,music=''):
        self.name=name
        self.ds=drones
        self.dots=[]
        self.t0=0
        self.music=music
        n=0
        for d in self.ds:
            n+=1
            line=dots2line(d.outputString,fii=[d.X,d.Y])
            self.dots.append(line[0])
            if len(line[2])>0:
                for warn in line[2]:
                    warnings.warn('d'+str(n)+' 无人机'+str(n)+':'+warn,Warning,2)
            self.t0=max(self.t0,dots2line(d.outputString,fii=[d.X,d.Y])[1])

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
        if len(self.music)>0:
            file.write('<MusicName path="'+self.music.split('.')[0]+'" />')
            file.write('\n')
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
        if len(self.music)>0:
            shutil.copyfile(self.music,self.name+'\\动作组\\'+self.music)
        print('已保存'+self.name)